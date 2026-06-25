"""Tests for trading.alpaca_client — all Alpaca API calls are mocked, no network traffic."""

from unittest.mock import MagicMock, patch

import pytest

from trading.alpaca_client import (
    AlpacaAuthError,
    AlpacaNetworkError,
    AlpacaOrderError,
    decide_order,
    execute_signal,
    get_account_info,
    get_order_status,
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
def test_get_account_info_network_failure_raises(mock_client_cls):
    """get_account_info wraps transient failures in AlpacaNetworkError, not AlpacaAuthError."""
    mock_client_cls.return_value.get_account.side_effect = RuntimeError("server error")
    with pytest.raises(AlpacaNetworkError, match="Failed to reach Alpaca"):
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


# ---------------------------------------------------------------------------
# decide_order
# ---------------------------------------------------------------------------

def test_decide_order_bullish_high_returns_buy():
    action, notional = decide_order("BULLISH", "High")
    assert action == "BUY"
    assert notional == 500.0


def test_decide_order_bullish_moderate_returns_buy():
    action, notional = decide_order("BULLISH", "Moderate")
    assert action == "BUY"
    assert notional == 200.0


def test_decide_order_bullish_low_no_trade():
    action, notional = decide_order("BULLISH", "Low")
    assert action is None
    assert notional == 0.0


def test_decide_order_bearish_no_trade():
    for confidence in ("High", "Moderate", "Low"):
        action, notional = decide_order("BEARISH", confidence)
        assert action is None, f"Expected no trade for BEARISH/{confidence}"
        assert notional == 0.0


def test_decide_order_neutral_no_trade():
    for confidence in ("High", "Moderate", "Low"):
        action, notional = decide_order("NEUTRAL", confidence)
        assert action is None, f"Expected no trade for NEUTRAL/{confidence}"
        assert notional == 0.0


# ---------------------------------------------------------------------------
# execute_signal
# ---------------------------------------------------------------------------

@patch("trading.alpaca_client.TradingClient")
def test_execute_signal_bullish_high_places_buy(mock_client_cls):
    """BULLISH/High with sufficient buying power triggers a paper buy."""
    mock_client_cls.return_value.get_account.return_value = _mock_account(buying_power="10000.00")
    mock_client_cls.return_value.submit_order.return_value = _mock_order(side="buy", qty="2.381")

    signal = {"ticker": "AAPL", "signal": "BULLISH", "confidence": "High"}
    result = execute_signal(signal, current_price=210.00)

    assert result is not None
    assert result["side"] == "BUY"
    assert result["ticker"] == "AAPL"
    mock_client_cls.return_value.submit_order.assert_called_once()


@patch("trading.alpaca_client.TradingClient")
def test_execute_signal_bullish_moderate_places_smaller_buy(mock_client_cls):
    """BULLISH/Moderate places a buy with a smaller notional ($200) than High."""
    mock_client_cls.return_value.get_account.return_value = _mock_account(buying_power="10000.00")
    mock_client_cls.return_value.submit_order.return_value = _mock_order(side="buy", qty="0.952")

    signal = {"ticker": "TSLA", "signal": "BULLISH", "confidence": "Moderate"}
    result = execute_signal(signal, current_price=210.00)

    assert result is not None
    # qty should be ~$200 / $210 ≈ 0.9524 shares
    submitted_qty = mock_client_cls.return_value.submit_order.call_args[0][0].qty
    assert abs(submitted_qty - round(200.0 / 210.0, 4)) < 0.0001


def test_execute_signal_bullish_low_no_trade():
    """BULLISH/Low returns None — confidence threshold not met."""
    signal = {"ticker": "AAPL", "signal": "BULLISH", "confidence": "Low"}
    assert execute_signal(signal, current_price=210.00) is None


def test_execute_signal_neutral_no_trade():
    """NEUTRAL signal returns None regardless of confidence."""
    signal = {"ticker": "AAPL", "signal": "NEUTRAL", "confidence": "High"}
    assert execute_signal(signal, current_price=210.00) is None


def test_execute_signal_bearish_no_trade():
    """BEARISH signal returns None — no short selling."""
    signal = {"ticker": "AAPL", "signal": "BEARISH", "confidence": "High"}
    assert execute_signal(signal, current_price=210.00) is None


@patch("trading.alpaca_client.TradingClient")
def test_execute_signal_insufficient_buying_power_skips(mock_client_cls):
    """execute_signal returns None without placing an order when buying power is too low."""
    mock_client_cls.return_value.get_account.return_value = _mock_account(buying_power="100.00")

    signal = {"ticker": "AAPL", "signal": "BULLISH", "confidence": "High"}
    result = execute_signal(signal, current_price=210.00)

    assert result is None
    mock_client_cls.return_value.submit_order.assert_not_called()


def test_execute_signal_missing_keys_raises():
    """execute_signal raises ValueError when signal_dict is missing required keys."""
    with pytest.raises(ValueError, match="missing required keys"):
        execute_signal({"ticker": "AAPL"}, current_price=210.00)


def test_execute_signal_nonpositive_price_raises():
    """execute_signal raises ValueError when current_price is zero or negative."""
    signal = {"ticker": "AAPL", "signal": "BULLISH", "confidence": "High"}
    with pytest.raises(ValueError, match="current_price must be positive"):
        execute_signal(signal, current_price=0)


# ---------------------------------------------------------------------------
# get_order_status
# ---------------------------------------------------------------------------

@patch("trading.alpaca_client.TradingClient")
def test_get_order_status_filled(mock_client_cls):
    """get_order_status returns filled_qty and filled_avg_price when the order filled."""
    order = MagicMock()
    order.id = "abc-123"
    order.symbol = "AAPL"
    order.side = "buy"
    order.qty = "2.381"
    order.status = "filled"
    order.filled_qty = "2.381"
    order.filled_avg_price = "210.05"
    mock_client_cls.return_value.get_order_by_id.return_value = order

    result = get_order_status("abc-123")

    assert result["status"] == "filled"
    assert result["filled_qty"] == 2.381
    assert result["filled_avg_price"] == pytest.approx(210.05)
    assert result["ticker"] == "AAPL"


@patch("trading.alpaca_client.TradingClient")
def test_get_order_status_pending(mock_client_cls):
    """get_order_status returns filled_qty=0 and filled_avg_price=None for a pending order."""
    order = MagicMock()
    order.id = "abc-456"
    order.symbol = "TSLA"
    order.side = "buy"
    order.qty = "1.0"
    order.status = "accepted"
    order.filled_qty = None
    order.filled_avg_price = None
    mock_client_cls.return_value.get_order_by_id.return_value = order

    result = get_order_status("abc-456")

    assert result["status"] == "accepted"
    assert result["filled_qty"] == 0.0
    assert result["filled_avg_price"] is None


@patch("trading.alpaca_client.TradingClient")
def test_get_order_status_not_found_raises(mock_client_cls):
    """get_order_status raises AlpacaOrderError when the order ID is not found."""
    mock_client_cls.return_value.get_order_by_id.side_effect = RuntimeError("order not found")

    with pytest.raises(AlpacaOrderError, match="GET_STATUS"):
        get_order_status("nonexistent-id")
