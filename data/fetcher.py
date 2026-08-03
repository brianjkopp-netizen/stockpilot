"""Fetches OHLCV stock data from yfinance for the StockPilot analysis pipeline."""

import logging

import pandas as pd
import yfinance as yf

# yfinance's default config swallows transport-layer exceptions (timeouts,
# connection resets, HTTP errors from Yahoo or an upstream proxy) instead of
# raising them: it logs "Failed to get ticker '<ticker>' reason: ..." on its
# own "yfinance" logger and returns an empty DataFrame. That empty frame is
# byte-for-byte identical to what a genuinely invalid ticker returns, so we
# watch the yfinance logger during the call to tell the two apart.
_YF_TRANSPORT_FAILURE_MARKER = "Failed to get ticker"


class _TransportFailureListener(logging.Handler):
    """Detects yfinance's own logged transport failures during a single call."""

    def __init__(self):
        super().__init__(level=logging.ERROR)
        self.saw_transport_failure = False

    def emit(self, record: logging.LogRecord) -> None:
        if _YF_TRANSPORT_FAILURE_MARKER in record.getMessage():
            self.saw_transport_failure = True


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
            ticker genuinely does not return any data (e.g. an invalid
            symbol).
        ConnectionError: If the data could not be fetched due to a network
            error, including a network failure that yfinance swallowed
            internally and surfaced only as an empty frame plus a logged
            transport error.
    """
    if not ticker or not ticker.strip():
        raise ValueError("Ticker must be a non-empty string.")
    if days <= 0:
        raise ValueError(f"Days must be a positive integer, got {days}.")

    yf_logger = logging.getLogger("yfinance")
    listener = _TransportFailureListener()
    yf_logger.addHandler(listener)
    try:
        data = yf.Ticker(ticker.strip().upper()).history(period=f"{days}d")
    except Exception as exc:
        raise ConnectionError(
            f"Failed to fetch data for ticker '{ticker}': {exc}"
        ) from exc
    finally:
        yf_logger.removeHandler(listener)

    if data.empty:
        if listener.saw_transport_failure:
            raise ConnectionError(
                f"Failed to fetch data for ticker '{ticker}': upstream data provider unreachable"
            )
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
