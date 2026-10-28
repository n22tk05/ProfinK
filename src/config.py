"""
Configuration module for Data Collection Pipeline.
Based on specifications in docs/DataInfo.txt.
"""
import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
MACRO_DIR = DATA_DIR / "macro"

# Binance API
BINANCE_VISION_API = "https://data-api.binance.vision/api/v3"
BINANCE_PUBLIC_API = "https://api.binance.com/api/v3"
DEFAULT_KLINES_LIMIT = 1000

# Symbols mapping (handles typos like BTCUSTD -> BTCUSDT)
SYMBOL_ALIASES = {
    "BTCUSTD": "BTCUSDT",
    "ETHUSTD": "ETHUSDT",
    "SOLUSTD": "SOLUSDT",
    "XRPUSTD": "XRPUSDT",
    "BNBUSTD": "BNBUSDT",
    "LINKUSTD": "LINKUSDT",
    "BTC": "BTCUSDT",
    "ETH": "ETHUSDT",
    "SOL": "SOLUSDT",
    "XRP": "XRPUSDT",
    "BNB": "BNBUSDT",
    "LINK": "LINKUSDT",
}

DEFAULT_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "LINKUSDT",
]

# Supported timeframes and their millisecond duration
TIMEFRAME_MS = {
    "1m": 60_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
}

DEFAULT_TIMEFRAMES = ["1m", "15m", "1h", "4h"]

# Macro indicators tickers & proxies
MACD_DEFAULT = (12, 26, 9)
RSI_PERIOD = 14
SMA_PERIOD = 20
EMA_PERIOD = 20
BB_PERIOD = 20
BB_STD = 2.0
SWING_WINDOW = 5  # local pivot window for Sup & Rep

# 35 Canonical Data Columns specified in DataInfo.txt (ordered 0 to 34):
# 0. Symbol
# 1. Open Time
# 2. Average Price (Time Frame)
# 3. Open
# 4. High
# 5. Low
# 6. Close
# 7. Volume
# 8. Close Time
# 9. Quote asset volume
# 10. Number of trades
# 11. Taker buy base asset volume
# 12. Taker buy quote asset volume
# 13. Taker sell base asset volume
# 14. Taker sell quote asset volume
# 15. FED
# 16. Global M2
# 17. DXY
# 18. CPI
# 19. PCE
# 20. NFP
# 21. VIX
# 22. S&P 500
# 23. SMA
# 24. EMA
# 25. RSI
# 26. MACD
# 27. Signal
# 28. Hist
# 29. Bollinger Bands
# 30. Slope
# 31. isHammer
# 32. isBullEngulf
# 33. Sup
# 34. Rep
CANONICAL_COLUMNS = [
    "Symbol",
    "Open Time",
    "Average Price",
    "Open",
    "High",
    "Low",
    "Close",
    "Volume",
    "Close Time",
    "Quote asset volume",
    "Number of trades",
    "Taker buy base asset volume",
    "Taker buy quote asset volume",
    "Taker sell base asset volume",
    "Taker sell quote asset volume",
    "FED",
    "Global M2",
    "DXY",
    "CPI",
    "PCE",
    "NFP",
    "VIX",
    "S&P 500",
    "SMA",
    "EMA",
    "RSI",
    "MACD",
    "Signal",
    "Hist",
    "Bollinger Bands",
    "Slope",
    "isHammer",
    "isBullEngulf",
    "Sup",
    "Rep",
]
