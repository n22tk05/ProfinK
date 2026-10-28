"""
Technical Indicators & Price Action Patterns.
Calculates SMA, EMA, RSI, MACD, Bollinger Bands, Slope, Candlestick patterns, and Support/Resistance.
"""
import numpy as np
import pandas as pd

from src.config import (
    SMA_PERIOD,
    EMA_PERIOD,
    RSI_PERIOD,
    MACD_DEFAULT,
    BB_PERIOD,
    BB_STD,
    SWING_WINDOW,
)


def compute_sma(series: pd.Series, period: int = SMA_PERIOD) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=1).mean()


def compute_ema(series: pd.Series, period: int = EMA_PERIOD) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Relative Strength Index with Wilder's Smoothing."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing equivalent to alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    # Handle zero loss (RSI = 100) or zero gain (RSI = 0)
    rsi = rsi.fillna(50.0)
    return rsi


def compute_macd(
    series: pd.Series,
    fast: int = MACD_DEFAULT[0],
    slow: int = MACD_DEFAULT[1],
    signal_period: int = MACD_DEFAULT[2],
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD Line, Signal Line, and Histogram (Hist = MACD - Signal)."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
    hist = macd_line - signal_line
    return macd_line, signal_line, hist


def compute_bollinger_bands(
    series: pd.Series,
    period: int = BB_PERIOD,
    num_std: float = BB_STD,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Computes Bollinger Bands:
    Returns (Upper, Middle, Lower, Percent_B).
    Percent_B = (Price - Lower) / (Upper - Lower).
    """
    middle = series.rolling(window=period, min_periods=1).mean()
    std = series.rolling(window=period, min_periods=1).std().fillna(0.0)
    upper = middle + (num_std * std)
    lower = middle - (num_std * std)

    bandwidth = upper - lower
    percent_b = (series - lower) / bandwidth.replace(0, np.nan)
    percent_b = percent_b.fillna(0.5)

    return upper, middle, lower, percent_b


def compute_slope(series: pd.Series, window: int = 5) -> pd.Series:
    """
    Computes rolling linear regression slope of price over `window` bars.
    Slope = Cov(x, y) / Var(x).
    """
    x = np.arange(window)
    x_mean = x.mean()
    x_var = ((x - x_mean) ** 2).sum()

    def calc_slope(y_vals):
        if len(y_vals) < window:
            return 0.0
        y_mean = np.mean(y_vals)
        cov = np.sum((x - x_mean) * (y_vals - y_mean))
        return cov / x_var

    return series.rolling(window=window, min_periods=window).apply(calc_slope, raw=True).fillna(0.0)


def detect_hammer(
    open_p: pd.Series,
    high_p: pd.Series,
    low_p: pd.Series,
    close_p: pd.Series,
) -> pd.Series:
    """
    Detect Hammer candlestick pattern (True/False):
    - Small body at the upper end of the candle.
    - Long lower shadow at least 2x the body size.
    - Little to no upper shadow.
    """
    body = (close_p - open_p).abs()
    candle_range = high_p - low_p
    lower_shadow = np.minimum(open_p, close_p) - low_p
    upper_shadow = high_p - np.maximum(open_p, close_p)

    cond_range = candle_range > 0
    cond_lower = lower_shadow >= (2.0 * body)
    cond_upper = upper_shadow <= (0.2 * candle_range)
    cond_body = body >= (0.05 * candle_range)

    is_hammer = cond_range & cond_lower & cond_upper & cond_body
    return is_hammer.astype(bool)


def detect_bullish_engulfing(
    open_p: pd.Series,
    close_p: pd.Series,
) -> pd.Series:
    """
    Detect Bullish Engulfing pattern (True/False):
    - Prior candle is bearish (Close[t-1] < Open[t-1]).
    - Current candle is bullish (Close[t] > Open[t]).
    - Current candle body engulfs prior candle body.
    """
    prev_open = open_p.shift(1)
    prev_close = close_p.shift(1)

    prev_bearish = prev_close < prev_open
    curr_bullish = close_p > open_p

    engulfs_top = close_p >= prev_open
    engulfs_bottom = open_p <= prev_close

    is_bull_engulf = prev_bearish & curr_bullish & engulfs_top & engulfs_bottom
    return is_bull_engulf.fillna(False).astype(bool)


def compute_support_resistance(
    high_p: pd.Series,
    low_p: pd.Series,
    window: int = SWING_WINDOW,
) -> tuple[pd.Series, pd.Series]:
    """
    Local Support (Sup - Swing Lows) & Local Resistance (Rep - Swing Highs).
    Uses a centered pivot window, then forward-fills the latest confirmed support/resistance price.
    """
    n = len(high_p)
    sup_points = pd.Series(np.nan, index=low_p.index, dtype="float64")
    rep_points = pd.Series(np.nan, index=high_p.index, dtype="float64")

    # A bar at index i is a pivot low if it's the lowest within [i-window, i+window]
    low_vals = low_p.values
    high_vals = high_p.values

    for i in range(window, n - window):
        # Local min (Support)
        if low_vals[i] == np.min(low_vals[i - window : i + window + 1]):
            sup_points.iloc[i + window] = low_vals[i]  # Available after confirmation window

        # Local max (Resistance)
        if high_vals[i] == np.max(high_vals[i - window : i + window + 1]):
            rep_points.iloc[i + window] = high_vals[i]  # Available after confirmation window

    # Forward fill latest confirmed support & resistance, and backward fill initial rows
    sup_series = sup_points.ffill().bfill()
    rep_series = rep_points.ffill().bfill()

    # Fallback to rolling min/max if still NaN (for very small datasets)
    if sup_series.isna().any():
        sup_series = low_p.rolling(window=window * 2, min_periods=1).min()
    if rep_series.isna().any():
        rep_series = high_p.rolling(window=window * 2, min_periods=1).max()

    return sup_series, rep_series


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates and appends all technical indicators (items 23-34) to DataFrame."""
    if df.empty:
        return df

    out = df.copy()

    # 23. SMA
    out["SMA"] = compute_sma(out["Close"], period=SMA_PERIOD)

    # 24. EMA
    out["EMA"] = compute_ema(out["Close"], period=EMA_PERIOD)

    # 25. RSI
    out["RSI"] = compute_rsi(out["Close"], period=RSI_PERIOD)

    # 26. MACD, 27. Signal, 28. Hist
    macd, signal, hist = compute_macd(out["Close"])
    out["MACD"] = macd
    out["Signal"] = signal
    out["Hist"] = hist

    # 29. Bollinger Bands (Percent_B)
    _, _, _, percent_b = compute_bollinger_bands(out["Close"], period=BB_PERIOD, num_std=BB_STD)
    out["Bollinger Bands"] = percent_b

    # 30. Slope
    out["Slope"] = compute_slope(out["Close"], window=5)

    # 31. isHammer
    out["isHammer"] = detect_hammer(out["Open"], out["High"], out["Low"], out["Close"])

    # 32. isBullEngulf
    out["isBullEngulf"] = detect_bullish_engulfing(out["Open"], out["Close"])

    # 33. Sup, 34. Rep
    sup, rep = compute_support_resistance(out["High"], out["Low"], window=SWING_WINDOW)
    out["Sup"] = sup
    out["Rep"] = rep

    return out
