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

    def __init__(self) -> None:
        self.orderbook_bids = {}  # {"binance-BTC/USDT": (20000.1, 0.0001)}
        self.orderbook_asks = {}  # {"binance-BTC/USDT": (20000.2, 0.0002)}
        self.symbols_mappings = {}  # {"kucoin-VAI/USDT": "VAIOT/USDT"}

        self.thread = None
        self.running = False

        # Retrieve all coins IDs from CoinGecko API (to be used to get mappings on add)
        # Response format: [{"id": "01coin", "symbol": "zoc", "name": "01coin", ...}]
        self.coingecko_all_coins_list = requests.get(
            "https://api.coingecko.com/api/v3/coins/list", timeout=5
        ).json()

    def start(self, update_every: float):
        """Starts the background API fetching task"""
        # Let's have each request timeout happening slightly before the next iteration.
        timeout = update_every - (update_every * 0.01)
        self.thread = RepeatEvery(update_every, self._update, timeout=timeout)
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

    def _init_pair(self, _id: str, force=False) -> None:
        """
        Initializes a pair with empty values.
        Called when adding a pair (but won't reset data if adding the same pair again)
        May be forced (during updates, to avoid stale prices on API issues)
        """
        if _id not in self.orderbook_bids or _id not in self.orderbook_asks or force:
            if not force:
                # only if new
                self._populate_symbol_mappings(_id)
            self.orderbook_bids[_id] = (None, None)
            self.orderbook_asks[_id] = (None, None)

    def _populate_symbol_mappings(self, _id: str) -> None:
        """
        Adds symbol mapping (may be different on exchange)
        """
        exchange_name, pair = _id.split("-")
        base_currency, quote_currency = pair.split("/")

        # Custom exchanges names on CoinGecko
        if exchange_name == "bybit":
            exchange_name = "bybit_spot"
        if exchange_name == "gateio":
            exchange_name = "gate"
        if exchange_name == "okx":
            exchange_name = "okex"

        # Retrieve coin info (multiple coins can match)
        coingecko_coin_ids = [
            coin["id"]
            for coin in self.coingecko_all_coins_list
            if coin["symbol"] == base_currency.lower()
        ]
        if not coingecko_coin_ids:
            return

        # Get tickers on exchange for each found coin
        found_tickers = []
        for coin_id in coingecko_coin_ids:
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/tickers?exchange_ids={exchange_name}"
            result = requests.get(url, timeout=5)
            if result.status_code >= 400:
                continue
            tickers = result.json()["tickers"]
            if not tickers:
                continue
            found_tickers.append(tickers[0]["base"])
        if not found_tickers:
            return

        # Best effort here. If we found an identical ticker, we do not change it.
        exchange_ticker = (
            base_currency if base_currency in found_tickers else found_tickers[0]
        )
        self.symbols_mappings[_id] = f"{exchange_ticker}/{quote_currency}"

    def _reset(self) -> None:
        """Empty all saved pair prices"""
        self.orderbook_bids = {}
        self.orderbook_asks = {}

    def delete(self, exchange_name: str, pair: str) -> None:
        """
        Removes volume and price for a specific exchange/pair couple.
        Can be used when a trade has just been closed for cleanup.
        """
        _id = f"{exchange_name.lower()}-{pair}"
        self.orderbook_bids.pop(_id, None)
        self.orderbook_asks.pop(_id, None)

    def add(self, exchange_name: str, pairs: Union[str, list]):
        """Adds specific exchange/pair(s) to get prices of"""
        if not isinstance(pairs, list):
            pairs = [pairs]
        for pair in pairs:
            # Initialize pair (if not already added)
            _id = f"{exchange_name.lower()}-{pair}"
            self._init_pair(_id)

    def _update(self, timeout) -> None:
        """Updates the orderbook with pair top ask/bid prices and volumes"""
        if not self.running:
            return

        urls = []
        ids = list(self.orderbook_bids.keys())  # Get all initialized pairs
        for _id in ids:
            exchange_name, pair = _id.split("-")
            urls.append(self.get_orderbook_url(exchange_name, pair))

        responses = request_boost.boosted_requests(
            urls,
            max_tries=1,
            timeout=timeout,
            verbose=False,
            parse_json=True,
        )

        for _id, res in zip(ids, responses):
            if res is None:
                exchange_name, pair = _id.split("-")
                logger.warning(
                    "update orderbook: request error or timeout for %s",
                    f"{pair} ({exchange_name})",
                )
                # cleanup stale data
                self._init_pair(_id, force=True)
                continue

            # this may need a bit of improvement but for now conditions order matters
            # to avoid matching wrong exchange with similar keys
            if all(k in res for k in ("code", "msg", "data", "ts")):  # okx
                if res["code"] == "0":
                    self._set_bid_price_and_volume(
                        _id,
                        float(res["data"][0]["bids"][0][0]),
                        float(res["data"][0]["bids"][0][1]),
                    )
                    self._set_ask_price_and_volume(
                        _id,
                        float(res["data"][0]["asks"][0][0]),
                        float(res["data"][0]["asks"][0][1]),
                    )
                continue
            if all(k in res for k in ("data", "code")):  # kucoin
                if res["code"] == "200000":
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
            if all(k in res for k in ("result", "retCode", "retMsg", "time")):  # bybit
                if res["retCode"] == 0:
                    self._set_bid_price_and_volume(
                        _id,
                        float(res["result"]["b"][0][0]),
                        float(res["result"]["b"][0][1]),
                    )
                    self._set_ask_price_and_volume(
                        _id,
                        float(res["result"]["a"][0][0]),
                        float(res["result"]["a"][0][1]),
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

            # if no case matched the exchange API response format, throw a warning
            logger.warning(
                "update orderbook: bad response, not matching any exchange format"
            )

    def get_orderbook_top_bid(self, exchange_name: str, pair: str) -> tuple:
        """
        Return best bid price and volume on exchange for a pair.
        Values can be `None` if no data is available yet.
        """
        price, volume = self.orderbook_bids.get(
            f"{exchange_name.lower()}-{pair}", (None, None)
        )
        return price, volume

    def get_orderbook_top_ask(self, exchange_name: str, pair: str) -> tuple:
        """
        Return best ask price and volume on exchange for a pair.
        Values can be `None` if no data is available yet.
        """
        price, volume = self.orderbook_asks.get(
            f"{exchange_name.lower()}-{pair}", (None, None)
        )
        return price, volume

    def get_exchange_symbol(self, exchange_name: str, pair: str) -> str:
        """Return pair with symbol on exchange"""
        _id = f"{exchange_name.lower()}-{pair}"
        return self.symbols_mappings.get(_id, pair)

    def get_orderbook_url(self, exchange_name: str, pair: str) -> str:
        """
        Helper generating URLs to exchange top orderbook APIs.
        """
        pair = self.get_exchange_symbol(exchange_name.lower(), pair)
        if exchange_name == "binance":
            return f"https://api.binance.com/api/v3/depth?limit=1&symbol={pair.replace('/', '')}"
        if exchange_name == "bybit":
            return f"https://api.bybit.com/v5/market/orderbook?category=spot&symbol={pair.upper().replace('/', '')}"
        if exchange_name == "gateio":
            return f"https://api.gateio.ws/api/v4/spot/order_book?currency_pair={pair.replace('/', '_')}"
        if exchange_name == "kraken":
            return f"https://api.kraken.com/0/public/Depth?count=1&pair={pair.replace('/', '')}"
        if exchange_name == "kucoin":
            return f"https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol={pair.replace('/', '-')}"
        if exchange_name in ["okx", "okex"]:
            return f"https://www.okx.com/api/v5/market/books?instId={pair.upper().replace('/', '-')}"
        raise RuntimeError(f"{exchange_name=} not supported")

    def get_chart_url(self, exchange_name: str, pair: str) -> str:
        """
        Helper generating URLs to used exchange trade charts.
        """
        exchange_name = exchange_name.lower()
        exchange_pair = self.get_exchange_symbol(exchange_name, pair)
        if exchange_name == "binance":
            return f"[{pair}](https://www.binance.com/en/trade/{exchange_pair.replace('/', '_')})"
        if exchange_name == "bybit":
            return f"[{pair}](https://www.bybit.com/en-US/trade/spot/{exchange_pair.upper()})"
        if exchange_name == "gateio":
            return (
                f"[{pair}](https://www.gate.io/trade/{exchange_pair.replace('/', '_')})"
            )
        if exchange_name == "kraken":
            return f"[{pair}](https://pro.kraken.com/app/trade/{exchange_pair.lower().replace('/', '-')})"
        if exchange_name == "kucoin":
            return f"[{pair}](https://www.kucoin.com/trade/{exchange_pair.replace('/', '-')})"
        if exchange_name in ["okx", "okex"]:
            return f"[{pair}](https://www.okx.com/trade-spot/{exchange_pair.lower().replace('/', '-')})"
        raise RuntimeError(f"{exchange_name=} not supported")
