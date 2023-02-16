# topbid

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Helper library to fetch and store current best bid from crypto exchanges APIs.
Currently supports Binance, Gateio, Kraken and Kucoin.

Requires Python 3.8+

## Installation

```
pip install topbid
```

## Usage

```python
>>> from topbid.orderbook import OrderBook

>>> orderbook = OrderBook("cryptocompare-api-key", ["binance", "kucoin"])
2023-01-01 13:37:00,000 - topbid_orderbook - INFO - Saved mappings from CryptoCompare API for exchange binance
2023-01-01 13:37:00,000 - topbid_orderbook - INFO - Saved mappings from CryptoCompare API for exchange kucoin

>>> orderbook.add("binance", "BTC/USDT")

>>> orderbook.start(update_every=2)

>>> orderbook.get_orderbook_top_bid("binance", "BTC/USDT")
(23130.41, 0.05)

>>> orderbook.delete("binance", "BTC/USDT")

>>> orderbook.stop()
```

## Build

```
python -m build
```
