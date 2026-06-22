"""Tests for analysis.ai_analyst — all API calls are monkeypatched, no network traffic."""

import httpx
import json
import pytest
from unittest.mock import MagicMock

import anthropic

from analysis.ai_analyst import (
    get_signal,
    log_signal,
    load_signal_history,
    calibrate_signal,
    SignalGenerationError,
)


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


# ---------------------------------------------------------------------------
# log_signal — corrupt / empty / missing file
# ---------------------------------------------------------------------------

_FAKE_SIGNAL = {
    "ticker": "AAPL",
    "signal": "BULLISH",
    "confidence": "High",
    "reasoning": "Strong momentum.",
    "key_factors": ["above MA10", "above MA20", "high volume"],
}


def test_log_signal_creates_file_when_missing(monkeypatch, tmp_path):
    """log_signal creates signals_log.json from scratch when it does not exist."""
    log_path = tmp_path / "signals_log.json"
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    log_signal(_FAKE_SIGNAL, 100.0)

    records = json.loads(log_path.read_text())
    assert len(records) == 1
    assert records[0]["ticker"] == "AAPL"


def test_log_signal_recovers_from_empty_file(monkeypatch, tmp_path):
    """log_signal treats an empty signals_log.json as a fresh log and backs up the corrupt file."""
    log_path = tmp_path / "signals_log.json"
    log_path.write_text("")
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    log_signal(_FAKE_SIGNAL, 100.0)

    records = json.loads(log_path.read_text())
    assert len(records) == 1
    assert (tmp_path / "signals_log.corrupt.json").exists()


def test_log_signal_recovers_from_invalid_json(monkeypatch, tmp_path):
    """log_signal treats malformed JSON as a fresh log and backs up the corrupt file."""
    log_path = tmp_path / "signals_log.json"
    log_path.write_text("{not valid json")
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    log_signal(_FAKE_SIGNAL, 100.0)

    records = json.loads(log_path.read_text())
    assert len(records) == 1
    assert (tmp_path / "signals_log.corrupt.json").exists()


def test_log_signal_appends_to_valid_log(monkeypatch, tmp_path):
    """log_signal appends to an existing valid log without overwriting prior records."""
    log_path = tmp_path / "signals_log.json"
    log_path.write_text(json.dumps([{"ticker": "TSLA", "signal": "BEARISH"}]))
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    log_signal(_FAKE_SIGNAL, 100.0)

    records = json.loads(log_path.read_text())
    assert len(records) == 2
    assert records[0]["ticker"] == "TSLA"
    assert records[1]["ticker"] == "AAPL"


# ---------------------------------------------------------------------------
# load_signal_history — corrupt / empty / missing file
# ---------------------------------------------------------------------------

def test_load_signal_history_returns_empty_when_file_missing(monkeypatch, tmp_path):
    """load_signal_history returns [] when signals_log.json does not exist."""
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", tmp_path / "signals_log.json")

    assert load_signal_history("AAPL") == []


def test_load_signal_history_returns_empty_when_file_empty(monkeypatch, tmp_path):
    """load_signal_history returns [] when signals_log.json is empty."""
    log_path = tmp_path / "signals_log.json"
    log_path.write_text("")
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    assert load_signal_history("AAPL") == []


def test_load_signal_history_returns_empty_when_invalid_json(monkeypatch, tmp_path):
    """load_signal_history returns [] when signals_log.json contains malformed JSON."""
    log_path = tmp_path / "signals_log.json"
    log_path.write_text("{not valid json")
    monkeypatch.setattr("analysis.ai_analyst._LOG_PATH", log_path)

    assert load_signal_history("AAPL") == []


# ---------------------------------------------------------------------------
# calibrate_signal — deterministic signal + confidence logic
# ---------------------------------------------------------------------------

def test_calibrate_signal_strong_bullish_returns_high():
    """Strong price-vs-MA deviations with above-average volume produce BULLISH/High.

    AAPL: +2.47% vs MA10, +5.80% vs MA20 — avg 4.14%, ABOVE AVERAGE volume.
    Thresholds: avg >= 3.0%, both > 1.0%, volume high → High.
    """
    summary = {
        "current_price": 213.45,
        "ma_10": 208.30,
        "ma_20": 201.75,
        "volume_signal": "ABOVE AVERAGE",
        "price_vs_ma10": "ABOVE",
        "price_vs_ma20": "ABOVE",
    }
    signal, confidence = calibrate_signal(summary)
    assert signal == "BULLISH"
    assert confidence == "High"


def test_calibrate_signal_neutral_band_returns_neutral():
    """Price within the 1.5% neutral band returns NEUTRAL regardless of volume.

    MSFT: -0.84% vs MA10, -1.19% vs MA20 — avg 1.02%, inside the 1.5% band.
    """
    summary = {
        "current_price": 415.00,
        "ma_10": 418.50,
        "ma_20": 420.00,
        "volume_signal": "AVERAGE",
        "price_vs_ma10": "BELOW",
        "price_vs_ma20": "BELOW",
    }
    signal, confidence = calibrate_signal(summary)
    assert signal == "NEUTRAL"


def test_calibrate_signal_mixed_ma_returns_neutral():
    """Price above MA10 but below MA20 returns NEUTRAL due to MA disagreement."""
    summary = {
        "current_price": 100.00,
        "ma_10": 97.00,   # price +3.09% above MA10
        "ma_20": 103.00,  # price -2.91% below MA20
        "volume_signal": "ABOVE AVERAGE",
        "price_vs_ma10": "ABOVE",
        "price_vs_ma20": "BELOW",
    }
    signal, confidence = calibrate_signal(summary)
    assert signal == "NEUTRAL"


def test_calibrate_signal_below_avg_volume_limits_confidence():
    """Strong bearish deviations with below-average volume cannot reach High confidence.

    TSLA: -3.60% vs MA10, -5.90% vs MA20 — avg 4.75%, BELOW AVERAGE volume.
    Avg exceeds High threshold but volume is not confirming, so at most Moderate.
    """
    summary = {
        "current_price": 178.92,
        "ma_10": 185.60,
        "ma_20": 190.14,
        "volume_signal": "BELOW AVERAGE",
        "price_vs_ma10": "BELOW",
        "price_vs_ma20": "BELOW",
    }
    signal, confidence = calibrate_signal(summary)
    assert signal == "BEARISH"
    assert confidence != "High"
