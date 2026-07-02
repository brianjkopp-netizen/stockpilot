"""Fetches OHLCV stock data from yfinance for the StockPilot analysis pipeline."""

import pandas as pd
import yfinance as yf


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
            ticker does not return any data (e.g. an invalid symbol).
        ConnectionError: If the data could not be fetched due to a
            network error.
    """
    if not ticker or not ticker.strip():
        raise ValueError("Ticker must be a non-empty string.")
    if days <= 0:
        raise ValueError(f"Days must be a positive integer, got {days}.")

    try:
        data = yf.Ticker(ticker.strip().upper()).history(period=f"{days}d")
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
