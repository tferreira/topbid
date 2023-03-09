""" Tests for main OrderBook class """

import time
from unittest.mock import patch

import pytest
import responses

from topbid.orderbook import OrderBook


@pytest.fixture(name="coingecko_all_coins")
def fixture_coingecko_all_coins():
    """CoinGecko all coins sample mocked response"""
    rsp = responses.get(
        "https://api.coingecko.com/api/v3/coins/list",
        json=[{"id": "vaiot", "symbol": "vai", "name": "Vaiot"}],
    )
    return rsp


@pytest.fixture(name="coingecko_vaiot_kucoin")
def fixture_coingecko_vaiot_kucoin():
    """CoinGecko Vaiot coin (on Kucoin) mocked response"""
    rsp = responses.get(
        "https://api.coingecko.com/api/v3/coins/vaiot/tickers?exchange_ids=kucoin",
        json={
            "name": "Vaiot",
            "tickers": [
                {
                    "base": "VAIOT",
                    "target": "USDT",
                    "market": {
                        "name": "KuCoin",
                        "identifier": "kucoin",
                        "has_trading_incentive": False,
                    },
                    "last": 0.089662,
                    "volume": 9486263.13469452,
                    "converted_last": {
                        "btc": 4.13e-06,
                        "eth": 5.83e-05,
                        "usd": 0.089663,
                    },
                    "converted_volume": {
                        "btc": 39.133522,
                        "eth": 553.066,
                        "usd": 850563,
                    },
                    "trust_score": "green",
                    "bid_ask_spread_percentage": 0.244893,
                    "timestamp": "2023-03-09T05:26:14+00:00",
                    "last_traded_at": "2023-03-09T05:26:14+00:00",
                    "last_fetch_at": "2023-03-09T05:26:14+00:00",
                    "is_anomaly": False,
                    "is_stale": False,
                    "trade_url": "https://www.kucoin.com/trade/VAIOT-USDT",
                    "token_info_url": None,
                    "coin_id": "vaiot",
                    "target_coin_id": "tether",
                }
            ],
        },
    )
    return rsp


@pytest.fixture(name="vaiot_prices")
def fixture_vaiot_prices():
    """Kucoin VAIOT/USDT sample mocked orderbook"""
    return [
        {
            "code": "200000",
            "data": {
                "time": 1675853445037,
                "sequence": "47221666",
                "bids": [["0.197007", "1300"], ["0.197", "202.6394"]],
                "asks": [["0.197607", "1506.5178"], ["0.197608", "1300"]],
            },
        }
    ]


@responses.activate
def test_init(coingecko_all_coins):
    """OrderBook __init__()"""
    # Instantiating OrderBook hydrates coingecko_all_coins_list from CoinGecko API
    orderbook = OrderBook()
    assert orderbook.coingecko_all_coins_list == [
        {"id": "vaiot", "symbol": "vai", "name": "Vaiot"}
    ]
    assert coingecko_all_coins.call_count == 1


@responses.activate
def test_get_orderbook_tops(coingecko_all_coins, coingecko_vaiot_kucoin, vaiot_prices):
    """OrderBook get_orderbook_top_bid()/get_orderbook_top_ask()"""
    orderbook = OrderBook()
    assert coingecko_all_coins.call_count == 1

    orderbook.add("kucoin", "VAI/USDT")
    assert coingecko_vaiot_kucoin.call_count == 1

    with patch("request_boost.boosted_requests") as boosted_mock:
        boosted_mock.return_value = vaiot_prices
        # start background update
        orderbook.start(0.1)
        time.sleep(0.2)
    assert orderbook.orderbook_bids == {"kucoin-VAI/USDT": ("0.197007", "1300")}
    assert orderbook.orderbook_asks == {"kucoin-VAI/USDT": ("0.197607", "1506.5178")}

    # get_orderbook_top_bid
    top_bid = orderbook.get_orderbook_top_bid("kucoin", "VAI/USDT")
    assert top_bid == ("0.197007", "1300")

    # delete
    orderbook.delete("kucoin", "VAI/USDT")
    assert not orderbook.orderbook_bids
    assert not orderbook.orderbook_asks

    orderbook.stop()


@responses.activate
def test_get_exchange_symbol(coingecko_all_coins, coingecko_vaiot_kucoin):
    """OrderBook get_exchange_symbol()"""
    orderbook = OrderBook()
    assert coingecko_all_coins.call_count == 1
    orderbook.add("kucoin", "VAI/USDT")
    assert coingecko_vaiot_kucoin.call_count == 1
    exchange_symbol = orderbook.get_exchange_symbol("kucoin", "VAI/USDT")
    assert exchange_symbol == "VAIOT/USDT"


@responses.activate
def test_get_orderbook_url(coingecko_all_coins, coingecko_vaiot_kucoin):
    """OrderBook get_orderbook_url()"""
    orderbook = OrderBook()
    assert coingecko_all_coins.call_count == 1
    orderbook.add("kucoin", "VAI/USDT")
    assert coingecko_vaiot_kucoin.call_count == 1
    orderbook_url = orderbook.get_orderbook_url("kucoin", "VAI/USDT")
    url = "https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol=VAIOT-USDT"
    assert orderbook_url == url


@responses.activate
def test_get_chart_url(coingecko_all_coins, coingecko_vaiot_kucoin):
    """OrderBook get_chart_url()"""
    orderbook = OrderBook()
    assert coingecko_all_coins.call_count == 1
    orderbook.add("kucoin", "VAI/USDT")
    assert coingecko_vaiot_kucoin.call_count == 1
    chart_url = orderbook.get_chart_url("kucoin", "VAI/USDT")
    hyperlink = "[VAI/USDT](https://www.kucoin.com/trade/VAIOT-USDT)"
    assert hyperlink == chart_url
