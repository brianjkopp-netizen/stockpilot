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
