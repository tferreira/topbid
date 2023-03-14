""" Tests for main OrderBook class """

import time
from unittest.mock import patch

import pytest
import responses

from topbid.orderbook import OrderBook


@pytest.fixture(name="vai_prices")
def fixture_vai_prices():
    """Kucoin VAI/USDT sample mocked orderbook"""
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


def test_init():
    """OrderBook __init__()"""
    orderbook = OrderBook()
    assert not orderbook.orderbook_bids
    assert not orderbook.orderbook_asks
    assert orderbook.thread is None
    assert orderbook.running is False


@responses.activate
def test_get_orderbook_tops(vai_prices):
    """OrderBook get_orderbook_top_bid()/get_orderbook_top_ask()"""
    orderbook = OrderBook()
    orderbook.add("kucoin", "VAI/USDT")

    with patch("request_boost.boosted_requests") as boosted_mock:
        boosted_mock.return_value = vai_prices
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
def test_get_orderbook_url():
    """OrderBook get_orderbook_url()"""
    orderbook = OrderBook()
    orderbook.add("kucoin", "VAI/USDT")
    orderbook_url = orderbook.get_orderbook_url("kucoin", "VAI/USDT")
    url = "https://api.kucoin.com/api/v1/market/orderbook/level2_20?symbol=VAI-USDT"
    assert orderbook_url == url


@responses.activate
def test_get_chart_url():
    """OrderBook get_chart_url()"""
    orderbook = OrderBook()
    orderbook.add("kucoin", "VAI/USDT")
    chart_url = orderbook.get_chart_url("kucoin", "VAI/USDT")
    hyperlink = "[VAI/USDT](https://www.kucoin.com/trade/VAI-USDT)"
    assert hyperlink == chart_url
