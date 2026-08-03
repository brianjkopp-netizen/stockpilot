"""Tests for the StockPilot HTTP API (api/main.py) — all upstreams are mocked."""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from analysis.ai_analyst import SignalGenerationError
from api.main import app
from portfolio.recommender import RecommendationError
from trading.alpaca_client import AlpacaAuthError, AlpacaNetworkError, AlpacaOrderError

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

_FAKE_DF = MagicMock()

_FAKE_SUMMARY = {
    "current_price": 189.42,
    "ma_10": 185.23,
    "ma_20": 182.10,
    "volume_signal": "ABOVE AVERAGE",
    "price_vs_ma10": "ABOVE",
    "price_vs_ma20": "ABOVE",
}

_FAKE_SIGNAL = {
    "ticker": "AAPL",
    "signal": "BULLISH",
    "confidence": "High",
    "reasoning": "Price is above both MAs with strong volume.",
    "key_factors": ["Price > MA10", "Price > MA20", "Volume above average"],
}

_FAKE_POSITION = {
    "ticker": "AAPL",
    "qty": 50.0,
    "avg_entry_price": 182.40,
    "mark_price": 189.42,
    "market_value": 9471.0,
    "unrealized_pl": 351.0,
    "unrealized_plpc": 0.038,
    "daily_pl": 42.5,
    "daily_plpc": 0.005,
    "sparkline": [182.0, 184.0, 186.0, 188.0, 189.42],
}

_FAKE_PORTFOLIO = {
    "positions": [_FAKE_POSITION],
    "totals": {
        "market_value": 9471.0,
        "cost_basis": 9120.0,
        "unrealized_pl": 351.0,
        "unrealized_plpc": 0.038,
        "daily_pl": 42.5,
        "daily_plpc": 0.005,
    },
    "account": {
        "cash": 71240.18,
        "buying_power": 71240.18,
        "portfolio_value": 80711.18,
    },
    "fetched_at": "2026-07-16T12:00:00+00:00",
}

_FAKE_REC = {
    "ticker": "AAPL",
    "verdict": "HOLD",
    "brief": "Trend is intact above both MAs; continue holding.",
    "signal": "BULLISH",
    "confidence": "High",
    "placeable": True,
    "placeable_reason": None,
}

_FAKE_SCAN = {
    "ticker": "AAPL",
    "company_name": "Apple Inc.",
    "signal": "BULLISH",
    "confidence": "High",
    "price": 189.42,
    "drift_5d": 0.025,
    "sparkline": [182.0, 184.0, 186.0, 188.0, 189.42],
    "reasoning": "Strong momentum.",
    "_signal_obj": _FAKE_SIGNAL,
    "error": None,
}

_FAKE_ORDER = {
    "id": "abc123ef",
    "ticker": "AAPL",
    "side": "BUY",
    "qty": 2.6385,
    "status": "accepted",
    "submitted_at": "2026-07-16T12:00:00+00:00",
}

_FAKE_ACCOUNT = {
    "cash": 71240.18,
    "buying_power": 71240.18,
    "portfolio_value": 80711.18,
}


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_exempt_from_password_gate(self, monkeypatch):
        """APP_PASSWORD set, no header supplied — /health must still answer 200."""
        monkeypatch.setattr("api.main.APP_PASSWORD", "letmein")
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# GET /signal/{ticker}
# ---------------------------------------------------------------------------

