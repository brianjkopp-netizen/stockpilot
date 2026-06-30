"""Tests for portfolio.tracker — no network traffic, no real filesystem writes."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from portfolio.tracker import (
    _compute_totals,
    _mark_to_market,
    get_portfolio_state,
    load_portfolio_state,
    refresh_portfolio_state,
)
from trading.alpaca_client import AlpacaAuthError, AlpacaNetworkError

_SAMPLE_POSITIONS = [
    {
        "ticker": "AAPL",
        "qty": 2.381,
        "market_value": 500.10,
        "avg_entry_price": 210.00,
        "unrealized_pl": 0.10,
        "unrealized_plpc": 0.0002,
    }
]

_SAMPLE_ACCOUNT = {
    "buying_power": 49500.0,
    "cash": 49500.0,
    "portfolio_value": 50000.10,
}

# A live-priced position as it appears once _mark_to_market has run — used by
# tests that exercise the caching/fallback paths after pricing is already applied.
_SAMPLE_PRICED_POSITIONS = [
    {
        "ticker": "AAPL",
        "qty": 2.381,
        "avg_entry_price": 210.00,
        "mark_price": 215.00,
        "market_value": 511.92,
        "unrealized_pl": 11.91,
        "unrealized_plpc": 0.0238,
        "daily_pl": 4.76,
        "daily_plpc": 0.0235,
    }
]


def _quote_history(closes: list) -> pd.DataFrame:
    """Build a minimal OHLCV-shaped DataFrame as data.fetcher.get_stock_data would return."""
    return pd.DataFrame({"Close": closes})


# ---------------------------------------------------------------------------
# refresh_portfolio_state
# ---------------------------------------------------------------------------

@patch("portfolio.tracker.get_account_info", return_value=_SAMPLE_ACCOUNT)
@patch("portfolio.tracker.get_positions", return_value=_SAMPLE_POSITIONS)
@patch("portfolio.tracker.get_stock_data", return_value=_quote_history([212.0, 215.0]))
def test_refresh_writes_cache_and_returns_state(mock_quote, mock_positions, mock_account, tmp_path):
    """refresh_portfolio_state marks positions to market, aggregates totals, and writes the cache."""
    cache_file = tmp_path / "portfolio_state.json"

    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = refresh_portfolio_state()

    assert state["account"] == _SAMPLE_ACCOUNT
    assert "fetched_at" in state

    pos = state["positions"][0]
    assert pos["ticker"] == "AAPL"
    assert pos["mark_price"] == 215.0
    assert pos["market_value"] == pytest.approx(215.0 * 2.381)
    assert pos["unrealized_pl"] == pytest.approx((215.0 - 210.0) * 2.381)
    assert pos["daily_pl"] == pytest.approx((215.0 - 212.0) * 2.381)

    assert state["totals"]["market_value"] == pytest.approx(pos["market_value"])
    assert state["totals"]["unrealized_pl"] == pytest.approx(pos["unrealized_pl"])
    assert state["totals"]["daily_pl"] == pytest.approx(pos["daily_pl"])

    written = json.loads(cache_file.read_text())
    assert written["fetched_at"] == state["fetched_at"]
    assert written["positions"][0]["ticker"] == "AAPL"


@patch("portfolio.tracker.get_account_info", side_effect=AlpacaAuthError("bad creds"))
@patch("portfolio.tracker.get_positions", return_value=_SAMPLE_POSITIONS)
def test_refresh_propagates_alpaca_auth_error(mock_positions, mock_account):
    """refresh_portfolio_state raises AlpacaAuthError when the API call fails."""
    with pytest.raises(AlpacaAuthError, match="bad creds"):
        refresh_portfolio_state()


# ---------------------------------------------------------------------------
# _mark_to_market / _compute_totals
# ---------------------------------------------------------------------------

@patch("portfolio.tracker.get_stock_data", return_value=_quote_history([212.0, 215.0]))
def test_mark_to_market_computes_pl_from_live_price(mock_quote):
    """_mark_to_market overrides market_value/unrealized_pl using the yfinance mark, not Alpaca's quote."""
    priced = _mark_to_market(_SAMPLE_POSITIONS[0])

    assert priced["mark_price"] == 215.0
    assert priced["market_value"] == pytest.approx(215.0 * 2.381)
    assert priced["unrealized_pl"] == pytest.approx((215.0 - 210.0) * 2.381)
    assert priced["unrealized_plpc"] == pytest.approx((215.0 - 210.0) / 210.0)
    assert priced["daily_pl"] == pytest.approx((215.0 - 212.0) * 2.381)
    assert priced["daily_plpc"] == pytest.approx((215.0 - 212.0) / 212.0)


