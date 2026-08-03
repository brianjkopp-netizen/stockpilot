"""Tests for data.fetcher.get_stock_data, mocking yfinance so no network calls are made."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from yfinance.exceptions import YFPricesMissingError, YFRateLimitError, YFTzMissingError

from data.fetcher import get_stock_data

@patch("data.fetcher.yf.Ticker")
def test_invalid_ticker_raises_value_error(mock_ticker):
    """A genuinely invalid ticker (empty frame, no exception) should raise ValueError."""
    mock_ticker.return_value.history.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="No data found for ticker 'BADTICKER'"):
        get_stock_data("BADTICKER", 5)


@patch("data.fetcher.yf.Ticker")
def test_network_failure_raises_connection_error(mock_ticker):
    """A network failure while fetching data should raise a descriptive ConnectionError."""
    mock_ticker.return_value.history.side_effect = ConnectionError("network unreachable")

    with pytest.raises(ConnectionError, match="Failed to fetch data for ticker 'AAPL'"):
        get_stock_data("AAPL", 5)


@patch("data.fetcher.yf.Ticker")
def test_yf_ticker_missing_error_raises_value_error(mock_ticker):
    """yfinance's own YFPricesMissingError/YFTzMissingError mean the provider
    affirmatively reported no data for this ticker — a real bad ticker, not an
    outage. Both are YFTickerMissingError subclasses (data/fetcher.py runs with
    yf.config.debug.hide_exceptions = False, so yfinance raises these instead
    of silently returning an empty frame).
    """
    mock_ticker.return_value.history.side_effect = YFPricesMissingError("MSFT", "no price data found (period=30d)")

    with pytest.raises(ValueError, match="No data found for ticker 'MSFT'"):
        get_stock_data("MSFT", 30)

    mock_ticker.return_value.history.side_effect = YFTzMissingError("MSFT")

    with pytest.raises(ValueError, match="No data found for ticker 'MSFT'"):
        get_stock_data("MSFT", 30)


@patch("data.fetcher.yf.Ticker")
def test_yf_rate_limit_error_raises_connection_error(mock_ticker):
    """A provider-side rate limit is an outage, not an invalid ticker — must
    raise ConnectionError, not ValueError, even though yfinance's own error
    class (YFRateLimitError) is unrelated to a plain network exception.
    """
    mock_ticker.return_value.history.side_effect = YFRateLimitError()

    with pytest.raises(ConnectionError, match="Failed to fetch data for ticker 'MSFT'"):
        get_stock_data("MSFT", 30)


@patch("data.fetcher.yf.Ticker")
def test_http_404_raises_value_error(mock_ticker):
    """yfinance's timezone-resolution fallback (hit for every ticker whose
    primary tz lookup comes back empty, including every nonexistent ticker)
    calls a quote endpoint directly and raises its HTTP client's own HTTPError
    on a 404 rather than a YFTickerMissingError. A clean 404 still means the
    provider is up and says this ticker doesn't exist, so it must map to
    ValueError, not ConnectionError. Simulated here via a plain object with a
    response.status_code, matching how curl_cffi's HTTPError (yfinance's
    current HTTP backend) shapes its exception, without importing that
    library directly.
    """
    class FakeHTTPError(Exception):
        def __init__(self):
            super().__init__("HTTP Error 404: Not Found")
            self.response = MagicMock(status_code=404)

    mock_ticker.return_value.history.side_effect = FakeHTTPError()

    with pytest.raises(ValueError, match="No data found for ticker 'FAKEXYZ'"):
        get_stock_data("FAKEXYZ", 30)
