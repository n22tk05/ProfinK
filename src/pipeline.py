"""
Main Pipeline Coordinator.
Orchestrates Binance data fetching, Macro alignment, Indicator computation, and Data validation.
"""
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src.config import (
    DATA_DIR,
    MACRO_DIR,
    DEFAULT_SYMBOLS,
    DEFAULT_TIMEFRAMES,
    CANONICAL_COLUMNS,
    TIMEFRAME_MS,
)
from src.binance_fetcher import BinanceFetcher
from src.macro_fetcher import MacroFetcher
from src.indicators import add_all_indicators

logger = logging.getLogger(__name__)


class DataPipeline:
    """End-to-end data collection and enrichment pipeline."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        fred_api_key: Optional[str] = None,
        request_delay: float = 0.05,
    ):
        self.output_dir = Path(output_dir) if output_dir else DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.binance_fetcher = BinanceFetcher(request_delay=request_delay)
        self.macro_fetcher = MacroFetcher(output_dir=MACRO_DIR, fred_api_key=fred_api_key)

    def run_single(
        self,
        symbol: str,
        interval: str,
        start_time_ms: int,
        end_time_ms: int,
        macro_df: pd.DataFrame,
        save_csv: bool = True,
        save_parquet: bool = True,
    ) -> pd.DataFrame:
        """Process a single symbol and timeframe pair."""
        norm_symbol = self.binance_fetcher.normalize_symbol(symbol)
        logger.info("=== Processing %s | %s ===", norm_symbol, interval)

        # 1. Fetch Binance klines
        klines = self.binance_fetcher.fetch_klines(
            symbol=norm_symbol,
            interval=interval,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )

        if klines.empty:
            logger.warning("Empty klines for %s %s, skipping.", norm_symbol, interval)
            return pd.DataFrame()

        # 2. Align Macro Indicators
        with_macro = self.macro_fetcher.align_to_klines(klines, macro_df)

        # 3. Compute Technical Indicators and Price Action
        enriched = add_all_indicators(with_macro)

        # 4. Enforce Canonical Columns ordering
        final_df = enriched[CANONICAL_COLUMNS].copy()

        # 5. Save outputs to data/<timeframe>/
        tf_dir = self.output_dir / interval
        tf_dir.mkdir(parents=True, exist_ok=True)

        base_filename = f"{norm_symbol}_{interval}"

        if save_csv:
            csv_path = tf_dir / f"{base_filename}.csv"
            final_df.to_csv(csv_path, index=False)
            logger.info("Saved CSV: %s (%d rows)", csv_path, len(final_df))

        if save_parquet:
            parquet_path = tf_dir / f"{base_filename}.parquet"
            final_df.to_parquet(parquet_path, index=False)
            logger.info("Saved Parquet: %s", parquet_path)

        return final_df

    def run(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        days: int = 365,
        save_csv: bool = True,
        save_parquet: bool = True,
        force_macro_refresh: bool = False,
    ) -> dict[str, int]:
        """
        Execute full pipeline over all requested symbols and timeframes.
        Returns dictionary of {f"{symbol}_{tf}": row_count}.
        """
        symbols = symbols or DEFAULT_SYMBOLS
        timeframes = timeframes or DEFAULT_TIMEFRAMES

        # Time range: 1 year ago to Now (UTC)
        now_dt = datetime.now(timezone.utc)
        start_dt = now_dt - timedelta(days=days)

        start_time_ms = int(start_dt.timestamp() * 1000)
        end_time_ms = int(now_dt.timestamp() * 1000)

        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = now_dt.strftime("%Y-%m-%d")

        logger.info(
            "Starting Pipeline | Symbols: %s | Timeframes: %s | Range: %s to %s (%d days)",
            symbols, timeframes, start_str, end_str, days
        )

        # Step 1: Prepare Macro DataFrame once
        macro_df = self.macro_fetcher.build_macro_dataframe(
            start_date=start_str,
            end_date=end_str,
            force_refresh=force_macro_refresh,
        )

        results = {}
        # Step 2: Iterate and process
        for tf in timeframes:
            for sym in symbols:
                try:
                    df = self.run_single(
                        symbol=sym,
                        interval=tf,
                        start_time_ms=start_time_ms,
                        end_time_ms=end_time_ms,
                        macro_df=macro_df,
                        save_csv=save_csv,
                        save_parquet=save_parquet,
                    )
                    results[f"{sym}_{tf}"] = len(df)
                except Exception as exc:
                    logger.error("Failed processing %s %s: %s", sym, tf, exc, exc_info=True)
                    results[f"{sym}_{tf}"] = 0

        logger.info("Pipeline completed. Summary: %s", results)
        return results
