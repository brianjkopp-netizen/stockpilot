"""Per-position recommendation engine for StockPilot.

Verdict (HOLD / ADD / SELL) is computed deterministically from position P&L
and the current technical signal. The Anthropic model writes the explanation,
not the verdict — following the same pattern as analysis.ai_analyst (SP-21).
"""

import anthropic

from analysis.ai_analyst import calibrate_signal
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary
from data.fetcher import get_stock_data
from trading.alpaca_client import decide_order


_MA_WINDOWS = [10, 20]
_HISTORY_DAYS = 30

# Deterministic verdict thresholds.
# Hard stop: cut regardless of signal.
_SELL_HARD_LOSS_PCT = -0.10
# Soft stop: cut only when signal confirms the down-trend.
_SELL_SIGNAL_LOSS_PCT = -0.05


class RecommendationError(Exception):
    """Raised when the Anthropic API call for the brief fails."""

    def __init__(self, ticker: str, message: str) -> None:
        super().__init__(f"[{ticker}] {message}")
        self.ticker = ticker


def compute_verdict(position: dict, signal: str, confidence: str) -> str:
    """Return HOLD, ADD, or SELL based on position P&L and technical signal.

    Rules applied in priority order:
      1. SELL — unrealized_plpc < -10% (hard stop, signal-agnostic)
      2. SELL — unrealized_plpc < -5%  AND signal is BEARISH
      3. ADD  — unrealized_plpc >= 0   AND signal is BULLISH
                AND confidence is High or Moderate
      4. HOLD — all other cases

    Note (SP-43): an ADD verdict here is necessary but not sufficient for the
    trade to actually place. trading.alpaca_client.decide_order() is the real
    gate at POST /orders and only looks at signal/confidence, not P&L — this
    function adds the P&L check on top. The two are meant to agree on the
    signal/confidence half of the decision, but nothing enforces that beyond
    convention, so get_recommendation() calls decide_order() itself and
    attaches placeable/placeable_reason to the result rather than letting an
    ADD verdict imply a trade the backend will refuse. See get_recommendation().

    Args:
        position: Dict with at least unrealized_plpc (fractional float, not %).
        signal: "BULLISH", "BEARISH", or "NEUTRAL".
        confidence: "High", "Moderate", or "Low".

    Returns:
        "HOLD", "ADD", or "SELL".
    """
    plpc = position.get("unrealized_plpc", 0.0)

    if plpc <= _SELL_HARD_LOSS_PCT:
        return "SELL"
    if plpc < _SELL_SIGNAL_LOSS_PCT and signal == "BEARISH":
        return "SELL"
    if plpc > 0.0 and signal == "BULLISH" and confidence in ("High", "Moderate"):
        return "ADD"
    return "HOLD"


def build_rec_prompt(
    position: dict,
    summary: dict,
    signal: str,
    confidence: str,
    verdict: str,
) -> str:
    """Construct the Anthropic prompt for a position's daily brief.

    The verdict is already determined; the model's only role is to write a
    2-3 sentence explanation grounded in the supplied P&L and indicator values.

    Args:
        position: Mark-to-market position dict (ticker, qty, avg_entry_price,
            mark_price, unrealized_pl, unrealized_plpc, daily_pl, daily_plpc).
        summary: Dict from indicators.get_summary (current_price, ma_10, ma_20,
            volume_signal).
        signal: Pre-computed signal: "BULLISH", "BEARISH", or "NEUTRAL".
        confidence: Pre-computed confidence: "High", "Moderate", or "Low".
        verdict: Pre-computed verdict: "HOLD", "ADD", or "SELL".

    Returns:
        A formatted prompt string ready for the Anthropic API.
    """
    ticker = position["ticker"]
    qty = position["qty"]
    avg_entry = position["avg_entry_price"]
    mark = position["mark_price"]
    unreal_pl = position["unrealized_pl"]
    unreal_plpc = position["unrealized_plpc"] * 100
    daily_pl = position["daily_pl"]
    daily_plpc = position["daily_plpc"] * 100

    price = summary["current_price"]
    ma10 = summary["ma_10"]
    ma20 = summary["ma_20"]
    volume = summary["volume_signal"]
    pct_ma10 = (price - ma10) / ma10 * 100
    pct_ma20 = (price - ma20) / ma20 * 100

    return f"""You are a quantitative portfolio analyst. The following data has been computed for the {ticker} position in a paper trading account. A recommendation has been determined algorithmically.

POSITION DATA FOR {ticker}
---------------------------
Shares held    : {qty:.4f}
Avg entry price: ${avg_entry:.2f}
Current mark   : ${mark:.2f}
Unrealized P&L : ${unreal_pl:+.2f} ({unreal_plpc:+.2f}%)
Daily P&L      : ${daily_pl:+.2f} ({daily_plpc:+.2f}%)

TECHNICAL INDICATORS
---------------------
Current price  : ${price:.2f}
10-day MA      : ${ma10:.2f}  ({pct_ma10:+.2f}% deviation)
20-day MA      : ${ma20:.2f}  ({pct_ma20:+.2f}% deviation)
Volume         : {volume}
Signal         : {signal} / {confidence}

RECOMMENDATION (pre-computed): {verdict}

Write a 2-3 sentence daily brief explaining the {verdict} recommendation.
Use ONLY the data shown above. Do NOT reference any factor absent from this data — no news, no fundamentals, no sector trends, no invented context.

Respond using EXACTLY this format and no other text:

BRIEF: <2-3 sentences grounding the {verdict} recommendation in the supplied P&L and indicator values>"""


