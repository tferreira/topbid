# topbid

[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Helper library to fetch and store current orderbook top bid/ask price and volume from crypto exchanges APIs.
Currently supports Binance, Bybit, Gateio, Kraken, Kucoin and OKX.

Requires Python 3.8+

## Installation

```
pip install topbid
```

## Usage

```python
>>> from topbid.orderbook import OrderBook

# Instanciate OrderBook with your CMP API key and exchanges you'll be using.
# Tickers mappings will be retrieved.
>>> orderbook = OrderBook("cryptocompare-api-key", ["binance", "kucoin"])
2023-01-01 13:37:00,000 - topbid_orderbook - INFO - Saved mappings from CryptoCompare API for exchange binance
2023-01-01 13:37:00,000 - topbid_orderbook - INFO - Saved mappings from CryptoCompare API for exchange kucoin

# Add one or more market pairs to be fetched from an exchange REST API.
>>> orderbook.add("binance", "BTC/USDT")
>>> orderbook.add("kucoin", ["BTC/USDT", "ETH/USDT"])

# Start the background thread fetching prices and volume (here, every 2 seconds).
>>> orderbook.start(update_every=2)

# Retrieve the highest bid on the orderbook.
>>> orderbook.get_orderbook_top_bid("binance", "BTC/USDT")
(23130.41, 0.0584)

# Retrieve the lowest ask on the orderbook.
>>> orderbook.get_orderbook_top_ask("binance", "BTC/USDT")
(23130.43, 0.0214)

# Removes a pair from being fetched.
>>> orderbook.delete("binance", "BTC/USDT")

# Stop the background thread and removes all watched pairs.
# It must be called before exiting your own application.
>>> orderbook.stop()
```
