"""Tests for portfolio.recommender — all API calls are monkeypatched, no network traffic."""

import httpx
import pytest
from unittest.mock import MagicMock, patch

import anthropic

from portfolio.recommender import (
    RecommendationError,
    compute_verdict,
    get_recommendation,
    parse_brief,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _position(unrealized_plpc: float, ticker: str = "AAPL") -> dict:
    """Minimal position dict with only the fields compute_verdict needs."""
    return {
        "ticker": ticker,
        "qty": 10.0,
        "avg_entry_price": 200.0,
        "mark_price": 200.0 * (1 + unrealized_plpc),
        "market_value": 2000.0 * (1 + unrealized_plpc),
        "unrealized_pl": 2000.0 * unrealized_plpc,
        "unrealized_plpc": unrealized_plpc,
        "daily_pl": 0.0,
        "daily_plpc": 0.0,
    }


_FAKE_REQUEST = httpx.Request("GET", "https://api.anthropic.com")


# ---------------------------------------------------------------------------
# compute_verdict — rule mapping
# ---------------------------------------------------------------------------

class TestComputeVerdict:
    def test_hard_stop_loss_is_sell_regardless_of_signal(self):
        """unrealized_plpc < -10% → SELL, even with a BULLISH signal."""
        pos = _position(-0.11)
        assert compute_verdict(pos, "BULLISH", "High") == "SELL"

    def test_hard_stop_loss_boundary_is_sell(self):
        """unrealized_plpc == -10% crosses the hard stop and returns SELL."""
        pos = _position(-0.10)
        assert compute_verdict(pos, "NEUTRAL", "Low") == "SELL"

    def test_moderate_loss_with_bearish_signal_is_sell(self):
        """unrealized_plpc < -5% + BEARISH → SELL (soft stop triggered)."""
        pos = _position(-0.06)
        assert compute_verdict(pos, "BEARISH", "Moderate") == "SELL"

    def test_moderate_loss_with_neutral_signal_is_hold(self):
        """unrealized_plpc < -5% but NEUTRAL signal → HOLD (soft stop not triggered)."""
        pos = _position(-0.06)
        assert compute_verdict(pos, "NEUTRAL", "Low") == "HOLD"

    def test_moderate_loss_with_bullish_signal_is_hold(self):
        """Losing position with a BULLISH signal still returns HOLD, not ADD."""
        pos = _position(-0.03)
        assert compute_verdict(pos, "BULLISH", "High") == "HOLD"

    def test_winning_position_bullish_high_is_add(self):
        """Positive P&L + BULLISH + High confidence → ADD."""
        pos = _position(0.08)
        assert compute_verdict(pos, "BULLISH", "High") == "ADD"

    def test_winning_position_bullish_moderate_is_add(self):
        """Positive P&L + BULLISH + Moderate confidence → ADD."""
        pos = _position(0.03)
        assert compute_verdict(pos, "BULLISH", "Moderate") == "ADD"

    def test_winning_position_bullish_low_confidence_is_hold(self):
        """Positive P&L + BULLISH but Low confidence → HOLD (conviction not sufficient)."""
        pos = _position(0.05)
        assert compute_verdict(pos, "BULLISH", "Low") == "HOLD"

    def test_winning_position_neutral_signal_is_hold(self):
        """Positive P&L + NEUTRAL signal → HOLD."""
        pos = _position(0.10)
        assert compute_verdict(pos, "NEUTRAL", "Low") == "HOLD"

    def test_winning_position_bearish_signal_is_hold(self):
        """Gaining position with a BEARISH signal → HOLD (no hard-stop threshold met)."""
        pos = _position(0.02)
        assert compute_verdict(pos, "BEARISH", "High") == "HOLD"

    def test_flat_position_is_hold(self):
        """Zero P&L returns HOLD regardless of signal."""
        pos = _position(0.0)
        assert compute_verdict(pos, "BULLISH", "High") == "HOLD"


# ---------------------------------------------------------------------------
# parse_brief
# ---------------------------------------------------------------------------

class TestParseBrief:
    def test_parses_well_formed_response(self):
        raw = "BRIEF: Hold {AAPL} while the 10-day MA aligns."
        assert parse_brief(raw) == "Hold {AAPL} while the 10-day MA aligns."

    def test_parses_multiline_response_with_preamble(self):
        """BRIEF: line is extracted even when there is text before it."""
        raw = "Some preamble\nBRIEF: The position shows strength.\nSome postamble"
        assert parse_brief(raw) == "The position shows strength."

    def test_returns_fallback_when_brief_line_missing(self):
        result = parse_brief("No brief here.")
        assert "unavailable" in result.lower()

    def test_returns_fallback_on_empty_string(self):
        result = parse_brief("")
        assert "unavailable" in result.lower()

    def test_returns_fallback_when_brief_value_empty(self):
        result = parse_brief("BRIEF:")
        assert "unavailable" in result.lower()


# ---------------------------------------------------------------------------
# get_recommendation — API success and failure paths
# ---------------------------------------------------------------------------

def _mock_anthropic_response(brief_text: str) -> MagicMock:
    """Return a mock Anthropic client whose messages.create returns brief_text."""
    content_block = MagicMock()
    content_block.text = f"BRIEF: {brief_text}"
    msg = MagicMock()
    msg.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = msg
    return client


def _make_summary():
    return {
        "current_price": 210.0,
        "ma_10": 205.0,
        "ma_20": 200.0,
        "volume_signal": "ABOVE AVERAGE",
        "price_vs_ma10": "ABOVE",
        "price_vs_ma20": "ABOVE",
    }


import pandas as pd


def _quote_df(closes: list) -> pd.DataFrame:
    return pd.DataFrame({"Close": closes})


@patch("portfolio.recommender.get_stock_data", return_value=_quote_df([205.0, 210.0]))
@patch("portfolio.recommender.anthropic.Anthropic")
def test_get_recommendation_returns_verdict_and_brief(mock_anthro_cls, mock_data):
    """get_recommendation returns ticker, verdict, brief, signal, confidence."""
    mock_anthro_cls.return_value = _mock_anthropic_response("Holding is prudent here.")

    pos = _position(0.05)
    result = get_recommendation(pos)

    assert result["ticker"] == "AAPL"
    assert result["verdict"] in ("HOLD", "ADD", "SELL")
    assert result["brief"] == "Holding is prudent here."
    assert result["signal"] in ("BULLISH", "BEARISH", "NEUTRAL")
    assert result["confidence"] in ("High", "Moderate", "Low")


@patch("portfolio.recommender.get_stock_data", return_value=_quote_df([205.0, 210.0]))
@patch("portfolio.recommender.anthropic.Anthropic")
def test_get_recommendation_auth_error_raises_recommendation_error(mock_anthro_cls, mock_data):
    """RecommendationError is raised when Anthropic returns 401."""
    client = MagicMock()
    client.messages.create.side_effect = anthropic.AuthenticationError(
        message="invalid x-api-key",
        response=httpx.Response(401, request=_FAKE_REQUEST),
        body=None,
    )
    mock_anthro_cls.return_value = client

    with pytest.raises(RecommendationError) as exc_info:
        get_recommendation(_position(0.05))

    assert "AAPL" in str(exc_info.value)
    assert "ANTHROPIC_API_KEY" in str(exc_info.value)


@patch("portfolio.recommender.get_stock_data", return_value=_quote_df([205.0, 210.0]))
@patch("portfolio.recommender.anthropic.Anthropic")
def test_get_recommendation_connection_error_raises_recommendation_error(mock_anthro_cls, mock_data):
    """RecommendationError is raised when the Anthropic API is unreachable."""
    client = MagicMock()
    client.messages.create.side_effect = anthropic.APIConnectionError(request=_FAKE_REQUEST)
    mock_anthro_cls.return_value = client

    with pytest.raises(RecommendationError):
        get_recommendation(_position(0.05))


@patch("portfolio.recommender.get_stock_data", return_value=_quote_df([205.0, 210.0]))
@patch("portfolio.recommender.anthropic.Anthropic")
def test_get_recommendation_malformed_response_returns_fallback_brief(mock_anthro_cls, mock_data):
    """A model response missing the BRIEF: prefix degrades to a fallback string, not a crash."""
    content_block = MagicMock()
    content_block.text = "I don't feel like following the format today."
    msg = MagicMock()
    msg.content = [content_block]
    client = MagicMock()
    client.messages.create.return_value = msg
    mock_anthro_cls.return_value = client

    result = get_recommendation(_position(0.05))

    assert result["verdict"] in ("HOLD", "ADD", "SELL")
    assert "unavailable" in result["brief"].lower()
