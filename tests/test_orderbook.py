""" Tests for main OrderBook class """

import time
from unittest.mock import patch

import pytest
import responses

from topbid.orderbook import OrderBook


@pytest.fixture(name="cmp_mappings")
def fixture_cmp_mappings():
    """CryptoCompare exchange mappings sample mocked response"""
    rsp = responses.get(
        "https://min-api.cryptocompare.com/data/v2/pair/mapping/exchange?e=Kucoin",
        json={
            "Response": "Success",
            "Data": {
                "current": [
                    {
                        "exchange": "Kucoin",
                        "exchange_fsym": "VAI",
                        "exchange_tsym": "USDT",
                        "fsym": "VAIOT",
                        "last_update": 1620315177.95121,
                        "tsym": "USDT",
                    }
                ]
            },
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
def test_init(cmp_mappings):
    """OrderBook __init__()"""
    # Instantiating OrderBook calls initialize_symbols_mappings()
    orderbook = OrderBook("cmp_api_key", ["kucoin"])
    assert orderbook.symbols_mappings == {"kucoin-VAIOT/USDT": "VAI/USDT"}
    assert cmp_mappings.call_count == 1


@responses.activate
def test_get_orderbook_tops(cmp_mappings, vaiot_prices):
    """OrderBook get_orderbook_top_bid()/get_orderbook_top_ask()"""
    orderbook = OrderBook("cmp_api_key", ["kucoin"])
    assert cmp_mappings.call_count == 1

    orderbook.add("kucoin", "VAIOT/USDT")
    with patch("request_boost.boosted_requests") as boosted_mock:
        boosted_mock.return_value = vaiot_prices
        # start background update
        orderbook.start(0.1)
        time.sleep(0.2)
    assert orderbook.orderbook_bids == {"kucoin-VAIOT/USDT": ("0.197007", "1300")}
    assert orderbook.orderbook_asks == {"kucoin-VAIOT/USDT": ("0.197607", "1506.5178")}

    # get_orderbook_top_bid
    top_bid = orderbook.get_orderbook_top_bid("kucoin", "VAIOT/USDT")
    assert top_bid == ("0.197007", "1300")

    # delete
    orderbook.delete("kucoin", "VAIOT/USDT")
    assert not orderbook.orderbook_bids
    assert not orderbook.orderbook_asks

    orderbook.stop()


@responses.activate
def test_get_exchange_symbol(cmp_mappings):
    """OrderBook get_exchange_symbol()"""
    orderbook = OrderBook("cmp_api_key", ["kucoin"])
    assert cmp_mappings.call_count == 1
    exchange_symbol = orderbook.get_exchange_symbol("kucoin", "VAIOT/USDT")
    assert exchange_symbol == "VAI/USDT"


@responses.activate
def test_get_orderbook_url(cmp_mappings):
    """OrderBook get_orderbook_url()"""
    orderbook = OrderBook("cmp_api_key", ["kucoin"])
    assert cmp_mappings.call_count == 1
    orderbook_url = orderbook.get_orderbook_url("kucoin", "VAIOT/USDT")
    url = "https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol=VAI-USDT"
    assert orderbook_url == url


@responses.activate
def test_get_chart_url(cmp_mappings):
    """OrderBook get_chart_url()"""
    orderbook = OrderBook("cmp_api_key", ["kucoin"])
    assert cmp_mappings.call_count == 1
    chart_url = orderbook.get_chart_url("kucoin", "VAIOT/USDT")
    hyperlink = "[VAIOT/USDT](https://www.kucoin.com/trade/VAI-USDT)"
    assert hyperlink == chart_url
