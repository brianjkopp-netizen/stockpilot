"""Tests for portfolio.tracker — no network traffic, no real filesystem writes."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from portfolio.tracker import (
    get_portfolio_state,
    load_portfolio_state,
    refresh_portfolio_state,
)
from trading.alpaca_client import AlpacaAuthError

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


# ---------------------------------------------------------------------------
# refresh_portfolio_state
# ---------------------------------------------------------------------------

@patch("portfolio.tracker.get_account_info", return_value=_SAMPLE_ACCOUNT)
@patch("portfolio.tracker.get_positions", return_value=_SAMPLE_POSITIONS)
def test_refresh_writes_cache_and_returns_state(mock_positions, mock_account, tmp_path):
    """refresh_portfolio_state returns correct state and writes portfolio_state.json."""
    cache_file = tmp_path / "portfolio_state.json"

    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = refresh_portfolio_state()

    assert state["positions"] == _SAMPLE_POSITIONS
    assert state["account"] == _SAMPLE_ACCOUNT
    assert "fetched_at" in state

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
def test_get_portfolio_state_prefers_live(mock_positions, mock_account, tmp_path):
    """get_portfolio_state returns live data when Alpaca is reachable."""
    cache_file = tmp_path / "portfolio_state.json"
    with patch("portfolio.tracker._CACHE_PATH", cache_file):
        state = get_portfolio_state()

    assert state["positions"] == _SAMPLE_POSITIONS
    assert "source" not in state  # live path does not tag the source


@patch("portfolio.tracker.get_account_info", side_effect=AlpacaAuthError("offline"))
@patch("portfolio.tracker.get_positions", side_effect=AlpacaAuthError("offline"))
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


@patch("portfolio.tracker.get_account_info", side_effect=AlpacaAuthError("offline"))
@patch("portfolio.tracker.get_positions", side_effect=AlpacaAuthError("offline"))
def test_get_portfolio_state_raises_when_no_cache_and_api_down(mock_positions, mock_account, tmp_path):
    """get_portfolio_state raises RuntimeError when both live API and cache are unavailable."""
    missing = tmp_path / "portfolio_state.json"

    with patch("portfolio.tracker._CACHE_PATH", missing):
        with pytest.raises(RuntimeError, match="Alpaca API is unreachable"):
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
