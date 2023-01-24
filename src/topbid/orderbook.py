""" OrderBook """

import logging

import requests
from request_boost import boosted_requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("topbid_orderbook")


class OrderBook:
    """Stores top exchange orderbook bid price and volume by pair"""

    def __init__(self, cmp_api_key, exchanges_list) -> None:
        self.cmp_api_key = cmp_api_key
        self.cmp_api_base_url = "https://min-api.cryptocompare.com"

        self.orderbook_bids = {}  # {"binance-BTC/USDT": (20000.1, 0.0001)}
        self.symbols_mappings = {}  # {"kucoin-VAIOT/USDT": "VAI/USDT"}
        self.requests_max_retry = 2
        self.requests_timeout = 1

        if isinstance(exchanges_list, str):
            exchanges_list = [exchanges_list]
        for exchange_name in exchanges_list:
            self.initialize_symbols_mappings(exchange_name)

    def _set_price_and_volume(self, _id, price, volume) -> None:
        self.orderbook_bids[_id] = (price, volume)

    def _reset(self) -> None:
        """Empty all saved pair prices"""
        self.orderbook_bids = {}

    def delete(self, exchange_name: str, pair: str):
        """
        Removes volume and price for a specific exchange/pair couple.
        Can be used when a trade has just been closed for cleanup.
        """
        _id = f"{exchange_name}-{pair}"
        del self.orderbook_bids[_id]

    def update(self, exchange_name: str, pairs: list):
        """Update orderbook with pair top buying (bid) prices"""
        urls = []
        ids = []
        for pair in pairs:
            _id = f"{exchange_name}-{pair}"
            ids.append(_id)
            urls.append(self.get_orderbook_url(exchange_name, pair))
        try:
            responses = boosted_requests(
                urls,
                max_tries=self.requests_max_retry,
                timeout=self.requests_timeout,
                verbose=False,
                parse_json=True,
            )
        except KeyError:
            self._reset()
            logger.warning("update orderbook: some requests failed, aborting")
            return

        for _id, res in zip(ids, responses):
            if "data" in res:  # kucoin
                if res["data"]["bids"] is not None:
                    self._set_price_and_volume(_id, res["data"]["bids"][0][0], res["data"]["bids"][0][1])
                continue
            if "bids" in res:  # binance
                self._set_price_and_volume(_id, res["bids"][0][0], res["bids"][0][1])
                continue
            if "result" in res:  # kraken
                key = next(iter(res["result"]))
                self._set_price_and_volume(
                    _id,
                    res["result"][key]["bids"][0][0],
                    res["result"][key]["bids"][0][1],
                )
                continue
            logger.warning("update orderbook: bad response, not matching any exchange format")

    def get_orderbook_bid_by_trade(self, trade: dict) -> tuple:
        """
        Return best price and volume on exchange for a pair (from trade).
        TODO: This function is too specific, params and returned values should be updated.
        """
        pair = trade["pair"]
        exchange_name = trade["exchange"]
        price, volume = self.orderbook_bids.get(f"{exchange_name}-{pair}", (None, None))
        if not price:
            price = trade.get("current_rate")
            logger.warning(
                "Could not find bid price in orderbook_bids for {%s} {%s}",
                exchange_name,
                pair,
            )
        return (float(price or 0), float(volume or 0))

    def initialize_symbols_mappings(self, exchange_name):
        """
        Gets all pair mappings for an exchange from CryptoCompare API
        https://min-api.cryptocompare.com/documentation?key=PairMapping&cat=pairMappingExchangeEndpoint
        """
        url = f"{self.cmp_api_base_url}/data/v2/pair/mapping/exchange?e={exchange_name.capitalize()}"
        request = requests.get(url, headers={"authorization": f"Apikey {self.cmp_api_key}"}, timeout=10)

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

        logger.info("Saved mappings from CryptoCompare API for exchange %s", exchange_name)

    def get_exchange_symbol(self, exchange_name, pair):
        """Return pair with symbol on exchange if there is a mapping"""
        _id = f"{exchange_name}-{pair}"
        return self.symbols_mappings.get(_id, pair)

    def get_orderbook_url(self, exchange_name, pair):
        """
        Helper generating URLs to exchange top orderbook APIs.
        """
        pair = self.get_exchange_symbol(exchange_name, pair)
        if exchange_name == "kraken":
            return f"https://api.kraken.com/0/public/Depth?count=1&pair={pair.replace('/', '')}"
        if exchange_name == "kucoin":
            return f"https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol={pair.replace('/', '-')}"
        if exchange_name == "binance":
            return f"https://api.binance.com/api/v3/depth?limit=1&symbol={pair.replace('/', '')}"
        raise RuntimeError(f"{exchange_name=} not supported")

    def get_chart_url(self, exchange_name, pair):
        """
        Helper generating URLs to used exchange trade charts.
        """
        exchange_pair = self.get_exchange_symbol(exchange_name, pair)
        if exchange_name == "kraken":
            return f"[{pair}](https://trade.kraken.com/charts/KRAKEN:{exchange_pair.replace('/', '-')})"
        if exchange_name == "kucoin":
            return f"[{pair}](https://www.kucoin.com/trade/{exchange_pair.replace('/', '-')})"
        if exchange_name == "binance":
            return f"[{pair}](https://www.binance.com/en/trade/{exchange_pair.replace('/', '_')})"
        raise RuntimeError(f"{exchange_name=} not supported")
