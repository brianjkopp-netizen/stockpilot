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


if __name__ == "__main__":
    print(get_stock_data("AAPL", 30))
