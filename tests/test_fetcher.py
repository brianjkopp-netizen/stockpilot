"""Tests for data.fetcher.get_stock_data, mocking yfinance so no network calls are made."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.fetcher import get_stock_data

@patch("data.fetcher.yf.Ticker")
def test_invalid_ticker_raises_value_error(mock_ticker):
    """An invalid ticker (no data returned) should raise a descriptive ValueError."""
    mock_ticker.return_value.history.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="No data found for ticker 'BADTICKER'"):
        get_stock_data("BADTICKER", 5)


@patch("data.fetcher.yf.Ticker")
def test_network_failure_raises_connection_error(mock_ticker):
    """A network failure while fetching data should raise a descriptive ConnectionError."""
    mock_ticker.return_value.history.side_effect = ConnectionError("network unreachable")

    with pytest.raises(ConnectionError, match="Failed to fetch data for ticker 'AAPL'"):
        get_stock_data("AAPL", 5)
