"""Tests for trading.alpaca_client — all Alpaca API calls are mocked, no network traffic."""

from unittest.mock import MagicMock, patch

import pytest

from trading.alpaca_client import (
    AlpacaAuthError,
    AlpacaOrderError,
    get_account_info,
    get_positions,
    place_buy_order,
    place_sell_order,
)


def _mock_account(buying_power="50000.00", cash="50000.00", portfolio_value="50000.00"):
    acct = MagicMock()
    acct.buying_power = buying_power
    acct.cash = cash
    acct.portfolio_value = portfolio_value
    return acct


def _mock_order(side="buy", qty="1.0", status="accepted", order_id="abc-123"):
    order = MagicMock()
    order.id = order_id
    order.qty = qty
    order.side = side
    order.status = status
    order.submitted_at = None
    return order


# ---------------------------------------------------------------------------
# get_account_info
# ---------------------------------------------------------------------------

@patch("trading.alpaca_client.TradingClient")
def test_get_account_info_returns_floats(mock_client_cls):
    """get_account_info returns a dict with float values for all three keys."""
    mock_client_cls.return_value.get_account.return_value = _mock_account()
    info = get_account_info()

    assert isinstance(info["buying_power"], float)
    assert isinstance(info["cash"], float)
    assert isinstance(info["portfolio_value"], float)
    assert info["buying_power"] == 50000.0
    assert info["cash"] == 50000.0
    assert info["portfolio_value"] == 50000.0


@patch.dict("os.environ", {}, clear=True)
def test_get_account_info_missing_credentials_raises():
    """get_account_info raises AlpacaAuthError when env vars are absent."""
    with pytest.raises(AlpacaAuthError, match="APCA_API_KEY_ID"):
        get_account_info()


@patch("trading.alpaca_client.TradingClient")
def test_get_account_info_api_failure_raises(mock_client_cls):
    """get_account_info wraps unexpected Alpaca errors in AlpacaAuthError."""
    mock_client_cls.return_value.get_account.side_effect = RuntimeError("server error")
    with pytest.raises(AlpacaAuthError, match="Failed to retrieve account info"):
        get_account_info()


# ---------------------------------------------------------------------------
# place_buy_order / place_sell_order
# ---------------------------------------------------------------------------

@patch("trading.alpaca_client.TradingClient")
def test_place_buy_order_returns_expected_keys(mock_client_cls):
    """place_buy_order returns a result dict with all required keys."""
    mock_client_cls.return_value.submit_order.return_value = _mock_order(side="buy")
    result = place_buy_order("AAPL", 1.0)

    assert result["ticker"] == "AAPL"
    assert result["side"] == "BUY"
    assert result["qty"] == 1.0
    assert "id" in result
    assert "status" in result
    assert "submitted_at" in result


@patch("trading.alpaca_client.TradingClient")
def test_place_sell_order_returns_expected_keys(mock_client_cls):
    """place_sell_order returns a result dict with all required keys."""
    mock_client_cls.return_value.submit_order.return_value = _mock_order(side="sell", qty="2.5")
    result = place_sell_order("TSLA", 2.5)

    assert result["ticker"] == "TSLA"
    assert result["side"] == "SELL"
    assert result["qty"] == 2.5


def test_place_buy_order_zero_qty_raises():
    """place_buy_order raises ValueError for non-positive qty."""
    with pytest.raises(ValueError, match="qty must be positive"):
        place_buy_order("AAPL", 0)


def test_place_sell_order_negative_qty_raises():
    """place_sell_order raises ValueError for negative qty."""
    with pytest.raises(ValueError, match="qty must be positive"):
        place_sell_order("AAPL", -1.0)


@patch("trading.alpaca_client.TradingClient")
def test_place_buy_order_alpaca_rejection_raises(mock_client_cls):
    """place_buy_order raises AlpacaOrderError when Alpaca rejects the order."""
    mock_client_cls.return_value.submit_order.side_effect = RuntimeError("insufficient funds")
    with pytest.raises(AlpacaOrderError, match="BUY"):
        place_buy_order("AAPL", 100.0)


# ---------------------------------------------------------------------------
# get_positions
# ---------------------------------------------------------------------------

@patch("trading.alpaca_client.TradingClient")
def test_get_positions_returns_list(mock_client_cls):
    """get_positions returns a list of position dicts with required keys."""
    pos = MagicMock()
    pos.symbol = "AAPL"
    pos.qty = "5.0"
    pos.market_value = "1000.00"
    pos.avg_entry_price = "195.00"
    pos.unrealized_pl = "25.00"
    pos.unrealized_plpc = "0.025"
    mock_client_cls.return_value.get_all_positions.return_value = [pos]

    result = get_positions()
    assert len(result) == 1
    assert result[0]["ticker"] == "AAPL"
    assert result[0]["qty"] == 5.0
    assert result[0]["unrealized_pl"] == 25.0


@patch("trading.alpaca_client.TradingClient")
def test_get_positions_empty_account(mock_client_cls):
    """get_positions returns an empty list when there are no open positions."""
    mock_client_cls.return_value.get_all_positions.return_value = []
    assert get_positions() == []
