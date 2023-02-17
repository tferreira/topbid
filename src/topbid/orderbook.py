""" OrderBook """

import logging
from typing import Union

import request_boost
import requests

from topbid.scheduler import RepeatEvery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("topbid_orderbook")


class OrderBook:
    """Fetches exchange orderbook top bid/ask price and volume by pair"""

    def __init__(self, cmp_api_key: str, exchanges_list: list) -> None:
        self.cmp_api_key = cmp_api_key

        self.orderbook_bids = {}  # {"binance-BTC/USDT": (20000.1, 0.0001)}
        self.orderbook_asks = {}  # {"binance-BTC/USDT": (20000.2, 0.0002)}
        self.symbols_mappings = {}  # {"kucoin-VAIOT/USDT": "VAI/USDT"}

        self.thread = None
        self.running = False

        if isinstance(exchanges_list, str):
            exchanges_list = [exchanges_list]
        for exchange_name in exchanges_list:
            self.initialize_symbols_mappings(exchange_name)

    def start(self, update_every: int):
        """Starts the background API fetching task"""
        self.thread = RepeatEvery(update_every, self._update)
        self.thread.start()
        self.running = True

    def stop(self):
        """Stops the background API fetching task"""
        self.running = False
        if self.thread:
            self.thread.stop()
        self.orderbook_bids = {}
        self.orderbook_asks = {}

    def _set_bid_price_and_volume(self, _id: str, price: float, volume: float) -> None:
        self.orderbook_bids[_id] = (price, volume)

    def _set_ask_price_and_volume(self, _id: str, price: float, volume: float) -> None:
        self.orderbook_asks[_id] = (price, volume)

    def _reset(self) -> None:
        """Empty all saved pair prices"""
        self.orderbook_bids = {}
        self.orderbook_asks = {}

    def delete(self, exchange_name: str, pair: str) -> None:
        """
        Removes volume and price for a specific exchange/pair couple.
        Can be used when a trade has just been closed for cleanup.
        """
        _id = f"{exchange_name}-{pair}"
        self.orderbook_bids.pop(_id, None)
        self.orderbook_asks.pop(_id, None)

    def add(self, exchange_name: str, pairs: Union[str, list]):
        """Adds specific exchange/pair(s) to get prices of"""
        if not isinstance(pairs, list):
            pairs = [pairs]
        for pair in pairs:
            # Initialize pair
            _id = f"{exchange_name}-{pair}"
            self.orderbook_bids[_id] = (None, None)
            self.orderbook_asks[_id] = (None, None)

    def _update(self) -> None:
        """Updates the orderbook with pair top ask/bid prices and volumes"""
        if not self.running:
            return

        urls = []
        ids = list(self.orderbook_bids.keys())  # Get all initialized pairs
        for _id in ids:
            exchange_name, pair = _id.split("-")
            urls.append(self.get_orderbook_url(exchange_name, pair))
        try:
            responses = request_boost.boosted_requests(
                urls,
                max_tries=2,
                timeout=1,
                verbose=False,
                parse_json=True,
            )
        except KeyError:
            self._reset()
            logger.warning("update orderbook: some requests failed, aborting")
            return

        for _id, res in zip(ids, responses):
            if all(k in res for k in ("data", "code")):  # kucoin
                if res["data"]["bids"] is not None:
                    self._set_bid_price_and_volume(
                        _id, res["data"]["bids"][0][0], res["data"]["bids"][0][1]
                    )
                if res["data"]["bids"] is not None:
                    self._set_ask_price_and_volume(
                        _id, res["data"]["asks"][0][0], res["data"]["asks"][0][1]
                    )
                continue
            if all(k in res for k in ("bids", "asks", "lastUpdateId")):  # binance
                self._set_bid_price_and_volume(
                    _id, res["bids"][0][0], res["bids"][0][1]
                )
                self._set_ask_price_and_volume(
                    _id, res["asks"][0][0], res["asks"][0][1]
                )
                continue
            if all(k in res for k in ("bids", "asks", "current", "update")):  # gateio
                self._set_bid_price_and_volume(
                    _id, res["bids"][0][0], res["bids"][0][1]
                )
                self._set_ask_price_and_volume(
                    _id, res["asks"][0][0], res["asks"][0][1]
                )
                continue
            if all(k in res for k in ("result", "error")):  # kraken
                key = next(iter(res["result"]))
                self._set_bid_price_and_volume(
                    _id,
                    res["result"][key]["bids"][0][0],
                    res["result"][key]["bids"][0][1],
                )
                self._set_ask_price_and_volume(
                    _id,
                    res["result"][key]["asks"][0][0],
                    res["result"][key]["asks"][0][1],
                )
                continue
            logger.warning(
                "update orderbook: bad response, not matching any exchange format"
            )

    def get_orderbook_top_bid(self, exchange_name: str, pair: str) -> tuple:
        """
        Return best bid price and volume on exchange for a pair.
        Values can be `None` if no data is available yet.
        """
        price, volume = self.orderbook_bids.get(f"{exchange_name}-{pair}", (None, None))
        return price, volume

    def get_orderbook_top_ask(self, exchange_name: str, pair: str) -> tuple:
        """
        Return best ask price and volume on exchange for a pair.
        Values can be `None` if no data is available yet.
        """
        price, volume = self.orderbook_asks.get(f"{exchange_name}-{pair}", (None, None))
        return price, volume

    def initialize_symbols_mappings(self, exchange_name: str) -> None:
        """
        Gets all pair mappings for an exchange from CryptoCompare API
        https://min-api.cryptocompare.com/documentation?key=PairMapping&cat=pairMappingExchangeEndpoint
        """
        url = f"https://min-api.cryptocompare.com/data/v2/pair/mapping/exchange?e={exchange_name.capitalize()}"
        request = requests.get(
            url, headers={"authorization": f"Apikey {self.cmp_api_key}"}, timeout=10
        )

        # If we got an error when querying the API, log and retry next time
        if request.status_code != 200:
            logger.warning(
                "Failed to make a request to CryptoCompare API (HTTP%s)",
                request.status_code,
            )
            return

        response = request.json()
        # If the response is not successful, log and retry next time
        if response["Response"] != "Success":
            logger.warning("Error from CryptoCompare API: {%s}", response["Message"])
            return

        for mapping in response["Data"]["current"]:
            pair = f"{mapping['fsym']}/{mapping['tsym']}"
            exchange_pair = f"{mapping['exchange_fsym']}/{mapping['exchange_tsym']}"
            _id = f"{exchange_name}-{pair}"
            self.symbols_mappings[_id] = exchange_pair

        logger.info(
            "Saved mappings from CryptoCompare API for exchange %s", exchange_name
        )

    def get_exchange_symbol(self, exchange_name: str, pair: str) -> str:
        """Return pair with symbol on exchange if there is a mapping"""
        _id = f"{exchange_name}-{pair}"
        return self.symbols_mappings.get(_id, pair)

    def get_orderbook_url(self, exchange_name: str, pair: str) -> str:
        """
        Helper generating URLs to exchange top orderbook APIs.
        """
        pair = self.get_exchange_symbol(exchange_name, pair)
        if exchange_name == "binance":
            return f"https://api.binance.com/api/v3/depth?limit=1&symbol={pair.replace('/', '')}"
        if exchange_name == "gateio":
            return f"https://api.gateio.ws/api/v4/spot/order_book?currency_pair={pair.replace('/', '_')}"
        if exchange_name == "kraken":
            return f"https://api.kraken.com/0/public/Depth?count=1&pair={pair.replace('/', '')}"
        if exchange_name == "kucoin":
            return f"https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol={pair.replace('/', '-')}"
        raise RuntimeError(f"{exchange_name=} not supported")

    def get_chart_url(self, exchange_name: str, pair: str) -> str:
        """
        Helper generating URLs to used exchange trade charts.
        """
        exchange_pair = self.get_exchange_symbol(exchange_name, pair)
        if exchange_name == "binance":
            return f"[{pair}](https://www.binance.com/en/trade/{exchange_pair.replace('/', '_')})"
        if exchange_name == "gateio":
            return (
                f"[{pair}](https://www.gate.io/trade/{exchange_pair.replace('/', '_')})"
            )
        if exchange_name == "kraken":
            return f"[{pair}](https://pro.kraken.com/app/trade/{exchange_pair.lower().replace('/', '-')})"
        if exchange_name == "kucoin":
            return f"[{pair}](https://www.kucoin.com/trade/{exchange_pair.replace('/', '-')})"
        raise RuntimeError(f"{exchange_name=} not supported")
