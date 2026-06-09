"""CLI entry point for StockPilot. Fetches stock data and prints a technical summary."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.fetcher import get_stock_data
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="StockPilot — fetch stock data and print a technical summary."
    )
    parser.add_argument("--ticker", default=None, help="Stock ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of calendar days of history to fetch (default: 30)",
    )
    args = parser.parse_args()

    if not args.ticker:
        args.ticker = input("Enter ticker symbol: ").strip()

    try:
        df = get_stock_data(args.ticker, args.days)
        df = add_moving_averages(df, [10, 20])
        df = add_volume_signal(df)
        summary = get_summary(df)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)

    ticker = args.ticker.upper()
    print(f"\n{'='*40}")
    print(f"  StockPilot Summary — {ticker}")
    print(f"{'='*40}")
    print(f"  Current price : ${summary['current_price']:.2f}")
    print(f"  MA (10-day)   : ${summary['ma_10']:.2f}  [{summary['price_vs_ma10']}]")
    print(f"  MA (20-day)   : ${summary['ma_20']:.2f}  [{summary['price_vs_ma20']}]")
    print(f"  Volume        : {summary['volume_signal']}")
    print(f"{'='*40}\n")


if __name__ == "__main__":
    main()
