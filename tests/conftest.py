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
