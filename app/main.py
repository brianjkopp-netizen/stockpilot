"""CLI entry point for StockPilot. Fetches stock data, computes indicators, and generates an AI signal."""

import argparse
import os
import sys
import textwrap
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from data.fetcher import get_stock_data
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary
from analysis.ai_analyst import get_signal

_DEFAULT_DAYS = 30
_MA_WINDOWS = [10, 20]
_WIDTH = 80
_LABEL_WIDTH = 16


def _row(label: str, value: str) -> str:
    return f"{label:<{_LABEL_WIDTH}}{value}"


def _reasoning_row(text: str) -> str:
    return textwrap.fill(
        text,
        width=_WIDTH,
        initial_indent=f"{'Reasoning:':<{_LABEL_WIDTH}}",
        subsequent_indent=" " * _LABEL_WIDTH,
    )


def main() -> None:
    """Parse CLI arguments, fetch stock data, compute indicators, call AI for a signal, and print results."""
    parser = argparse.ArgumentParser(
        description="StockPilot — fetch stock data, compute indicators, and generate an AI trading signal."
    )
    parser.add_argument("--ticker", default=None, help="Stock ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--days",
        type=int,
        default=_DEFAULT_DAYS,
        help=f"Number of calendar days of history to fetch (default: {_DEFAULT_DAYS})",
    )
    args = parser.parse_args()

    if not args.ticker:
        args.ticker = input("Enter ticker symbol: ").strip()

    t_start = time.perf_counter()

    try:
        df = get_stock_data(args.ticker, args.days)
        df = add_moving_averages(df, _MA_WINDOWS)
        df = add_volume_signal(df)
        summary = get_summary(df)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching AI signal for {args.ticker.upper()}...", flush=True)
    try:
        signal = get_signal(args.ticker, summary)
    except Exception as exc:
        print(f"AI signal error: {exc}", file=sys.stderr)
        sys.exit(1)

    t_end = time.perf_counter()

    ticker = args.ticker.upper()
    date_from = df.index[0].strftime("%Y-%m-%d")
    date_to = df.index[-1].strftime("%Y-%m-%d")
    sep = "=" * _WIDTH

    print(f"\n{sep}")
    print("StockPilot -- AI Signal Analysis")
    print(sep)
    print(_row("Ticker:", ticker))
    print(_row("Date Range:", f"{date_from} to {date_to}"))
    print(_row("Current Price:", f"${summary['current_price']:.2f}"))
    print(_row("MA (10-day):", f"${summary['ma_10']:.2f}"))
    print(_row("MA (20-day):", f"${summary['ma_20']:.2f}"))
    print(_row("Volume Signal:", summary["volume_signal"]))
    print()
    print("--- AI Signal ---")
    print(_row("Signal:", signal["signal"]))
    print(_row("Confidence:", signal["confidence"]))
    print(_reasoning_row(signal["reasoning"]))
    print()
    print(f"Runtime: {t_end - t_start:.1f}s")
    print(sep)
    print()


if __name__ == "__main__":
    main()
