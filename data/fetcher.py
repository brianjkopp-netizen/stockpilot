"""Fetches OHLCV stock data from yfinance for the StockPilot analysis pipeline."""

import logging

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFTickerMissingError

_log = logging.getLogger(__name__)


def disable_yfinance_error_hiding() -> None:
    """Make yfinance raise real exceptions instead of silently hiding them.

    yfinance's default config (hide_exceptions=True) swallows internal errors —
    a network failure, a rate limit, a malformed provider response — and
    returns an empty DataFrame instead of raising. That empty frame is
    byte-for-byte identical to what a genuinely invalid ticker returns, which
    is the root cause of the bug this works around: an outage looks like an
    invalid ticker. Disabling it makes yfinance raise real exceptions instead,
    so failure type can be told apart from "the ticker doesn't exist."

    Shared by data/fetcher.py and trading/alpaca_client.py, both of which call
    this at import time (process-wide and set once, not toggled per call,
    since it's a shared global on the yfinance module — flipping it per-request
    would race against concurrent requests handled on other threads).

    yf.config.debug.hide_exceptions is an undocumented internal yfinance
    attribute, not a public API. If a future yfinance version renames or
    restructures it, this must not raise at import time: api/main.py imports
    data.fetcher at module scope, so an uncaught AttributeError here would
    crash uvicorn before it binds a port, with no application logs to explain
    why. Instead, log a warning and leave hide_exceptions at its default —
    degrading the outage-vs-invalid-ticker distinction rather than taking the
    service down. See CLAUDE.md for the re-verification note on yfinance
    upgrades.
    """
    try:
        yf.config.debug.hide_exceptions = False
    except AttributeError:
        _log.warning(
            "yfinance no longer exposes yf.config.debug.hide_exceptions "
            "(library internals may have changed). Continuing with yfinance's "
            "default error hiding: network failures and rate limits may now be "
            "misreported as invalid tickers until this is re-verified against "
            "the new yfinance version."
        )


disable_yfinance_error_hiding()


def is_http_not_found(exc: Exception) -> bool:
    """True if exc represents a clean HTTP 404 from the data provider.

    yfinance's timezone-resolution fallback (used internally by `.history()`
    for every ticker whose primary tz lookup comes back empty — which
    includes every nonexistent ticker) hits a quote endpoint directly via its
    HTTP client and raises that client's own HTTPError on a 404, rather than
    yfinance's YFTickerMissingError. A clean 404 means the provider is up and
    affirmatively says this ticker doesn't exist, so it belongs with the
    invalid-ticker case, not the outage case. Checked via duck typing
    (response.status_code) instead of importing yfinance's underlying HTTP
    library's exception classes directly, since that library is an internal
    implementation detail yfinance could swap out.
    """
    return getattr(getattr(exc, "response", None), "status_code", None) == 404


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
        if is_http_not_found(exc):
            raise ValueError(f"No data found for ticker '{ticker}'. It may be invalid.") from exc
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