class TestSignalEndpoint:
    @patch("api.main.get_signal", return_value=_FAKE_SIGNAL)
    @patch("api.main.get_summary", return_value=_FAKE_SUMMARY)
    @patch("api.main.add_volume_signal", side_effect=lambda df: df)
    @patch("api.main.add_moving_averages", side_effect=lambda df, w: df)
    @patch("api.main.get_stock_data", return_value=_FAKE_DF)
    def test_success_returns_full_schema(self, *_):
        resp = client.get("/signal/AAPL")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("ticker", "signal", "confidence", "reasoning", "key_factors",
                    "price", "ma_10", "ma_20", "volume_signal"):
            assert key in body, f"Missing key in response: {key}"
        assert body["signal"] == "BULLISH"
        assert body["confidence"] == "High"
        assert body["price"] == 189.42

    @patch("api.main.get_stock_data", side_effect=ValueError("No data for ZZZZ"))
    def test_invalid_ticker_returns_422(self, _):
        resp = client.get("/signal/ZZZZ")
        assert resp.status_code == 422

    @patch("api.main.get_signal", side_effect=SignalGenerationError("AAPL", "Anthropic timeout"))
    @patch("api.main.get_summary", return_value=_FAKE_SUMMARY)
    @patch("api.main.add_volume_signal", side_effect=lambda df: df)
    @patch("api.main.add_moving_averages", side_effect=lambda df, w: df)
    @patch("api.main.get_stock_data", return_value=_FAKE_DF)
    def test_ai_failure_returns_502(self, *_):
        resp = client.get("/signal/AAPL")
        assert resp.status_code == 502

    @patch("api.main.get_stock_data", side_effect=ConnectionError("no internet"))
    def test_network_error_returns_503(self, _):
        resp = client.get("/signal/AAPL")
        assert resp.status_code == 503

    @patch("api.main.get_stock_data", side_effect=ConnectionError("Failed to connect to internal.host:5432"))
    def test_network_error_does_not_leak_exception_text(self, _):
        """A forced upstream error must return a generic message, not the raw exception."""
        resp = client.get("/signal/AAPL")
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "internal.host" not in detail
        assert detail == "Upstream data provider unavailable"

    @patch("api.main.get_signal", side_effect=SignalGenerationError("AAPL", "sk-ant-secret-leak"))
    @patch("api.main.get_summary", return_value=_FAKE_SUMMARY)
    @patch("api.main.add_volume_signal", side_effect=lambda df: df)
    @patch("api.main.add_moving_averages", side_effect=lambda df, w: df)
    @patch("api.main.get_stock_data", return_value=_FAKE_DF)
    def test_ai_failure_does_not_leak_exception_text(self, *_):
        resp = client.get("/signal/AAPL")
        assert resp.status_code == 502
        detail = resp.json()["detail"]
        assert "sk-ant-secret-leak" not in detail
        assert detail == "AI signal generation failed"

    @patch("api.main.get_signal", return_value=_FAKE_SIGNAL)
    @patch("api.main.get_summary", return_value=_FAKE_SUMMARY)
    @patch("api.main.add_volume_signal", side_effect=lambda df: df)
    @patch("api.main.add_moving_averages", side_effect=lambda df, w: df)
    @patch("api.main.get_stock_data", return_value=_FAKE_DF)
    def test_days_query_param_is_forwarded(self, mock_gsd, *_):
        client.get("/signal/AAPL?days=60")
        mock_gsd.assert_called_once_with("AAPL", 60)

    def test_days_out_of_range_returns_422(self):
        assert client.get("/signal/AAPL?days=0").status_code == 422
        assert client.get("/signal/AAPL?days=366").status_code == 422


# ---------------------------------------------------------------------------
# GET /signals
# ---------------------------------------------------------------------------

class TestSignalsEndpoint:
    @patch("api.main.load_all_signals", return_value=[
        {"timestamp": "2026-07-16T12:00:00+00:00", **_FAKE_SIGNAL, "price": 189.42},
        {"timestamp": "2026-07-16T13:00:00+00:00", **_FAKE_SIGNAL, "price": 190.10},
    ])
    def test_success_returns_most_recent_first(self, _):
        resp = client.get("/signals")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["records"][0]["timestamp"] == "2026-07-16T13:00:00+00:00"
        assert body["records"][1]["timestamp"] == "2026-07-16T12:00:00+00:00"

    @patch("api.main.load_all_signals", return_value=[])
    def test_empty_log_returns_zero_records(self, _):
        resp = client.get("/signals")
        assert resp.status_code == 200
        assert resp.json() == {"records": [], "total": 0}


# ---------------------------------------------------------------------------
# GET /portfolio
# ---------------------------------------------------------------------------

