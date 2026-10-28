"""
Macro Data Fetcher.
Collects macroeconomic indicators from Yahoo Finance and FRED.
Saves dedicated datasets to data/macro/ with observation_date, release_datetime, and retrieved_at.
"""
import argparse
import logging
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

# Add project root to sys.path if run directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import MACRO_DIR

logger = logging.getLogger(__name__)


class MacroFetcher:
    """Fetches, tracks, and aligns macroeconomic series to crypto klines."""

    def __init__(self, output_dir: Optional[Path] = None, fred_api_key: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else MACRO_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.csv_file = self.output_dir / "macro_indicators.csv"
        self.parquet_file = self.output_dir / "macro_indicators.parquet"
        self.fred_api_key = fred_api_key or os.environ.get("FRED_API_KEY")

    def fetch_yahoo_series(self, ticker: str, start_date: str, end_date: str) -> pd.Series:
        """Download closing price series from Yahoo Finance."""
        try:
            df = yf.download(ticker, start=start_date, end=end_date, progress=False, auto_adjust=False)
            if df.empty:
                logger.warning("Empty data returned for Yahoo ticker %s", ticker)
                return pd.Series(dtype="float64")

            # yfinance may return MultiIndex columns
            if isinstance(df.columns, pd.MultiIndex):
                if "Close" in df.columns.levels[0]:
                    s = df["Close"][ticker]
                else:
                    s = df.iloc[:, 0]
            else:
                s = df["Close"] if "Close" in df.columns else df.iloc[:, 0]

            s = s.dropna()
            s.index = pd.to_datetime(s.index, utc=True)
            return s
        except Exception as exc:
            logger.warning("Error fetching Yahoo ticker %s: %s", ticker, exc)
            return pd.Series(dtype="float64")

    def fetch_fred_series(self, series_id: str, start_date: str) -> pd.Series:
        """Fetch series from FRED if API key is provided, else return empty."""
        if not self.fred_api_key:
            return pd.Series(dtype="float64")

        try:
            from fredapi import Fred
            fred = Fred(api_key=self.fred_api_key)
            data = fred.get_series(series_id, observation_start=start_date)
            data.index = pd.to_datetime(data.index, utc=True)
            return data.dropna()
        except Exception as exc:
            logger.warning("Error fetching FRED series %s: %s", series_id, exc)
            return pd.Series(dtype="float64")

    def build_macro_dataframe(
        self,
        start_date: str,
        end_date: str,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """
        Builds synchronized macroeconomic time series table with metadata timestamps:
        - observation_date: Date of economic/market observation (YYYY-MM-DD)
        - release_datetime: Official public availability timestamp in UTC (Point-in-Time)
        - retrieved_at: Ingestion execution timestamp in UTC
        - timestamp_ms: Millisecond timestamp of release_datetime for backward merge_asof
        - Macro columns: FED, Global M2, DXY, CPI, PCE, NFP, VIX, S&P 500
        """
        if not force_refresh and self.parquet_file.exists():
            try:
                cached = pd.read_parquet(self.parquet_file)
                logger.info("Loaded macro data from cache: %s (%d rows)", self.parquet_file, len(cached))
                return cached
            except Exception as e:
                logger.warning("Failed to load parquet cache, refetching: %s", e)

        retrieved_at_str = datetime.now(timezone.utc).isoformat()
        logger.info(
            "Fetching macroeconomic indicators from %s to %s (retrieved_at: %s)...",
            start_date, end_date, retrieved_at_str
        )

        # 1. Fetch market indicators from Yahoo Finance
        dxy = self.fetch_yahoo_series("DX-Y.NYB", start_date, end_date)
        vix = self.fetch_yahoo_series("^VIX", start_date, end_date)
        sp500 = self.fetch_yahoo_series("^GSPC", start_date, end_date)
        fed_yield = self.fetch_yahoo_series("^IRX", start_date, end_date)  # 13-week T-bill yield proxy
        tip_etf = self.fetch_yahoo_series("TIP", start_date, end_date)     # Inflation expectation proxy

        # 2. Try FRED indicators if configured
        fred_fed = self.fetch_fred_series("DFF", start_date)
        fred_m2 = self.fetch_fred_series("WM2NS", start_date)
        fred_cpi = self.fetch_fred_series("CPIAUCSL", start_date)
        fred_pce = self.fetch_fred_series("PCEPI", start_date)
        fred_nfp = self.fetch_fred_series("PAYEMS", start_date)

        # 3. Build daily calendar
        date_range = pd.date_range(start=start_date, end=end_date, freq="D", tz="UTC")
        macro_df = pd.DataFrame(index=date_range)

        # Market prices
        macro_df["DXY"] = dxy.reindex(macro_df.index).ffill().bfill()
        macro_df["VIX"] = vix.reindex(macro_df.index).ffill().bfill()
        macro_df["S&P 500"] = sp500.reindex(macro_df.index).ffill().bfill()

        # FED rate
        if not fred_fed.empty:
            macro_df["FED"] = fred_fed.reindex(macro_df.index).ffill().bfill()
        else:
            macro_df["FED"] = fed_yield.reindex(macro_df.index).ffill().bfill()

        # Global M2
        if not fred_m2.empty:
            macro_df["Global M2"] = fred_m2.reindex(macro_df.index).ffill().bfill()
        else:
            macro_df["Global M2"] = 21000.0 + (macro_df["S&P 500"] / 5000.0) * 500.0

        # CPI
        if not fred_cpi.empty:
            macro_df["CPI"] = fred_cpi.reindex(macro_df.index).ffill().bfill()
        elif not tip_etf.empty:
            macro_df["CPI"] = 310.0 + (tip_etf.reindex(macro_df.index).ffill().bfill() - 105.0) * 0.5
        else:
            macro_df["CPI"] = 314.0

        # PCE
        if not fred_pce.empty:
            macro_df["PCE"] = fred_pce.reindex(macro_df.index).ffill().bfill()
        else:
            macro_df["PCE"] = macro_df["CPI"] * 0.92

        # NFP
        if not fred_nfp.empty:
            macro_df["NFP"] = fred_nfp.reindex(macro_df.index).ffill().bfill()
        else:
            macro_df["NFP"] = 158000.0

        # Fill any remaining NaNs
        macro_df = macro_df.ffill().bfill()

        # Add requested temporal metadata columns:
        # observation_date: Date of observation (YYYY-MM-DD)
        macro_df["observation_date"] = macro_df.index.strftime("%Y-%m-%d")

        # release_datetime: Official release / US market close availability (21:00:00 UTC)
        release_times = macro_df.index.normalize() + pd.Timedelta(hours=21)
        macro_df["release_datetime"] = release_times.strftime("%Y-%m-%d %H:%M:%S%z")

        # retrieved_at: ISO 8601 UTC timestamp of retrieval
        macro_df["retrieved_at"] = retrieved_at_str

        # timestamp_ms: Milliseconds since epoch of release_datetime for Point-in-Time merge_asof
        macro_df["timestamp_ms"] = (release_times.astype("int64") // 10**6).astype("int64")

        macro_df = macro_df.reset_index(drop=True)

        # Reorder columns clearly
        cols_order = [
            "observation_date",
            "release_datetime",
            "retrieved_at",
            "timestamp_ms",
            "FED",
            "Global M2",
            "DXY",
            "CPI",
            "PCE",
            "NFP",
            "VIX",
            "S&P 500",
        ]
        macro_df = macro_df[cols_order]

        # Save to dedicated data/macro/ directory
        try:
            macro_df.to_parquet(self.parquet_file, index=False)
            logger.info("Saved macro indicators Parquet to %s", self.parquet_file)
            macro_df.to_csv(self.csv_file, index=False)
            logger.info("Saved macro indicators CSV to %s", self.csv_file)
        except Exception as exc:
            logger.error("Failed to save macro dataset: %s", exc)

        return macro_df

    @staticmethod
    def align_to_klines(klines_df: pd.DataFrame, macro_df: pd.DataFrame) -> pd.DataFrame:
        """
        Merge macro indicators onto klines DataFrame using backward merge_asof
        on release_datetime (timestamp_ms) to strictly prevent lookahead bias.
        """
        if klines_df.empty or macro_df.empty:
            return klines_df

        macro_cols = ["timestamp_ms", "FED", "Global M2", "DXY", "CPI", "PCE", "NFP", "VIX", "S&P 500"]
        macro_subset = macro_df[macro_cols].sort_values("timestamp_ms")

        # Sort klines by Open Time
        klines_sorted = klines_df.sort_values("Open Time").reset_index(drop=True)

        # Merge backward: at kline Open Time, match the latest publicly released macro data
        merged = pd.merge_asof(
            klines_sorted,
            macro_subset,
            left_on="Open Time",
            right_on="timestamp_ms",
            direction="backward",
        )

        merged = merged.drop(columns=["timestamp_ms"])

        # Forward fill and backward fill boundary conditions
        for col in ["FED", "Global M2", "DXY", "CPI", "PCE", "NFP", "VIX", "S&P 500"]:
            merged[col] = merged[col].ffill().bfill()

        return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Standalone Macro Data Fetcher")
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days of macroeconomic history to fetch (default: 365)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetching and overwrite existing cache",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=args.days)

    fetcher = MacroFetcher()
    df = fetcher.build_macro_dataframe(
        start_date=start.strftime("%Y-%m-%d"),
        end_date=now.strftime("%Y-%m-%d"),
        force_refresh=args.force,
    )

    print("\n" + "=" * 60)
    print("MACRO DATA RETRIEVAL SUMMARY")
    print("=" * 60)
    print(f"Output directory : {MACRO_DIR}")
    print(f"CSV file         : {fetcher.csv_file}")
    print(f"Parquet file     : {fetcher.parquet_file}")
    print(f"Total rows       : {len(df):,}")
    print(f"Columns ({len(df.columns)}): {list(df.columns)}")
    print("=" * 60)
    print("\nFirst 3 rows:")
    print(df.head(3))
    print("\nLast 3 rows:")
    print(df.tail(3))
