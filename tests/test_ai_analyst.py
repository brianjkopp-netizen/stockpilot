"""Tests for analysis.ai_analyst — all API calls are monkeypatched, no network traffic."""

import httpx
import pytest
from unittest.mock import MagicMock

import anthropic

from analysis.ai_analyst import get_signal, SignalGenerationError


_SUMMARY = {
    "current_price": 100.0,
    "ma_10": 98.0,
    "ma_20": 95.0,
    "volume_signal": "ABOVE AVERAGE",
    "price_vs_ma10": "ABOVE",
    "price_vs_ma20": "ABOVE",
}

_FAKE_REQUEST = httpx.Request("GET", "https://api.anthropic.com")


def _client_raising(exc: Exception):
    """Return a mock Anthropic() instance whose messages.create raises exc."""
    mock = MagicMock()
    mock.messages.create.side_effect = exc
    return mock


# ---------------------------------------------------------------------------
# Connection failure
# ---------------------------------------------------------------------------

def test_get_signal_raises_signal_generation_error_on_connection_failure(monkeypatch, tmp_path):
    """SignalGenerationError is raised and signals_log.json is not created on connection error."""
    conn_error = anthropic.APIConnectionError(request=_FAKE_REQUEST)

    monkeypatch.setattr(
        "analysis.ai_analyst.anthropic.Anthropic",
        lambda: _client_raising(conn_error),
    )
    log_path = tmp_path / "signals_log.json"
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    with pytest.raises(SignalGenerationError) as exc_info:
        get_signal("AAPL", _SUMMARY)

    assert "AAPL" in str(exc_info.value)
    assert not log_path.exists()


# ---------------------------------------------------------------------------
# Authentication failure
# ---------------------------------------------------------------------------

def test_get_signal_auth_error_mentions_api_key(monkeypatch, tmp_path):
    """SignalGenerationError message names ANTHROPIC_API_KEY when auth fails."""
    auth_error = anthropic.AuthenticationError(
        message="invalid x-api-key",
        response=httpx.Response(401, request=_FAKE_REQUEST),
        body=None,
    )

    monkeypatch.setattr(
        "analysis.ai_analyst.anthropic.Anthropic",
        lambda: _client_raising(auth_error),
    )
    log_path = tmp_path / "signals_log.json"
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    with pytest.raises(SignalGenerationError) as exc_info:
        get_signal("TSLA", _SUMMARY)

    assert "ANTHROPIC_API_KEY" in str(exc_info.value)
    assert not log_path.exists()


# ---------------------------------------------------------------------------
# Generic API status error (e.g. rate limit)
# ---------------------------------------------------------------------------

def test_get_signal_no_log_written_on_api_status_error(monkeypatch, tmp_path):
    """signals_log.json is not created when the API returns a non-2xx status."""
    rate_error = anthropic.RateLimitError(
        message="rate limit exceeded",
        response=httpx.Response(429, request=_FAKE_REQUEST),
        body=None,
    )

    monkeypatch.setattr(
        "analysis.ai_analyst.anthropic.Anthropic",
        lambda: _client_raising(rate_error),
    )
    log_path = tmp_path / "signals_log.json"
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    with pytest.raises(SignalGenerationError):
        get_signal("MSFT", _SUMMARY)

    assert not log_path.exists()