class TestPortfolioEndpoint:
    @patch("api.main.get_portfolio_state", return_value=_FAKE_PORTFOLIO)
    def test_success_returns_full_schema(self, _):
        resp = client.get("/portfolio")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("positions", "totals", "account", "fetched_at"):
            assert key in body, f"Missing key: {key}"
        assert body["positions"][0]["ticker"] == "AAPL"
        assert "portfolio_value" in body["account"]

    @patch("api.main.get_portfolio_state", side_effect=AlpacaAuthError("bad creds"))
    def test_auth_error_returns_503(self, _):
        resp = client.get("/portfolio")
        assert resp.status_code == 503

    @patch("api.main.get_portfolio_state", side_effect=AlpacaNetworkError("timeout"))
    def test_network_error_returns_503(self, _):
        resp = client.get("/portfolio")
        assert resp.status_code == 503

    @patch("api.main.get_portfolio_state", side_effect=AlpacaNetworkError("connect to 10.0.0.5:443 refused"))
    def test_network_error_does_not_leak_exception_text(self, _):
        resp = client.get("/portfolio")
        detail = resp.json()["detail"]
        assert "10.0.0.5" not in detail
        assert detail == "Portfolio data unavailable"

    def test_stale_quote_position_passes_through_as_null_not_fabricated(self):
        """A position with a stale live quote surfaces null fields and quote_stale, and totals.partial is set."""
        stale_position = {
            **_FAKE_POSITION,
            "mark_price": None,
            "daily_pl": None,
            "daily_plpc": None,
            "sparkline": [],
            "quote_stale": True,
        }
        stale_portfolio = {
            **_FAKE_PORTFOLIO,
            "positions": [stale_position],
            "totals": {**_FAKE_PORTFOLIO["totals"], "daily_pl": 0.0, "daily_plpc": 0.0, "partial": True},
        }
        with patch("api.main.get_portfolio_state", return_value=stale_portfolio):
            resp = client.get("/portfolio")

        assert resp.status_code == 200
        body = resp.json()
        position = body["positions"][0]
        assert position["quote_stale"] is True
        assert position["mark_price"] is None
        assert position["daily_pl"] is None
        assert position["daily_plpc"] is None
        assert body["totals"]["partial"] is True


# ---------------------------------------------------------------------------
# GET /portfolio/{ticker}/recommendation
# ---------------------------------------------------------------------------

class TestRecommendationEndpoint:
    @patch("api.main.get_recommendation", return_value=_FAKE_REC)
    @patch("api.main.get_portfolio_state", return_value=_FAKE_PORTFOLIO)
    def test_success_returns_full_schema(self, *_):
        resp = client.get("/portfolio/AAPL/recommendation")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("ticker", "verdict", "brief", "signal", "confidence", "placeable", "placeable_reason"):
            assert key in body, f"Missing key: {key}"
        assert body["verdict"] in ("HOLD", "ADD", "SELL")

    @patch("api.main.get_portfolio_state", return_value=_FAKE_PORTFOLIO)
    def test_missing_ticker_returns_404(self, _):
        resp = client.get("/portfolio/ZZZZ/recommendation")
        assert resp.status_code == 404

    @patch("api.main.get_recommendation", side_effect=RecommendationError("AAPL", "API down"))
    @patch("api.main.get_portfolio_state", return_value=_FAKE_PORTFOLIO)
    def test_rec_failure_returns_502(self, *_):
        resp = client.get("/portfolio/AAPL/recommendation")
        assert resp.status_code == 502

    @patch("api.main.get_portfolio_state", side_effect=AlpacaAuthError("bad creds"))
    def test_alpaca_failure_returns_503(self, _):
        resp = client.get("/portfolio/AAPL/recommendation")
        assert resp.status_code == 503

    @patch("api.main.get_recommendation", side_effect=RecommendationError("AAPL", "sk-ant-secret-leak"))
    @patch("api.main.get_portfolio_state", return_value=_FAKE_PORTFOLIO)
    def test_rec_failure_does_not_leak_exception_text(self, *_):
        resp = client.get("/portfolio/AAPL/recommendation")
        detail = resp.json()["detail"]
        assert "sk-ant-secret-leak" not in detail
        assert detail == "Recommendation generation failed"

    @patch("api.main.get_recommendation", side_effect=ValueError("AAPL: live quote is stale"))
    @patch("api.main.get_portfolio_state", return_value=_FAKE_PORTFOLIO)
    def test_stale_quote_recommendation_returns_503(self, *_):
        """A stale-quote position (mark_price None) can't be recommended against — 503, not a 500 crash."""
        resp = client.get("/portfolio/AAPL/recommendation")
        assert resp.status_code == 503


# ---------------------------------------------------------------------------
# GET /discover
# ---------------------------------------------------------------------------