@patch("portfolio.tracker.get_stock_data", return_value=_quote_history([215.0]))
def test_mark_to_market_single_day_history_has_zero_daily_pl(mock_quote):
    """With only one trading day of history, prior_close falls back to mark_price."""
    priced = _mark_to_market(_SAMPLE_POSITIONS[0])

    assert priced["daily_pl"] == 0.0
    assert priced["daily_plpc"] == 0.0


@patch("portfolio.tracker.get_stock_data", side_effect=ConnectionError("network down"))
def test_mark_to_market_falls_back_when_yfinance_unreachable(mock_quote):
    """A yfinance failure for one ticker degrades gracefully instead of raising."""
    priced = _mark_to_market(_SAMPLE_POSITIONS[0])

    assert priced["daily_pl"] == 0.0
    assert priced["daily_plpc"] == 0.0
    assert priced["market_value"] == _SAMPLE_POSITIONS[0]["market_value"]
    assert priced["unrealized_pl"] == _SAMPLE_POSITIONS[0]["unrealized_pl"]


def test_compute_totals_aggregates_across_positions():
    """_compute_totals sums market value and P&L, and weights percent returns by cost/prior value."""
    positions = [
        {
            "ticker": "AAPL", "qty": 2.0, "avg_entry_price": 200.0,
            "market_value": 430.0, "unrealized_pl": 30.0, "daily_pl": 10.0,
        },
        {
            "ticker": "MSFT", "qty": 1.0, "avg_entry_price": 300.0,
            "market_value": 290.0, "unrealized_pl": -10.0, "daily_pl": -5.0,
        },
    ]
    totals = _compute_totals(positions)

    assert totals["market_value"] == 720.0
    assert totals["cost_basis"] == 700.0
    assert totals["unrealized_pl"] == 20.0
    assert totals["unrealized_plpc"] == pytest.approx(20.0 / 700.0)
    assert totals["daily_pl"] == 5.0
    assert totals["daily_plpc"] == pytest.approx(5.0 / (720.0 - 5.0))


def test_compute_totals_empty_positions_is_all_zero():
    """_compute_totals returns zeroed-out totals for an empty positions list."""
    totals = _compute_totals([])
    assert totals == {
        "market_value": 0.0,
        "cost_basis": 0,
        "unrealized_pl": 0,
        "unrealized_plpc": 0.0,
        "daily_pl": 0,
        "daily_plpc": 0.0,
    }


# ---------------------------------------------------------------------------
# load_portfolio_state
# ---------------------------------------------------------------------------

def test_load_returns_none_when_no_cache(tmp_path):
    """load_portfolio_state returns None when portfolio_state.json does not exist."""
    with patch("portfolio.tracker._CACHE_PATH", tmp_path / "missing.json"):
        assert load_portfolio_state() is None


def test_load_returns_none_on_corrupt_json(tmp_path):
    """load_portfolio_state returns None when the cache file contains invalid JSON."""
    bad_file = tmp_path / "portfolio_state.json"
    bad_file.write_text("not json {{{")

    with patch("portfolio.tracker._CACHE_PATH", bad_file):
        assert load_portfolio_state() is None


