"""Portfolio state tracker for StockPilot.

Fetches live positions and account state from Alpaca, marks each position to
market using a live yfinance price, and caches the result to
portfolio_state.json. Provides a read-only fallback from the cache when
Alpaca is unreachable. The live fetch is always preferred — the cache
is never trusted when the API can be reached.

Also houses the per-position recommendation engine (HOLD / ADD / SELL):
the verdict is computed deterministically from technical indicators and the
position's P&L (see calibrate_recommendation), and the Anthropic model is
used only to write a short plain-English brief explaining that verdict —
same discipline as analysis.ai_analyst.calibrate_signal.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic

from analysis.ai_analyst import calibrate_signal
from analysis.indicators import build_analysis_summary
from data.fetcher import get_stock_data
from trading.alpaca_client import AlpacaNetworkError, get_account_info, get_positions

_CACHE_PATH = Path(__file__).parent.parent / "portfolio_state.json"

# Trading days of history pulled per ticker to derive a live mark and the
# prior session's close. 5 covers weekends/holidays without over-fetching.
_QUOTE_HISTORY_DAYS = 5

# Calendar days of history pulled to compute indicators for the rec engine —
# matches the default used on the Signal screen (indicators.build_analysis_summary
# needs enough history for a 20-day moving average).
_INDICATOR_HISTORY_DAYS = 30

# A position at or above this unrealized P&L fraction is "not losing" for
# recommendation purposes. 0.0 means any red position counts as losing.
_LOSS_BAND_PCT = 0.0

logging.basicConfig(
    format="%(asctime)s [tracker] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
_log = logging.getLogger(__name__)


class RecommendationError(Exception):
    """Raised when the Anthropic API call in get_recommendation fails."""

    def __init__(self, ticker: str, message: str) -> None:
        super().__init__(f"[{ticker}] {message}")
        self.ticker = ticker


def _fetch_live_quote(ticker: str) -> tuple[float, float]:
    """Fetch a live mark price and the prior session's close for a ticker.

    Returns:
        (mark_price, prior_close) — both positive floats. If only one trading
        day of history is available, prior_close equals mark_price so daily
        P&L computes to zero rather than raising.

    Raises:
        ValueError: If the ticker has no price data.
        ConnectionError: If yfinance is unreachable.
    """
    df = get_stock_data(ticker, days=_QUOTE_HISTORY_DAYS)
    closes = df["Close"].dropna()
    mark_price = float(closes.iloc[-1])
    prior_close = float(closes.iloc[-2]) if len(closes) >= 2 else mark_price
    return mark_price, prior_close


def _mark_to_market(position: dict) -> dict:
    """Mark a single Alpaca position to a live yfinance price.

    Recomputes market_value, unrealized_pl, and unrealized_plpc from the live
    mark against avg_entry_price (rather than trusting Alpaca's own bundled
    quote), and adds daily_pl / daily_plpc — the change since the prior
    session's close. Falls back to Alpaca's reported figures with zero daily
    P&L if yfinance is unreachable for this ticker.

    Returns:
        A new dict — the input position plus mark_price, daily_pl, daily_plpc,
        with market_value/unrealized_pl/unrealized_plpc overridden when a live
        quote was available.
    """
    ticker = position["ticker"]
    qty = position["qty"]
    avg_entry = position["avg_entry_price"]

    try:
        mark_price, prior_close = _fetch_live_quote(ticker)
    except (ValueError, ConnectionError) as exc:
        _log.warning(
            "Live quote unavailable for %s (%s) — using Alpaca-reported figures", ticker, exc
        )
        return {**position, "mark_price": position["avg_entry_price"], "daily_pl": 0.0, "daily_plpc": 0.0}

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
                         unrealized_pl, unrealized_plpc, daily_pl, daily_plpc
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


# ---------------------------------------------------------------------------
# Per-position recommendation engine (HOLD / ADD / SELL)
# ---------------------------------------------------------------------------

def calibrate_recommendation(signal: str, confidence: str, unrealized_plpc: float) -> str:
    """Map a calibrated trend signal and position P&L to a HOLD/ADD/SELL verdict.

    Deterministic, following the SP-21 calibration pattern (see
    analysis.ai_analyst.calibrate_signal) — the Anthropic model explains the
    verdict, it never decides it.

    Rules:
      - NEUTRAL signal -> HOLD always. No directional conviction to act on.
      - BULLISH signal, High/Moderate confidence, position not underwater
        (unrealized_plpc >= _LOSS_BAND_PCT) -> ADD.
      - BULLISH signal otherwise (Low confidence, or a losing position) -> HOLD.
        A bullish reading doesn't override a position that's already red.
      - BEARISH signal, position underwater, High/Moderate confidence -> SELL.
        A deteriorating trend compounding an existing loss.
      - BEARISH signal, High confidence, position still in the green -> SELL.
        Protect gains against a high-conviction reversal.
      - BEARISH signal otherwise (Low confidence, or a Moderate-confidence
        winner) -> HOLD.

    Args:
        signal: BULLISH / BEARISH / NEUTRAL, from calibrate_signal.
        confidence: High / Moderate / Low, from calibrate_signal.
        unrealized_plpc: Position's unrealized P&L as a fraction (e.g. -0.05 for -5%).

    Returns:
        "HOLD", "ADD", or "SELL".
    """
    if signal == "NEUTRAL":
        return "HOLD"

    losing = unrealized_plpc < _LOSS_BAND_PCT

    if signal == "BULLISH":
        if confidence in ("High", "Moderate") and not losing:
            return "ADD"
        return "HOLD"

    # BEARISH
    if confidence in ("High", "Moderate") and losing:
        return "SELL"
    if confidence == "High" and not losing:
        return "SELL"
    return "HOLD"


def build_recommendation_prompt(
    ticker: str,
    summary: dict,
    signal: str,
    confidence: str,
    unrealized_pl: float,
    unrealized_plpc: float,
    recommendation: str,
) -> str:
    """Construct an Anthropic API prompt to explain a pre-computed HOLD/ADD/SELL verdict.

    The recommendation is computed by calibrate_recommendation; the model's
    only role is to produce a short, plain-English brief grounded in the
    supplied indicator and P&L values.

    Args:
        ticker: The stock symbol (e.g. "AAPL").
        summary: Dict from indicators.get_summary.
        signal: Pre-computed trend signal: "BULLISH", "BEARISH", or "NEUTRAL".
        confidence: Pre-computed confidence: "High", "Moderate", or "Low".
        unrealized_pl: Position's unrealized P&L in dollars.
        unrealized_plpc: Position's unrealized P&L as a fraction.
        recommendation: Pre-computed verdict: "HOLD", "ADD", or "SELL".

    Returns:
        A formatted prompt string ready for the Anthropic API.
    """
    price = summary["current_price"]
    ma10 = summary["ma_10"]
    ma20 = summary["ma_20"]
    pct_ma10 = (price - ma10) / ma10 * 100
    pct_ma20 = (price - ma20) / ma20 * 100
    pl_sign = "+" if unrealized_pl >= 0 else "-"

    return f"""You are a portfolio analyst writing a short daily brief for an existing paper-trading position. A recommendation has already been determined algorithmically — your only job is to explain it in plain English.

