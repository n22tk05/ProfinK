"""
Data Collection Pipeline CLI.
Entry point for historical data harvesting based on docs/DataInfo.txt.
"""
import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAMES, DATA_DIR, CANONICAL_COLUMNS
from src.pipeline import DataPipeline


def setup_logging(verbose: bool = False):
    """Configure structured logging."""
    level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=log_format, datefmt="%Y-%m-%d %H:%M:%S")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Crypto Historical Data Pipeline (Binance + Macro + Technical Indicators)"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default=",".join(DEFAULT_SYMBOLS),
        help=f"Comma-separated list of symbols (default: {','.join(DEFAULT_SYMBOLS)}) or 'all'",
    )
    parser.add_argument(
        "--timeframes",
        type=str,
        default=",".join(DEFAULT_TIMEFRAMES),
        help=f"Comma-separated list of timeframes (default: {','.join(DEFAULT_TIMEFRAMES)}) or 'all'",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Number of days of historical data to collect (default: 365 = 1 year)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.05,
        help="Request delay in seconds between Binance pagination requests (default: 0.05)",
    )
    parser.add_argument(
        "--no-csv",
        action="store_true",
        help="Do not save CSV files (saves disk space for 1m timeframe)",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Do not save Parquet files",
    )
    parser.add_argument(
        "--refresh-macro",
        action="store_true",
        help="Force re-downloading macroeconomic data instead of using cache",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a quick smoke test (BTCUSDT, 1h, 7 days)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging(args.verbose)

    if args.test:
        symbols = ["BTCUSDT"]
        timeframes = ["1h"]
        days = 7
        print("=== RUNNING IN TEST MODE (BTCUSDT, 1h, 7 days) ===")
    else:
        if args.symbols.strip().lower() == "all":
            symbols = DEFAULT_SYMBOLS
        else:
            symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

        if args.timeframes.strip().lower() == "all":
            timeframes = DEFAULT_TIMEFRAMES
        else:
            timeframes = [t.strip().lower() for t in args.timeframes.split(",") if t.strip()]
        days = args.days

    pipeline = DataPipeline(
        output_dir=DATA_DIR,
        request_delay=args.delay,
    )

    start_time = time.time()
    results = pipeline.run(
        symbols=symbols,
        timeframes=timeframes,
        days=days,
        save_csv=not args.no_csv,
        save_parquet=not args.no_parquet,
        force_macro_refresh=args.refresh_macro,
    )
    elapsed = time.time() - start_time

    # Print summary
    print("\n" + "=" * 60)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Total time: {elapsed:.2f} seconds")
    print(f"Output directory: {DATA_DIR}")
    print(f"Canonical Columns ({len(CANONICAL_COLUMNS)} items):")
    print(" -> " + ", ".join(CANONICAL_COLUMNS[:10]) + ", ...")
    print("-" * 60)
    for key, count in results.items():
        status = f"{count:,} rows" if count > 0 else "FAILED"
        print(f"  * {key:20s}: {status}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