def test_load_returns_cached_state(tmp_path):
    """load_portfolio_state deserialises and returns the cached state dict."""
    cache_file = tmp_path / "portfolio_state.json"
    expected = {
        "positions": _SAMPLE_POSITIONS,
        "account": _SAMPLE_ACCOUNT,
        "fetched_at": "2026-06-24T12:00:00+00:00",
    }
    cache_file.write_text(json.dumps(expected))

    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = load_portfolio_state()

    assert state["fetched_at"] == "2026-06-24T12:00:00+00:00"
    assert state["positions"][0]["ticker"] == "AAPL"
    assert state["account"]["portfolio_value"] == 50000.10


# ---------------------------------------------------------------------------
# get_portfolio_state (live-first, cache fallback)
# ---------------------------------------------------------------------------

@patch("portfolio.tracker.get_account_info", return_value=_SAMPLE_ACCOUNT)
@patch("portfolio.tracker.get_positions", return_value=_SAMPLE_POSITIONS)
@patch("portfolio.tracker.get_stock_data", return_value=_quote_history([212.0, 215.0]))
def test_get_portfolio_state_prefers_live(mock_quote, mock_positions, mock_account, tmp_path):
    """get_portfolio_state returns live mark-to-market data when Alpaca is reachable."""
    cache_file = tmp_path / "portfolio_state.json"
    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = get_portfolio_state()

    assert state["positions"][0]["ticker"] == "AAPL"
    assert state["positions"][0]["mark_price"] == 215.0
    assert "totals" in state
    assert "source" not in state  # live path does not tag the source


@patch("portfolio.tracker.get_account_info", side_effect=AlpacaNetworkError("offline"))
@patch("portfolio.tracker.get_positions", side_effect=AlpacaNetworkError("offline"))
def test_get_portfolio_state_falls_back_to_cache(mock_positions, mock_account, tmp_path):
    """get_portfolio_state falls back to cache when Alpaca is unreachable."""
    cache_file = tmp_path / "portfolio_state.json"
    cached = {
        "positions": _SAMPLE_POSITIONS,
        "account": _SAMPLE_ACCOUNT,
        "fetched_at": "2026-06-24T11:00:00+00:00",
    }
    cache_file.write_text(json.dumps(cached))

    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = get_portfolio_state()

    assert state["source"] == "cache"
    assert state["positions"][0]["ticker"] == "AAPL"


@patch("portfolio.tracker.get_account_info", side_effect=AlpacaNetworkError("offline"))
@patch("portfolio.tracker.get_positions", side_effect=AlpacaNetworkError("offline"))
def test_get_portfolio_state_raises_when_no_cache_and_api_down(mock_positions, mock_account, tmp_path):
    """get_portfolio_state raises RuntimeError when both live API and cache are unavailable."""
    missing = tmp_path / "portfolio_state.json"

    with patch("portfolio.tracker._CACHE_PATH", missing):
        with pytest.raises(RuntimeError, match="Alpaca API is unreachable"):
            get_portfolio_state()


@patch("portfolio.tracker.get_account_info", side_effect=AlpacaAuthError("invalid key"))
@patch("portfolio.tracker.get_positions", side_effect=AlpacaAuthError("invalid key"))
def test_get_portfolio_state_propagates_auth_error(mock_positions, mock_account, tmp_path):
    """get_portfolio_state does not fall back to cache on auth failure — raises AlpacaAuthError."""
    cache_file = tmp_path / "portfolio_state.json"
    cache_file.write_text('{"positions": [], "account": {}, "fetched_at": "2026-06-24T12:00:00+00:00"}')

    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        with pytest.raises(AlpacaAuthError, match="invalid key"):
            get_portfolio_state()


@patch("portfolio.tracker.get_account_info", return_value=_SAMPLE_ACCOUNT)
@patch("portfolio.tracker.get_positions", return_value=[])
def test_get_portfolio_state_empty_positions(mock_positions, mock_account, tmp_path):
    """get_portfolio_state returns an empty positions list when no positions are open."""
    cache_file = tmp_path / "portfolio_state.json"
    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = get_portfolio_state()

    assert state["positions"] == []
    assert state["account"]["portfolio_value"] == 50000.10