class TestDiscoverEndpoint:
    @patch("api.main.scan_ticker", return_value=_FAKE_SCAN)
    @patch("api.main._load_watchlist", return_value=["AAPL"])
    def test_success_returns_full_schema(self, *_):
        resp = client.get("/discover")
        assert resp.status_code == 200
        body = resp.json()
        for key in ("results", "counts", "total", "scanned_at"):
            assert key in body, f"Missing key: {key}"
        assert body["total"] == 1
        result = body["results"][0]
        for key in ("ticker", "signal", "confidence", "price", "drift_5d", "sparkline", "reasoning"):
            assert key in result, f"Missing key in result: {key}"

    @patch("api.main.scan_ticker", return_value=_FAKE_SCAN)
    @patch("api.main._load_watchlist", return_value=["AAPL"])
    def test_signal_obj_stripped_from_results(self, *_):
        resp = client.get("/discover")
        body = resp.json()
        assert "_signal_obj" not in body["results"][0]

    @patch("api.main._load_watchlist", return_value=[])
    def test_empty_watchlist_returns_zero_results(self, _):
        resp = client.get("/discover")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["results"] == []

    @patch("api.main.scan_ticker", side_effect=lambda t, d: {**_FAKE_SCAN, "signal": "BULLISH"})
    @patch("api.main._load_watchlist", return_value=["AAPL", "NVDA"])
    def test_counts_are_tallied(self, *_):
        resp = client.get("/discover")
        assert resp.json()["counts"]["BULLISH"] == 2

    def test_days_out_of_range_returns_422(self):
        assert client.get("/discover?days=0").status_code == 422
        assert client.get("/discover?days=366").status_code == 422


# ---------------------------------------------------------------------------
# GET /watchlist · POST /watchlist · DELETE /watchlist/{ticker}
# ---------------------------------------------------------------------------

class TestWatchlistEndpoints:
    def test_get_watchlist_returns_schema(self, tmp_path, monkeypatch):
        wl = tmp_path / "watchlist.json"
        wl.write_text(json.dumps(["AAPL", "NVDA"]))
        monkeypatch.setattr("api.main._WATCHLIST_PATH", wl)
        resp = client.get("/watchlist")
        assert resp.status_code == 200
        assert resp.json() == {"tickers": ["AAPL", "NVDA"]}

    def test_add_ticker_appends_and_uppercases(self, tmp_path, monkeypatch):
        wl = tmp_path / "watchlist.json"
        wl.write_text(json.dumps(["AAPL"]))
        monkeypatch.setattr("api.main._WATCHLIST_PATH", wl)
        resp = client.post("/watchlist", json={"ticker": "nvda"})
        assert resp.status_code == 200
        tickers = resp.json()["tickers"]
        assert "NVDA" in tickers
        assert "AAPL" in tickers

    def test_add_ticker_idempotent(self, tmp_path, monkeypatch):
        wl = tmp_path / "watchlist.json"
        wl.write_text(json.dumps(["AAPL"]))
        monkeypatch.setattr("api.main._WATCHLIST_PATH", wl)
        client.post("/watchlist", json={"ticker": "AAPL"})
        resp = client.post("/watchlist", json={"ticker": "AAPL"})
        assert resp.json()["tickers"].count("AAPL") == 1

    def test_remove_ticker(self, tmp_path, monkeypatch):
        wl = tmp_path / "watchlist.json"
        wl.write_text(json.dumps(["AAPL", "NVDA"]))
        monkeypatch.setattr("api.main._WATCHLIST_PATH", wl)
        resp = client.delete("/watchlist/AAPL")
        assert resp.status_code == 200
        tickers = resp.json()["tickers"]
        assert "AAPL" not in tickers
        assert "NVDA" in tickers

    def test_remove_absent_ticker_is_noop(self, tmp_path, monkeypatch):
        wl = tmp_path / "watchlist.json"
        wl.write_text(json.dumps(["AAPL"]))
        monkeypatch.setattr("api.main._WATCHLIST_PATH", wl)
        resp = client.delete("/watchlist/ZZZZ")
        assert resp.status_code == 200
        assert resp.json()["tickers"] == ["AAPL"]


# ---------------------------------------------------------------------------
# POST /orders
# ---------------------------------------------------------------------------

