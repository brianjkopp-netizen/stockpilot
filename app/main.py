"""CLI entry point for StockPilot. Fetches stock data, computes indicators, and generates an AI signal."""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from data.fetcher import get_stock_data
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary
from analysis.ai_analyst import get_signal

_DEFAULT_DAYS = 30
_MA_WINDOWS = [10, 20]

_SIGNAL_LABEL = {
    "BULLISH": "BULLISH  ▲",
    "BEARISH": "BEARISH  ▼",
    "NEUTRAL": "NEUTRAL  —",
}


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

    t_after_data = time.perf_counter()

    print(f"  Fetching AI signal for {args.ticker.upper()}...", flush=True)
    try:
        signal = get_signal(args.ticker, summary)
    except Exception as exc:
        print(f"AI signal error: {exc}", file=sys.stderr)
        sys.exit(1)

    t_end = time.perf_counter()

    ticker = args.ticker.upper()
    date_from = df.index[0].strftime("%Y-%m-%d")
    date_to = df.index[-1].strftime("%Y-%m-%d")
    signal_label = _SIGNAL_LABEL.get(signal["signal"], signal["signal"])

    print(f"\n{'='*50}")
    print(f"  StockPilot — {ticker}")
    print(f"{'='*50}")
    print(f"  Date range    : {date_from} to {date_to}")
    print(f"  Current price : ${summary['current_price']:.2f}")
    print(f"  MA (10-day)   : ${summary['ma_10']:.2f}  [{summary['price_vs_ma10']}]")
    print(f"  MA (20-day)   : ${summary['ma_20']:.2f}  [{summary['price_vs_ma20']}]")
    print(f"  Volume        : {summary['volume_signal']}")
    print(f"{'-'*50}")
    print(f"  AI Signal     : {signal_label}")
    print(f"  Confidence    : {signal['confidence']}")
    print(f"  Reasoning     : {signal['reasoning']}")
    if signal["key_factors"]:
        print(f"  Key factors   :")
        for factor in signal["key_factors"]:
            print(f"    • {factor}")
    print(f"{'='*50}")
    print(f"  Data: {t_after_data - t_start:.2f}s  |  AI: {t_end - t_after_data:.2f}s  |  Total: {t_end - t_start:.2f}s")
    print()


if __name__ == "__main__":
    main()
