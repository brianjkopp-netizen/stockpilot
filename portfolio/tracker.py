"""Portfolio state tracker for StockPilot.

Fetches live positions and account state from Alpaca, caches them to
portfolio_state.json, and provides a read-only fallback from the cache
when Alpaca is unreachable. The live fetch is always preferred — the cache
is never trusted when the API can be reached.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from trading.alpaca_client import AlpacaAuthError, get_account_info, get_positions

_CACHE_PATH = Path(__file__).parent.parent / "portfolio_state.json"

logging.basicConfig(
    format="%(asctime)s [tracker] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
_log = logging.getLogger(__name__)


def refresh_portfolio_state() -> dict:
    """Fetch live positions and account state from Alpaca and cache locally.

    Always calls the Alpaca API. Overwrites portfolio_state.json on every
    successful fetch. Raises rather than falling back to the cache — callers
    that want the fallback should catch AlpacaAuthError and call
    load_portfolio_state() themselves.

    Returns:
        Dict with keys:
            positions  — list of position dicts (see get_positions schema)
            account    — dict with cash, buying_power, portfolio_value (floats)
            fetched_at — ISO-8601 UTC timestamp string

    Raises:
        AlpacaAuthError: If Alpaca credentials are missing or the API call fails.
    """
    positions = get_positions()
    account = get_account_info()

    state = {
        "positions": positions,
        "account": account,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    _write_cache(state)
    _log.info(
        "Portfolio state refreshed — %d position(s)  portfolio_value=$%.2f",
        len(positions),
        account["portfolio_value"],
    )
    return state


def load_portfolio_state() -> Optional[dict]:
    """Load the cached portfolio state from portfolio_state.json.

    Use this only when Alpaca is unreachable. The cache may be minutes or
    hours old. Always call refresh_portfolio_state() first when the API is up.

    Returns:
        Cached state dict (same schema as refresh_portfolio_state), or None if
        no cache file exists or the file cannot be parsed.
    """
    if not _CACHE_PATH.exists():
        _log.warning("No portfolio cache found at %s", _CACHE_PATH)
        return None

    try:
        with _CACHE_PATH.open() as f:
            state = json.load(f)
        _log.info("Loaded cached portfolio state from %s", _CACHE_PATH)
        return state
    except (json.JSONDecodeError, OSError) as exc:
        _log.error("Failed to read portfolio cache: %s", exc)
        return None


def get_portfolio_state() -> dict:
    """Return portfolio state, preferring a live Alpaca fetch over the cache.

    Tries the live API first. Falls back to the on-disk cache only when the
    API is unreachable. Raises if both sources fail.

    Returns:
        Dict with keys: positions (list), account (dict), fetched_at (str).
        When returning from cache, also includes source="cache".

    Raises:
        RuntimeError: If the API is unreachable and no cache is available.
    """
    try:
        return refresh_portfolio_state()
    except AlpacaAuthError as exc:
        _log.warning("Alpaca unreachable (%s) — trying local cache", exc)

    cached = load_portfolio_state()
    if cached is None:
        raise RuntimeError(
            "Alpaca API is unreachable and no local portfolio cache exists. "
            "Connect to the internet and ensure your .env credentials are set."
        )

    cached["source"] = "cache"
    return cached


def _write_cache(state: dict) -> None:
    """Serialise state to portfolio_state.json."""
    with _CACHE_PATH.open("w") as f:
        json.dump(state, f, indent=2)
    _log.info("Portfolio state written to %s", _CACHE_PATH)


if __name__ == "__main__":
    print("=== Portfolio state smoke test ===\n")

    state = get_portfolio_state()

    account = state["account"]
    print("Account:")
    print(f"  cash            : ${account['cash']:>12,.2f}")
    print(f"  buying_power    : ${account['buying_power']:>12,.2f}")
    print(f"  portfolio_value : ${account['portfolio_value']:>12,.2f}")

    positions = state["positions"]
    print(f"\nOpen positions ({len(positions)}):")
    if positions:
        for p in positions:
            pl_sign = "+" if p["unrealized_pl"] >= 0 else ""
            print(
                f"  {p['ticker']:<6}  qty={p['qty']:.4f}  "
                f"avg_entry=${p['avg_entry_price']:.2f}  "
                f"market_value=${p['market_value']:,.2f}  "
                f"unrealized_pl={pl_sign}{p['unrealized_pl']:.2f}"
            )
    else:
        print("  (no open positions)")

    source = state.get("source", "live")
    print(f"\nData source  : {source}")
    print(f"Fetched at   : {state['fetched_at']}")

    if source == "live":
        cached = load_portfolio_state()
        assert cached is not None, "Cache write failed — portfolio_state.json not readable"
        assert cached["fetched_at"] == state["fetched_at"], "Cache content mismatch"
        print("Cache write  : OK")

    print("\nSmoke test passed.")