class TestOrdersEndpoint:
    @patch("api.main.place_buy_order", return_value=_FAKE_ORDER)
    @patch("api.main.get_account_info", return_value=_FAKE_ACCOUNT)
    @patch("api.main.get_latest_price", return_value=189.42)
    def test_buy_order_success(self, *_):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "buy",
            "signal": "BULLISH",
            "confidence": "High",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["placed"] is True
        assert body["order"]["ticker"] == "AAPL"

    @patch("api.main.place_sell_order", return_value={**_FAKE_ORDER, "side": "SELL"})
    def test_sell_order_success(self, _):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "sell",
            "qty": 10.0,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["placed"] is True

    def test_neutral_signal_returns_not_placed(self):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "buy",
            "signal": "NEUTRAL",
            "confidence": "Moderate",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["placed"] is False
        assert body["order"] is None

    @patch("api.main.get_latest_price", return_value=189.42)
    @patch("api.main.get_account_info", return_value={**_FAKE_ACCOUNT, "buying_power": 0.01})
    def test_insufficient_buying_power_returns_not_placed(self, *_):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "buy",
            "signal": "BULLISH",
            "confidence": "High",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["placed"] is False

    def test_invalid_side_returns_422(self):
        resp = client.post("/orders", json={"ticker": "AAPL", "side": "short"})
        assert resp.status_code == 422

    def test_sell_without_qty_returns_422(self):
        resp = client.post("/orders", json={"ticker": "AAPL", "side": "sell"})
        assert resp.status_code == 422

    def test_buy_without_signal_returns_422(self):
        resp = client.post("/orders", json={"ticker": "AAPL", "side": "buy"})
        assert resp.status_code == 422

    @patch("api.main.get_latest_price", side_effect=AlpacaAuthError("bad creds"))
    def test_auth_error_returns_503(self, _):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "buy",
            "signal": "BULLISH",
            "confidence": "High",
        })
        assert resp.status_code == 503

    @patch("api.main.place_sell_order", side_effect=AlpacaOrderError("SELL", "AAPL", "rejected"))
    def test_order_rejected_returns_502(self, _):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "sell",
            "qty": 5.0,
        })
        assert resp.status_code == 502

    @patch("api.main.place_sell_order", side_effect=AlpacaOrderError("SELL", "AAPL", "insufficient qty available: acct #12345"))
    def test_order_rejected_does_not_leak_exception_text(self, _):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "sell",
            "qty": 5.0,
        })
        detail = resp.json()["detail"]
        assert "acct #12345" not in detail
        assert detail == "Order could not be placed"

    @patch("api.main.get_latest_price", side_effect=ConnectionError("Failed to fetch price for 'AAPL': timeout at 10.0.0.9"))
    def test_market_data_network_error_returns_503_without_leak(self, _):
        resp = client.post("/orders", json={
            "ticker": "AAPL",
            "side": "buy",
            "signal": "BULLISH",
            "confidence": "High",
        })
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "10.0.0.9" not in detail
        assert detail == "Market data unavailable"


# ---------------------------------------------------------------------------
# Password gate (require_password dependency)
# ---------------------------------------------------------------------------

