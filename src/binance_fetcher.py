"""
Binance Historical Klines Fetcher.
Fetches OHLCV and trade volume data using Binance Vision API with automatic fallback.
"""
import time
import logging
from typing import Optional, List
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import (
    BINANCE_VISION_API,
    BINANCE_PUBLIC_API,
    DEFAULT_KLINES_LIMIT,
    TIMEFRAME_MS,
    SYMBOL_ALIASES,
)

logger = logging.getLogger(__name__)


class BinanceFetcher:
    """Fetches historical market data from Binance."""

    def __init__(
        self,
        base_url: str = BINANCE_VISION_API,
        fallback_url: str = BINANCE_PUBLIC_API,
        request_delay: float = 0.05,
    ):
        self.base_url = base_url.rstrip("/")
        self.fallback_url = fallback_url.rstrip("/")
        self.request_delay = request_delay

        self.session = requests.Session()
        retries = Retry(
            total=5,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """Resolve aliases and ensure uppercase symbol."""
        cleaned = symbol.strip().upper()
        return SYMBOL_ALIASES.get(cleaned, cleaned)

    def _fetch_klines_batch(
        self,
        symbol: str,
        interval: str,
        start_time: int,
        end_time: int,
        limit: int = DEFAULT_KLINES_LIMIT,
    ) -> List[list]:
        """Fetch a single batch of klines."""
        params = {
            "symbol": symbol,
            "interval": interval,
            "startTime": start_time,
            "endTime": end_time,
            "limit": limit,
        }

        # Try base_url first, fallback to fallback_url
        urls = [f"{self.base_url}/klines", f"{self.fallback_url}/klines"]
        last_error = None

        for url in urls:
            try:
                resp = self.session.get(url, params=params, timeout=15)
                if resp.status_code == 200:
                    return resp.json()
                elif resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 2))
                    logger.warning("Rate limit 429 hit. Waiting %d seconds...", retry_after)
                    time.sleep(retry_after)
                else:
                    logger.warning("Binance API %s returned status %d: %s", url, resp.status_code, resp.text[:100])
            except Exception as exc:
                last_error = exc
                logger.warning("Error requesting %s: %s", url, exc)

        if last_error:
            raise RuntimeError(f"Failed to fetch klines from all endpoints: {last_error}")
        return []

    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        progress_callback: Optional[callable] = None,
    ) -> pd.DataFrame:
        """
        Fetch continuous klines from start_time_ms to end_time_ms.
        Paginates in chunks of 1000 klines.
        """
        symbol = self.normalize_symbol(symbol)
        tf_ms = TIMEFRAME_MS.get(interval)
        if not tf_ms:
            raise ValueError(f"Unsupported timeframe: {interval}. Expected one of {list(TIMEFRAME_MS.keys())}")

        all_klines: List[list] = []
        current_start = start_time_ms
        total_expected = max(1, (end_time_ms - start_time_ms) // tf_ms)

        logger.info(
            "Fetching %s (%s) from %d to %d (~%d bars)",
            symbol, interval, start_time_ms, end_time_ms, total_expected
        )

        while current_start < end_time_ms:
            batch = self._fetch_klines_batch(
                symbol=symbol,
                interval=interval,
                start_time=current_start,
                end_time=end_time_ms,
                limit=DEFAULT_KLINES_LIMIT,
            )

            if not batch:
                break

            all_klines.extend(batch)
            last_open_time = batch[-1][0]

            if progress_callback:
                progress_callback(len(all_klines), total_expected)

            # Move start to next expected candle
            next_start = last_open_time + tf_ms
            if next_start <= current_start:
                # Avoid infinite loop if timestamp didn't advance
                current_start += tf_ms
            else:
                current_start = next_start
                logger.info(
                    "Fetching Success %s (%s) from %d to %d (~%d bars)",
                    symbol, interval, start_time_ms, end_time_ms, total_expected
                )

            if len(batch) < DEFAULT_KLINES_LIMIT:
                # Reached latest available data
                break

            if self.request_delay > 0:
                time.sleep(self.request_delay)

        if not all_klines:
            logger.warning("No data retrieved for %s %s", symbol, interval)
            return pd.DataFrame()

        # Build DataFrame with canonical raw schema
        df = pd.DataFrame(
            all_klines,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )

        # Drop duplicate timestamps if any
        df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)

        # Type conversion
        int_cols = ["open_time", "close_time", "number_of_trades"]
        for col in int_cols:
            df[col] = df[col].astype("int64")

        float_cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
        ]
        for col in float_cols:
            df[col] = df[col].astype("float64")

        # Map to Canonical names & compute volume balance
        df["Symbol"] = symbol
        df["Open Time"] = df["open_time"]
        df["Open"] = df["open"]
        df["High"] = df["high"]
        df["Low"] = df["low"]
        df["Close"] = df["close"]
        df["Volume"] = df["volume"]
        df["Close Time"] = df["close_time"]
        df["Quote asset volume"] = df["quote_asset_volume"]
        df["Number of trades"] = df["number_of_trades"]
        df["Taker buy base asset volume"] = df["taker_buy_base_asset_volume"]
        df["Taker buy quote asset volume"] = df["taker_buy_quote_asset_volume"]

        # Calculation rules from DataInfo.txt:
        # 13. Taker sell base asset volume = Volume - Taker buy base asset volume
        df["Taker sell base asset volume"] = df["Volume"] - df["Taker buy base asset volume"]

        # 14. Taker sell quote asset volume = Quote asset volume - Taker buy quote asset volume
        df["Taker sell quote asset volume"] = df["Quote asset volume"] - df["Taker buy quote asset volume"]

        # 2. Average Price: VWAP if volume > 0, else (Open + High + Low + Close) / 4
        ohlc4 = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4.0
        vwap = df["Quote asset volume"] / df["Volume"]
        df["Average Price"] = vwap.where(df["Volume"] > 0, ohlc4)

        keep_cols = [
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
        ]
        return df[keep_cols]
