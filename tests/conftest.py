"""Project-wide pytest fixtures.

autouse fixtures here apply to every test automatically — no import needed.
"""

import pytest


_FAKE_ALPACA_ENV = {
    "APCA_API_KEY_ID": "fake_key_for_tests",
    "APCA_API_SECRET_KEY": "fake_secret_for_tests",
}


@pytest.fixture(autouse=True)
def alpaca_env(monkeypatch):
    """Inject fake Alpaca credentials so tests pass without a real .env file."""
    for key, value in _FAKE_ALPACA_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture(autouse=True)
def disable_password_gate(monkeypatch):
    """Force the API password gate off for every test by default.

    api/main.py reads APP_PASSWORD once at import time, so whatever is (or
    isn't) in the real .env would otherwise leak into every test run. Tests
    that specifically exercise the gate (TestPasswordGate) turn it back on
    with their own monkeypatch.setattr, which overrides this.
    """
    import api.main as mod
    monkeypatch.setattr(mod, "APP_PASSWORD", None)


@pytest.fixture(autouse=True)
def reset_alpaca_client():
    """Reset the TradingClient singleton before and after each test.

    Without this, a test that triggers client creation would leave a stale
    mock instance that contaminates the next test.
    """
    import trading.alpaca_client as mod
    mod._client = None
    yield
    mod._client = None


@pytest.fixture(autouse=True)
def isolate_trade_history(monkeypatch, tmp_path):
    """Redirect trade_history writes to a throwaway temp file for every test.

    _HISTORY_PATH is a module-level Path constant. Without this fixture, any
    test that reaches append_trade() (e.g. execute_signal success paths) would
    write phantom records into the real runtime trade_history.json.
    """
    import trading.trade_history as mod
    monkeypatch.setattr(mod, "_HISTORY_PATH", tmp_path / "trade_history_test.json")


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear the API rate limiter's in-memory storage before and after each test.

    The limiter is a module-level singleton keyed by client IP. Without this,
    hits from earlier tests against /signal or /discover would accumulate
    against the same TestClient "IP" and eventually trip a 429 in an
    unrelated test.
    """
    import api.main as mod
    mod.limiter.reset()
    yield
    mod.limiter.reset()


@pytest.fixture(autouse=True)
def isolate_portfolio_cache(monkeypatch, tmp_path):
    """Redirect portfolio cache writes to a throwaway temp file for every test.

    _CACHE_PATH is a module-level Path constant. Without this fixture, any
    test that reaches _write_cache() would overwrite the real runtime
    portfolio_state.json.
    """
    import portfolio.tracker as mod
    monkeypatch.setattr(mod, "_CACHE_PATH", tmp_path / "portfolio_state_test.json")
