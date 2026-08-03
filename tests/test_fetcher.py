"""Tests for data.fetcher.get_stock_data, mocking yfinance so no network calls are made."""

import logging
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data.fetcher import get_stock_data

@patch("data.fetcher.yf.Ticker")
def test_invalid_ticker_raises_value_error(mock_ticker):
    """A genuinely invalid ticker (empty frame, nothing logged) should raise ValueError."""
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
def test_swallowed_transport_failure_raises_connection_error(mock_ticker):
    """yfinance can log a transport failure and return an empty frame instead of
    raising. That must be treated as an outage (ConnectionError), not an invalid
    ticker (ValueError), even though the returned frame looks identical to a
    real bad-ticker response.
    """
    yf_logger = logging.getLogger("yfinance")

    def fake_history(*args, **kwargs):
        yf_logger.error("Failed to get ticker 'MSFT' reason: CONNECT tunnel failed, response 403")
        yf_logger.error("$MSFT: possibly delisted; no price data found (period=30d)")
        return pd.DataFrame()

    mock_ticker.return_value.history.side_effect = fake_history

    with pytest.raises(ConnectionError, match="upstream data provider unreachable"):
        get_stock_data("MSFT", 30)


@patch("data.fetcher.yf.Ticker")
def test_delisted_ticker_without_transport_log_raises_value_error(mock_ticker):
    """An empty frame with only the "possibly delisted" log line (no transport
    failure logged first) is a genuinely bad ticker, not an outage.
    """
    yf_logger = logging.getLogger("yfinance")

    def fake_history(*args, **kwargs):
        yf_logger.error("$FAKEXYZ: possibly delisted; no price data found (period=30d)")
        return pd.DataFrame()

    mock_ticker.return_value.history.side_effect = fake_history

    with pytest.raises(ValueError, match="No data found for ticker 'FAKEXYZ'"):
        get_stock_data("FAKEXYZ", 30)