class TestPasswordGate:
    @patch("api.main.load_all_signals", return_value=[])
    def test_gate_off_allows_request_without_header(self, _):
        """APP_PASSWORD unset (the default/test/local-dev state) — no header needed."""
        resp = client.get("/signals")
        assert resp.status_code == 200

    @patch("api.main.load_all_signals", return_value=[])
    def test_gate_on_rejects_missing_header(self, _, monkeypatch):
        monkeypatch.setattr("api.main.APP_PASSWORD", "letmein")
        resp = client.get("/signals")
        assert resp.status_code == 401

    @patch("api.main.load_all_signals", return_value=[])
    def test_gate_on_rejects_wrong_password(self, _, monkeypatch):
        monkeypatch.setattr("api.main.APP_PASSWORD", "letmein")
        resp = client.get("/signals", headers={"X-App-Password": "wrong"})
        assert resp.status_code == 401

    @patch("api.main.load_all_signals", return_value=[])
    def test_gate_on_accepts_correct_password(self, _, monkeypatch):
        monkeypatch.setattr("api.main.APP_PASSWORD", "letmein")
        resp = client.get("/signals", headers={"X-App-Password": "letmein"})
        assert resp.status_code == 200

    def test_gate_on_still_answers_cors_preflight(self, monkeypatch):
        """CORSMiddleware must answer OPTIONS itself, before require_password runs."""
        monkeypatch.setattr("api.main.APP_PASSWORD", "letmein")
        resp = client.options(
            "/signals",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert resp.status_code == 200
        assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"


# ---------------------------------------------------------------------------
# Docs gate (_docs_enabled / docs_url, redoc_url, openapi_url)
# ---------------------------------------------------------------------------

class TestDocsGate:
    def test_docs_enabled_by_default(self):
        """APP_ENV unset (the default/test/local-dev state) — docs stay on."""
        from api.main import _docs_enabled
        assert _docs_enabled() is True

    def test_docs_disabled_in_production(self, monkeypatch):
        from api.main import _docs_enabled
        monkeypatch.setenv("APP_ENV", "production")
        assert _docs_enabled() is False

    def test_docs_disabled_is_case_insensitive(self, monkeypatch):
        from api.main import _docs_enabled
        monkeypatch.setenv("APP_ENV", "Production")
        assert _docs_enabled() is False

    def test_docs_enabled_for_other_app_env_values(self, monkeypatch):
        from api.main import _docs_enabled
        monkeypatch.setenv("APP_ENV", "development")
        assert _docs_enabled() is True

    def test_docs_routes_reachable_in_test_env(self):
        """The module-level app is built once at import time with docs on,
        since the test process never sets APP_ENV=production."""
        assert client.get("/docs").status_code == 200
        assert client.get("/redoc").status_code == 200
        assert client.get("/openapi.json").status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting (/signal, /discover) — SP-49
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_defaults_are_configured_and_discover_is_tighter_than_signal(self):
        from api.main import _signal_rate_limit, _discover_rate_limit

        signal_count = int(_signal_rate_limit().split("/")[0])
        discover_count = int(_discover_rate_limit().split("/")[0])
        assert discover_count < signal_count

    @patch("api.main.get_signal", return_value=_FAKE_SIGNAL)
    @patch("api.main.get_summary", return_value=_FAKE_SUMMARY)
    @patch("api.main.add_volume_signal", side_effect=lambda df: df)
    @patch("api.main.add_moving_averages", side_effect=lambda df, w: df)
    @patch("api.main.get_stock_data", return_value=_FAKE_DF)
    def test_signal_returns_429_after_threshold(self, _m1, _m2, _m3, _m4, _m5, monkeypatch):
        monkeypatch.setenv("SIGNAL_RATE_LIMIT", "2/minute")

        assert client.get("/signal/AAPL").status_code == 200
        assert client.get("/signal/AAPL").status_code == 200
        resp = client.get("/signal/AAPL")
        assert resp.status_code == 429
        assert "detail" in resp.json()
        assert "rate limit" in resp.json()["detail"].lower()

    @patch("api.main.scan_ticker", return_value=_FAKE_SCAN)
    @patch("api.main._load_watchlist", return_value=["AAPL"])
    def test_discover_returns_429_after_threshold(self, _m1, _m2, monkeypatch):
        monkeypatch.setenv("DISCOVER_RATE_LIMIT", "2/minute")

        assert client.get("/discover").status_code == 200
        assert client.get("/discover").status_code == 200
        resp = client.get("/discover")
        assert resp.status_code == 429
        assert "detail" in resp.json()

    @patch("api.main.scan_ticker", return_value=_FAKE_SCAN)
    @patch("api.main._load_watchlist", return_value=["AAPL"])
    def test_limit_is_keyed_per_client_ip(self, _m1, _m2, monkeypatch):
        """Two different X-Forwarded-For callers get independent budgets."""
        monkeypatch.setenv("DISCOVER_RATE_LIMIT", "1/minute")

        assert client.get("/discover", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
        assert client.get("/discover", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
        assert client.get("/discover", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200

    def test_client_ip_prefers_first_forwarded_hop(self):
        from api.main import _client_ip

        req = MagicMock()
        req.headers = {"x-forwarded-for": "9.9.9.9, 10.0.0.1"}
        assert _client_ip(req) == "9.9.9.9"

    def test_client_ip_falls_back_to_socket_peer_without_proxy(self):
        from api.main import _client_ip

        req = MagicMock()
        req.headers = {}
        req.client.host = "127.0.0.1"
        assert _client_ip(req) == "127.0.0.1"
