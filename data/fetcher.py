"""Fetches OHLCV stock data from yfinance for the StockPilot analysis pipeline."""

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFTickerMissingError

# yfinance's default config (hide_exceptions=True) swallows internal errors —
# a network failure, a rate limit, a malformed provider response — and
# returns an empty DataFrame instead of raising. That empty frame is
# byte-for-byte identical to what a genuinely invalid ticker returns, which is
# the root cause of the bug this module works around: an outage looks like an
# invalid ticker. Disabling it makes yfinance raise real exceptions instead,
# so failure type can be told apart from "the ticker doesn't exist."
# Process-wide and set once at import time (not toggled per call) since it's
# a shared global on the yfinance module — flipping it per-request would race
# against concurrent requests handled on other threads.
yf.config.debug.hide_exceptions = False


def get_stock_data(ticker: str, days: int) -> pd.DataFrame:
    """Fetch recent OHLCV data for a stock ticker.

    Args:
        ticker: Stock ticker symbol, e.g. "AAPL".
        days: Number of calendar days of history to fetch.

    Returns:
        A pandas DataFrame of daily Open, High, Low, Close, and Volume
        data, indexed by date, ordered oldest to newest.

    Raises:
        ValueError: If ticker is empty, days is not positive, or the
            provider affirmatively reports the ticker has no data (e.g. an
            invalid or delisted symbol).
        ConnectionError: If the data could not be fetched for any other
            reason — network failure, timeout, or the provider rate-limiting
            or erroring out. These are outages, not invalid tickers.
    """
    if not ticker or not ticker.strip():
        raise ValueError("Ticker must be a non-empty string.")
    if days <= 0:
        raise ValueError(f"Days must be a positive integer, got {days}.")

    try:
        data = yf.Ticker(ticker.strip().upper()).history(period=f"{days}d")
    except YFTickerMissingError:
        raise ValueError(f"No data found for ticker '{ticker}'. It may be invalid.")
    except Exception as exc:
        raise ConnectionError(
            f"Failed to fetch data for ticker '{ticker}': {exc}"
        ) from exc

    if data.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. It may be invalid.")

    return data[["Open", "High", "Low", "Close", "Volume"]]


def get_company_name(ticker: str) -> str:
    """Fetch the company's long name for a ticker symbol from yfinance.

    Args:
        ticker: Stock ticker symbol (e.g. "AAPL").

    Returns:
        The longName if available, shortName as fallback, or the uppercased ticker
        if yfinance returns no info or the network call fails.
    """
    try:
        info = yf.Ticker(ticker.strip().upper()).info
        return info.get("longName") or info.get("shortName") or ticker.upper()
    except Exception:
        return ticker.upper()


if __name__ == "__main__":
    print(get_stock_data("AAPL", 30))
