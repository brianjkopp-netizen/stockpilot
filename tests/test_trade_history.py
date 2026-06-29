"""Tests for trading.trade_history — all file I/O uses a temp path, no disk side-effects."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from trading.trade_history import append_trade, get_trades_for_ticker, load_trade_history

# Absolute path to the real runtime file — used to prove tests never touch it.
_REAL_HISTORY_PATH = Path(__file__).parent.parent / "trade_history.json"


@pytest.fixture(autouse=True)
def isolated_history(tmp_path, monkeypatch):
    """Redirect _HISTORY_PATH to a temp file so tests never touch trade_history.json."""
    import trading.trade_history as mod
    monkeypatch.setattr(mod, "_HISTORY_PATH", tmp_path / "trade_history.json")


# ---------------------------------------------------------------------------
# append_trade
# ---------------------------------------------------------------------------

def test_append_trade_returns_record_with_all_required_fields():
    """append_trade returns a dict containing every required field."""
    record = append_trade(
        ticker="AAPL",
        side="BUY",
        qty=2.381,
        fill_price=210.05,
        order_id="abc-001",
        signal="BULLISH",
        confidence="High",
    )

    for field in ("timestamp", "ticker", "side", "qty", "fill_price", "order_id", "signal", "confidence"):
        assert field in record, f"Missing field: {field}"
    assert record["ticker"] == "AAPL"
    assert record["side"] == "BUY"
    assert record["qty"] == 2.381
    assert record["fill_price"] == 210.05
    assert record["order_id"] == "abc-001"
    assert record["signal"] == "BULLISH"
    assert record["confidence"] == "High"
    assert record["signal_timestamp"] is None


def test_append_trade_stores_signal_timestamp_when_provided():
    """signal_timestamp is saved when supplied, enabling linkage to signals_log.json."""
    ts = "2026-06-25T12:00:00+00:00"
    record = append_trade(
        ticker="TSLA",
        side="BUY",
        qty=1.0,
        fill_price=250.0,
        order_id="abc-002",
        signal="BULLISH",
        confidence="Moderate",
        signal_timestamp=ts,
    )
    assert record["signal_timestamp"] == ts


def test_append_trade_writes_to_disk():
    """append_trade persists the record to trade_history.json."""
    import trading.trade_history as mod

    append_trade("AAPL", "BUY", 1.0, 200.0, "abc-003", "BULLISH", "High")

    with mod._HISTORY_PATH.open() as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["order_id"] == "abc-003"


def test_append_trade_accumulates_records():
    """Two append_trade calls produce two records, not one."""
    append_trade("AAPL", "BUY", 1.0, 200.0, "id-001", "BULLISH", "High")
    append_trade("TSLA", "BUY", 0.5, 300.0, "id-002", "BULLISH", "Moderate")

    history = load_trade_history()
    assert len(history) == 2
    assert history[0]["order_id"] == "id-001"
    assert history[1]["order_id"] == "id-002"


def test_append_trade_normalises_ticker_to_uppercase():
    """Ticker is stored uppercase regardless of how it is passed in."""
    record = append_trade("aapl", "BUY", 1.0, 200.0, "id-001", "BULLISH", "High")
    assert record["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# load_trade_history
# ---------------------------------------------------------------------------

def test_load_trade_history_returns_empty_list_when_no_file():
    """load_trade_history returns [] when trade_history.json does not exist."""
    assert load_trade_history() == []


def test_load_trade_history_returns_empty_list_on_corrupt_file(tmp_path, monkeypatch):
    """load_trade_history returns [] when trade_history.json contains invalid JSON."""
    import trading.trade_history as mod
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("this is not json")
    monkeypatch.setattr(mod, "_HISTORY_PATH", corrupt)

    assert load_trade_history() == []


def test_load_trade_history_returns_empty_list_on_non_array_json(tmp_path, monkeypatch):
    """load_trade_history returns [] when the file contains a JSON object, not an array."""
    import trading.trade_history as mod
    bad = tmp_path / "bad.json"
    bad.write_text('{"not": "an array"}')
    monkeypatch.setattr(mod, "_HISTORY_PATH", bad)

    assert load_trade_history() == []


# ---------------------------------------------------------------------------
# get_trades_for_ticker
# ---------------------------------------------------------------------------

def test_get_trades_for_ticker_filters_correctly():
    """get_trades_for_ticker returns only records matching the given ticker."""
    append_trade("AAPL", "BUY", 1.0, 200.0, "id-001", "BULLISH", "High")
    append_trade("TSLA", "BUY", 0.5, 300.0, "id-002", "BULLISH", "Moderate")
    append_trade("AAPL", "BUY", 0.8, 205.0, "id-003", "BULLISH", "High")

    aapl = get_trades_for_ticker("AAPL")
    assert len(aapl) == 2
    assert all(r["ticker"] == "AAPL" for r in aapl)


def test_get_trades_for_ticker_case_insensitive():
    """get_trades_for_ticker matches ticker regardless of case."""
    append_trade("AAPL", "BUY", 1.0, 200.0, "id-001", "BULLISH", "High")
    assert len(get_trades_for_ticker("aapl")) == 1
    assert len(get_trades_for_ticker("AAPL")) == 1


def test_get_trades_for_ticker_returns_empty_for_unknown():
    """get_trades_for_ticker returns [] when no records exist for the ticker."""
    append_trade("AAPL", "BUY", 1.0, 200.0, "id-001", "BULLISH", "High")
    assert get_trades_for_ticker("MSFT") == []


# ---------------------------------------------------------------------------
# Smoke test: two paper trades, two records with correct fields
# ---------------------------------------------------------------------------

@patch("trading.alpaca_client.get_latest_price", return_value=210.00)
@patch("trading.alpaca_client.TradingClient")
def test_smoke_execute_signal_records_two_trades(mock_client_cls, mock_price):
    """Smoke test: two execute_signal calls produce two trade history records with correct fields."""
    import trading.trade_history as mod
    import trading.alpaca_client as alpaca_mod

    def _mock_account():
        acct = MagicMock()
        acct.buying_power = "50000.00"
        acct.cash = "50000.00"
        acct.portfolio_value = "50000.00"
        return acct

    def _mock_order(order_id, qty):
        order = MagicMock()
        order.id = order_id
        order.qty = qty
        order.side = "buy"
        order.status = "accepted"
        order.submitted_at = None
        return order

    mock_client_cls.return_value.get_account.return_value = _mock_account()
    mock_client_cls.return_value.submit_order.side_effect = [
        _mock_order("order-aapl-001", "2.381"),
        _mock_order("order-tsla-001", "0.952"),
    ]

    from trading.alpaca_client import execute_signal

    signal_aapl = {"ticker": "AAPL", "signal": "BULLISH", "confidence": "High"}
    signal_tsla = {"ticker": "TSLA", "signal": "BULLISH", "confidence": "Moderate"}

    execute_signal(signal_aapl)
    execute_signal(signal_tsla)

    history = load_trade_history()
    assert len(history) == 2, f"Expected 2 records, got {len(history)}"

    aapl_trade = history[0]
    assert aapl_trade["ticker"] == "AAPL"
    assert aapl_trade["side"] == "BUY"
    assert aapl_trade["fill_price"] == 210.00
    assert aapl_trade["order_id"] == "order-aapl-001"
    assert aapl_trade["signal"] == "BULLISH"
    assert aapl_trade["confidence"] == "High"
    assert "timestamp" in aapl_trade

    tsla_trade = history[1]
    assert tsla_trade["ticker"] == "TSLA"
    assert tsla_trade["side"] == "BUY"
    assert tsla_trade["fill_price"] == 210.00
    assert tsla_trade["order_id"] == "order-tsla-001"
    assert tsla_trade["signal"] == "BULLISH"
    assert tsla_trade["confidence"] == "Moderate"


# ---------------------------------------------------------------------------
# Isolation proof: fake trades never touch the real file, real tickers go to temp
# ---------------------------------------------------------------------------

def test_fake_trade_does_not_pollute_real_history():
    """A mock/test trade (order_id 'abc-123') must not modify the real trade_history.json.

    This is the regression check for the phantom-trade bug: test runs were
    appending fake records to the live file because _HISTORY_PATH was not
    redirected. The isolate_trade_history fixture in conftest.py (autouse)
    redirects writes to tmp_path — this test proves it works.
    """
    real_content_before = _REAL_HISTORY_PATH.read_text() if _REAL_HISTORY_PATH.exists() else None

    append_trade(
        ticker="AAPL",
        side="BUY",
        qty=2.381,
        fill_price=210.0,
        order_id="abc-123",  # the mock default that caused the original pollution
        signal="BULLISH",
        confidence="High",
    )

    real_content_after = _REAL_HISTORY_PATH.read_text() if _REAL_HISTORY_PATH.exists() else None
    assert real_content_before == real_content_after, (
        "append_trade wrote to the real trade_history.json during a test — "
        "isolate_trade_history fixture is not working"
    )


def test_real_ticker_trade_writes_to_temp_path_not_real_file():
    """A legitimate ticker trade must be persisted — but only in the test's temp path.

    Confirms that isolation does not silently drop writes: the record lands in
    the redirected tmp_path file, and the real trade_history.json is untouched.
    """
    import trading.trade_history as mod

    real_content_before = _REAL_HISTORY_PATH.read_text() if _REAL_HISTORY_PATH.exists() else None

    append_trade(
        ticker="AAPL",
        side="BUY",
        qty=2.381,
        fill_price=210.05,
        order_id="real-order-uuid-001",
        signal="BULLISH",
        confidence="High",
    )

    # The record must exist in the temp file.
    temp_history = json.loads(mod._HISTORY_PATH.read_text())
    assert len(temp_history) == 1
    assert temp_history[0]["order_id"] == "real-order-uuid-001"
    assert temp_history[0]["ticker"] == "AAPL"

    # The real file must be unchanged.
    real_content_after = _REAL_HISTORY_PATH.read_text() if _REAL_HISTORY_PATH.exists() else None
    assert real_content_before == real_content_after, (
        "append_trade modified the real trade_history.json — isolation is broken"
    )
