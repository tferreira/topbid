# topbid
Helper library to store current best bid from crypto exchanges APIs

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

>>> orderbook.update("binance", ["BTC/USDT"])

>>> o.get_orderbook_bid_by_trade({"pair": "BTC/USDT", "exchange": "binance"})
(23130.41, 0.05)
```

## Build

```
python -m build
```