POSITION FOR {ticker}
----------------------
Current price   : ${price:.2f}
10-day MA       : ${ma10:.2f}  ({pct_ma10:+.2f}% deviation)
20-day MA       : ${ma20:.2f}  ({pct_ma20:+.2f}% deviation)
Volume          : {summary['volume_signal']}
Unrealized P&L  : {pl_sign}${abs(unrealized_pl):.2f} ({unrealized_plpc * 100:+.2f}%)

SIGNAL (pre-computed): {signal}
RECOMMENDATION (pre-computed): {recommendation}

Write a 2-3 sentence daily brief explaining this recommendation.
Use ONLY the indicator and P&L values shown above. Do NOT reference any factor absent from this data — no news, no fundamentals, no sector trends, no institutional activity.

Respond using EXACTLY this format and no other text:

BRIEF: <2-3 sentences grounding the {recommendation} verdict in the indicator and P&L values above>"""


def parse_recommendation_brief(raw_text: str) -> dict:
    """Parse the BRIEF field from the model's recommendation explanation response.

    The recommendation verdict is injected by get_recommendation from
    calibrate_recommendation output; this function only extracts the model's
    plain-English brief.

    Args:
        raw_text: The text content from the Anthropic API response.

    Returns:
        Dict with key: brief (str). On parse failure, brief describes the error.
    """
    for line in raw_text.strip().splitlines():
        if line.startswith("BRIEF:"):
            brief = line.split(":", 1)[1].strip()
            if brief:
                return {"brief": brief}

    return {"brief": "Parse error: BRIEF field missing or empty"}


def get_recommendation(
    ticker: str, summary: dict, unrealized_pl: float, unrealized_plpc: float
) -> dict:
    """Generate a HOLD/ADD/SELL recommendation for one position via calibration + Anthropic brief.

    The verdict is computed deterministically by calibrate_recommendation. The
    Anthropic API is called only to produce the plain-English daily brief text.

    Args:
        ticker: The stock symbol to analyse (e.g. "AAPL").
        summary: Dict produced by indicators.get_summary.
        unrealized_pl: Position's unrealized P&L in dollars.
        unrealized_plpc: Position's unrealized P&L as a fraction.

    Returns:
        Dict with keys: ticker, signal, confidence, recommendation, brief.

    Raises:
        RecommendationError: If the Anthropic API call fails.
    """
    signal, confidence = calibrate_signal(summary)
    recommendation = calibrate_recommendation(signal, confidence, unrealized_plpc)
    prompt = build_recommendation_prompt(
        ticker, summary, signal, confidence, unrealized_pl, unrealized_plpc, recommendation
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise RecommendationError(
            ticker,
            "Authentication failed — check that ANTHROPIC_API_KEY is set and valid",
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise RecommendationError(
            ticker,
            f"Could not reach the Anthropic API: {exc}",
        ) from exc
    except anthropic.APIStatusError as exc:
        raise RecommendationError(
            ticker,
            f"Anthropic API returned an error ({exc.status_code}): {exc.message}",
        ) from exc

    parsed = parse_recommendation_brief(response.content[0].text)
    return {
        "ticker": ticker,
        "signal": signal,
        "confidence": confidence,
        "recommendation": recommendation,
        **parsed,
    }


def _fetch_indicator_summary(ticker: str) -> dict:
    """Fetch OHLCV history for a ticker and reduce it to an indicator summary.

    Delegates to analysis.indicators.build_analysis_summary — the single
    canonical pipeline shared by all screens and the recommendation engine.

    Raises:
        ValueError: If the ticker has no price data.
        ConnectionError: If yfinance is unreachable.
    """
    return build_analysis_summary(ticker, days=_INDICATOR_HISTORY_DAYS)


def get_portfolio_recommendations(positions: list[dict]) -> list[dict]:
    """Generate a HOLD/ADD/SELL recommendation and daily brief for every open position.

    Fetches fresh indicator history per ticker and calls get_recommendation.
    A failure for one position (bad ticker data, network error, malformed or
    failed Anthropic response) degrades to a HOLD fallback for that position
    only — it never aborts the whole batch.

    Args:
        positions: List of position dicts (as produced by refresh_portfolio_state),
            each with at least ticker, unrealized_pl, unrealized_plpc.

    Returns:
        List of dicts, one per input position, each with keys: ticker, signal,
        confidence, recommendation, brief, and error (bool, True on fallback).
    """
    results = []
    for position in positions:
        ticker = position["ticker"]
        try:
            summary = _fetch_indicator_summary(ticker)
            rec = get_recommendation(
                ticker, summary, position["unrealized_pl"], position["unrealized_plpc"]
            )
            rec["error"] = False
            results.append(rec)
        except (ValueError, ConnectionError, RecommendationError) as exc:
            _log.warning("Recommendation unavailable for %s (%s) — defaulting to HOLD", ticker, exc)
            results.append(
                {
                    "ticker": ticker,
                    "signal": "NEUTRAL",
                    "confidence": "Low",
                    "recommendation": "HOLD",
                    "brief": f"Recommendation unavailable: {exc}",
                    "error": True,
                }
            )

    return results


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