def parse_brief(raw_text: str) -> str:
    """Extract the brief string from the model response.

    Args:
        raw_text: The text content from the Anthropic API response.

    Returns:
        The brief string, or a fallback message on parse failure.
    """
    for line in raw_text.strip().splitlines():
        if line.startswith("BRIEF:"):
            brief = line.split(":", 1)[1].strip()
            if brief:
                return brief
    return "Brief unavailable — model response format unexpected."


def get_recommendation(position: dict) -> dict:
    """Compute verdict and AI brief for one position.

    Fetches fresh market data, computes the technical signal deterministically
    via calibrate_signal, then computes the verdict deterministically via
    compute_verdict. The Anthropic API is called once to produce a plain-English
    brief explaining the verdict.

    Args:
        position: Mark-to-market position dict from tracker.get_portfolio_state.
            Required keys: ticker, qty, avg_entry_price, mark_price,
            unrealized_pl, unrealized_plpc, daily_pl, daily_plpc.

    Returns:
        Dict with keys: ticker, verdict ("HOLD"/"ADD"/"SELL"), brief (str),
        signal (str), confidence (str), placeable (bool), placeable_reason
        (str or None). placeable is only meaningful for an ADD verdict — it
        is False when decide_order() would refuse the trade despite the ADD
        (see the SP-43 note on compute_verdict). It is always True for HOLD
        and SELL, since neither goes through decide_order's buy gate.

    Raises:
        RecommendationError: If the Anthropic API call fails.
        ValueError: If the ticker has no price data or the position dict is
            missing required keys.
        ConnectionError: If yfinance is unreachable.
    """
    ticker = position["ticker"]

    df = get_stock_data(ticker, days=_HISTORY_DAYS)
    df = add_moving_averages(df, _MA_WINDOWS)
    df = add_volume_signal(df)
    summary = get_summary(df)

    signal, confidence = calibrate_signal(summary)
    verdict = compute_verdict(position, signal, confidence)

    # SP-43: compute_verdict's ADD case must agree with decide_order's BUY case
    # (trading.alpaca_client), since decide_order is the actual gate at
    # POST /orders. Check it here so an ADD verdict never asserts a trade the
    # backend will refuse — the React Portfolio screen only renders this as
    # presentational state (button disabled + reason shown).
    placeable = True
    placeable_reason = None
    if verdict == "ADD":
        action, _ = decide_order(signal, confidence)
        if action is None:
            placeable = False
            placeable_reason = "Signal/confidence below buy threshold"

    prompt = build_rec_prompt(position, summary, signal, confidence, verdict)

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

    brief = parse_brief(response.content[0].text)
    return {
        "ticker": ticker,
        "verdict": verdict,
        "brief": brief,
        "signal": signal,
        "confidence": confidence,
        "placeable": placeable,
        "placeable_reason": placeable_reason,
    }
