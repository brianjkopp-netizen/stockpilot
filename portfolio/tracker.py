"""Portfolio state tracker for StockPilot.

Fetches live positions and account state from Alpaca, marks each position to
market using a live yfinance price, and caches the result to
portfolio_state.json. Provides a read-only fallback from the cache when
Alpaca is unreachable. The live fetch is always preferred — the cache
is never trusted when the API can be reached.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from analysis.discover import compute_sparkline
from data.fetcher import get_stock_data
from trading.alpaca_client import AlpacaNetworkError, get_account_info, get_positions

_CACHE_PATH = Path(__file__).parent.parent / "portfolio_state.json"

# Calendar days of history pulled per ticker to derive a live mark, the prior
# session's close, and a 14-trading-day sparkline without over-fetching.
_QUOTE_HISTORY_DAYS = 30
_SPARKLINE_DAYS = 14

logging.basicConfig(
    format="%(asctime)s [tracker] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
_log = logging.getLogger(__name__)


def _fetch_live_quote(ticker: str) -> tuple[float, float, list[float]]:
    """Fetch a live mark price, the prior session's close, and a sparkline for a ticker.

    Returns:
        (mark_price, prior_close, sparkline). mark_price/prior_close are both
        positive floats — if only one trading day of history is available,
        prior_close equals mark_price so daily P&L computes to zero rather
        than raising. sparkline is the trailing _SPARKLINE_DAYS closes
        (oldest first, per analysis.discover.compute_sparkline).

    Raises:
        ValueError: If the ticker has no price data.
        ConnectionError: If yfinance is unreachable.
    """
    df = get_stock_data(ticker, days=_QUOTE_HISTORY_DAYS)
    closes = df["Close"].dropna().tolist()
    mark_price = closes[-1]
    prior_close = closes[-2] if len(closes) >= 2 else mark_price
    sparkline = compute_sparkline(closes, _SPARKLINE_DAYS)
    return mark_price, prior_close, sparkline


def _mark_to_market(position: dict) -> dict:
    """Mark a single Alpaca position to a live yfinance price.

    Recomputes market_value, unrealized_pl, and unrealized_plpc from the live
    mark against avg_entry_price (rather than trusting Alpaca's own bundled
    quote), and adds daily_pl / daily_plpc — the change since the prior
    session's close — plus a 14-day sparkline. Falls back to Alpaca's
    reported figures with zero daily P&L and an empty sparkline if yfinance
    is unreachable for this ticker.

    Returns:
        A new dict — the input position plus mark_price, daily_pl, daily_plpc,
        sparkline, with market_value/unrealized_pl/unrealized_plpc overridden
        when a live quote was available.
    """
    ticker = position["ticker"]
    qty = position["qty"]
    avg_entry = position["avg_entry_price"]

    try:
        mark_price, prior_close, sparkline = _fetch_live_quote(ticker)
    except (ValueError, ConnectionError) as exc:
        _log.warning(
            "Live quote unavailable for %s (%s) — using Alpaca-reported figures", ticker, exc
        )
        return {
            **position,
            "mark_price": position["avg_entry_price"],
            "daily_pl": 0.0,
            "daily_plpc": 0.0,
            "sparkline": [],
        }

    market_value = mark_price * qty
    unrealized_pl = (mark_price - avg_entry) * qty
    unrealized_plpc = (mark_price - avg_entry) / avg_entry if avg_entry else 0.0
    daily_pl = (mark_price - prior_close) * qty
    daily_plpc = (mark_price - prior_close) / prior_close if prior_close else 0.0

    return {
        **position,
        "mark_price": mark_price,
        "market_value": market_value,
        "unrealized_pl": unrealized_pl,
        "unrealized_plpc": unrealized_plpc,
        "daily_pl": daily_pl,
        "daily_plpc": daily_plpc,
        "sparkline": sparkline,
    }


def _compute_totals(positions: list[dict]) -> dict:
    """Aggregate per-position mark-to-market figures into portfolio-level totals.

    Returns:
        Dict with keys: market_value, cost_basis, unrealized_pl,
        unrealized_plpc, daily_pl, daily_plpc. All zero when positions is empty.
    """
    market_value = sum(p["market_value"] for p in positions)
    cost_basis = sum(p["avg_entry_price"] * p["qty"] for p in positions)
    unrealized_pl = sum(p["unrealized_pl"] for p in positions)
    daily_pl = sum(p["daily_pl"] for p in positions)
    prior_value = market_value - daily_pl

    return {
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pl": unrealized_pl,
        "unrealized_plpc": unrealized_pl / cost_basis if cost_basis else 0.0,
        "daily_pl": daily_pl,
        "daily_plpc": daily_pl / prior_value if prior_value else 0.0,
    }


def refresh_portfolio_state() -> dict:
    """Fetch live positions and account state from Alpaca and cache locally.

    Always calls the Alpaca API. Marks every position to a live yfinance price
    (see _mark_to_market) and aggregates portfolio-level totals before
    caching. Overwrites portfolio_state.json on every successful fetch.
    Raises rather than falling back to the cache — callers that want the
    fallback should catch AlpacaAuthError and call load_portfolio_state()
    themselves.

    Returns:
        Dict with keys:
            positions  — list of position dicts, each with ticker, qty,
                         avg_entry_price, mark_price, market_value,
                         unrealized_pl, unrealized_plpc, daily_pl, daily_plpc,
                         sparkline (list of trailing 14 daily closes)
            totals     — dict aggregating the above across all positions
                         (see _compute_totals)
            account    — dict with cash, buying_power, portfolio_value (floats)
            fetched_at — ISO-8601 UTC timestamp string

    Raises:
        AlpacaAuthError: If Alpaca credentials are missing or the API call fails.
    """
    positions = [_mark_to_market(p) for p in get_positions()]
    account = get_account_info()

    state = {
        "positions": positions,
        "totals": _compute_totals(positions),
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
        AlpacaAuthError: If Alpaca rejects the credentials (do not fall back — surfaced immediately).
        RuntimeError: If the API is unreachable and no cache is available.
    """
    try:
        return refresh_portfolio_state()
    except AlpacaNetworkError as exc:
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
            day_sign = "+" if p["daily_pl"] >= 0 else ""
            print(
                f"  {p['ticker']:<6}  qty={p['qty']:.4f}  "
                f"avg_entry=${p['avg_entry_price']:.2f}  mark=${p['mark_price']:.2f}  "
                f"market_value=${p['market_value']:,.2f}  "
                f"unrealized_pl={pl_sign}{p['unrealized_pl']:.2f} ({p['unrealized_plpc']*100:+.2f}%)  "
                f"daily_pl={day_sign}{p['daily_pl']:.2f} ({p['daily_plpc']*100:+.2f}%)"
            )

        totals = state["totals"]
        t_pl_sign = "+" if totals["unrealized_pl"] >= 0 else ""
        t_day_sign = "+" if totals["daily_pl"] >= 0 else ""
        print("\nTotals:")
        print(f"  market_value    : ${totals['market_value']:>12,.2f}")
        print(
            f"  unrealized_pl   : {t_pl_sign}${totals['unrealized_pl']:,.2f} "
            f"({totals['unrealized_plpc']*100:+.2f}%)"
        )
        print(
            f"  daily_pl        : {t_day_sign}${totals['daily_pl']:,.2f} "
            f"({totals['daily_plpc']*100:+.2f}%)"
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
