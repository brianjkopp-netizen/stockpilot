"""AI signal generation for the StockPilot analysis pipeline."""

import anthropic
import json
from datetime import datetime, timezone
from pathlib import Path


class SignalGenerationError(Exception):
    """Raised when the Anthropic API call in get_signal fails."""

    def __init__(self, ticker: str, message: str) -> None:
        super().__init__(f"[{ticker}] {message}")
        self.ticker = ticker


_LOG_PATH = Path(__file__).parent.parent / "signals_log.json"

_REQUIRED_SUMMARY_KEYS = {
    "current_price",
    "ma_10",
    "ma_20",
    "volume_signal",
    "price_vs_ma10",
    "price_vs_ma20",
}

# Signal calibration thresholds — percent deviation of price from a moving average.
# Avg of |pct_ma10| and |pct_ma20| must exceed this for a directional signal.
_NEUTRAL_BAND_PCT = 1.5
# Avg pct deviation required for High confidence.
_HIGH_CONF_AVG_PCT = 3.0
# Each individual MA deviation must clear this for High confidence.
_HIGH_CONF_EACH_PCT = 1.0
# Avg pct deviation required for Moderate confidence.
_MODERATE_CONF_AVG_PCT = 2.0


def calibrate_signal(summary: dict) -> tuple[str, str]:
    """Compute (signal, confidence) deterministically from price-vs-MA deviations.

    Signal logic:
      - NEUTRAL if price is on opposite sides of MA10 and MA20 (mixed trend).
      - NEUTRAL if the average of |pct deviation from MA10| and |pct deviation
        from MA20| is less than _NEUTRAL_BAND_PCT (1.5%) — consolidation zone.
      - BULLISH if price is above both MAs and avg deviation exceeds the band.
      - BEARISH if price is below both MAs and avg deviation exceeds the band.

    Confidence logic (directional signals only):
      - High:     avg_pct >= 3.0% AND ABOVE AVERAGE volume AND both individual
                  deviations >= 1.0%.
      - Moderate: avg_pct >= 2.0%.
      - Low:      avg_pct < 2.0% (directional but weak).

    Args:
        summary: Dict from indicators.get_summary. Required keys:
            current_price, ma_10, ma_20, volume_signal.

    Returns:
        Tuple (signal, confidence). signal is BULLISH / BEARISH / NEUTRAL.
        confidence is High / Moderate / Low.
    """
    price = summary["current_price"]
    ma10 = summary["ma_10"]
    ma20 = summary["ma_20"]
    volume_signal = summary["volume_signal"]

    pct_ma10 = (price - ma10) / ma10 * 100
    pct_ma20 = (price - ma20) / ma20 * 100
    avg_pct = (abs(pct_ma10) + abs(pct_ma20)) / 2

    # NEUTRAL: MAs point in different directions, or both deviations are small.
    ma_disagree = (pct_ma10 > 0) != (pct_ma20 > 0)
    if ma_disagree or avg_pct < _NEUTRAL_BAND_PCT:
        return "NEUTRAL", "Low"

    signal = "BULLISH" if pct_ma10 > 0 else "BEARISH"

    volume_high = volume_signal == "ABOVE AVERAGE"
    both_deviations_strong = (
        abs(pct_ma10) >= _HIGH_CONF_EACH_PCT and abs(pct_ma20) >= _HIGH_CONF_EACH_PCT
    )

    if avg_pct >= _HIGH_CONF_AVG_PCT and volume_high and both_deviations_strong:
        confidence = "High"
    elif avg_pct >= _MODERATE_CONF_AVG_PCT:
        confidence = "Moderate"
    else:
        confidence = "Low"

    return signal, confidence


def build_prompt(ticker: str, summary: dict, signal: str, confidence: str) -> str:
    """Construct an Anthropic API prompt to explain a pre-computed trading signal.

    Signal and confidence are computed by calibrate_signal; the model's only role
    is to produce plain-English reasoning grounded in the supplied indicator values.

    Args:
        ticker: The stock symbol (e.g. "AAPL").
        summary: Dict from indicators.get_summary — required keys listed in
            _REQUIRED_SUMMARY_KEYS.
        signal: Pre-computed signal: "BULLISH", "BEARISH", or "NEUTRAL".
        confidence: Pre-computed confidence: "High", "Moderate", or "Low".

    Returns:
        A formatted prompt string ready for the Anthropic API.

    Raises:
        ValueError: If any required summary key is missing.
    """
    missing = _REQUIRED_SUMMARY_KEYS - summary.keys()
    if missing:
        raise ValueError(
            f"build_prompt: summary is missing required keys: {sorted(missing)}"
        )

    price = summary["current_price"]
    ma10 = summary["ma_10"]
    ma20 = summary["ma_20"]
    pct_ma10 = (price - ma10) / ma10 * 100
    pct_ma20 = (price - ma20) / ma20 * 100

    return f"""You are a quantitative trading analyst. The following technical indicators have been computed for {ticker}, and a signal has been determined algorithmically.

MARKET DATA FOR {ticker}
------------------------
Current price  : ${price:.2f}
10-day MA      : ${ma10:.2f}  ({pct_ma10:+.2f}% deviation)
20-day MA      : ${ma20:.2f}  ({pct_ma20:+.2f}% deviation)
Volume         : {summary['volume_signal']}

SIGNAL (pre-computed): {signal}
CONFIDENCE (pre-computed): {confidence}

Explain the reasoning for this signal in 2-3 sentences.
Use ONLY the indicator values shown above. Do NOT reference any factor absent from this data — no news, no fundamentals, no sector trends, no institutional activity.

Respond using EXACTLY this format and no other text:

REASONING: <2-3 sentences grounding the {signal} / {confidence} reading in the indicator values above>
KEY_FACTORS:
- <factor 1>
- <factor 2>
- <factor 3>"""


def parse_signal(raw_text: str) -> dict:
    """Parse REASONING and KEY_FACTORS from the model's explanation response.

    Signal and confidence are injected by get_signal from calibrate_signal output;
    this function only extracts the model's plain-English explanation.

    Args:
        raw_text: The text content from the Anthropic API response.

    Returns:
        Dict with keys: reasoning (str), key_factors (list[str]).
        On parse failure, reasoning describes the error and key_factors is [].
    """
    result: dict = {
        "reasoning": "",
        "key_factors": [],
    }

    try:
        lines = raw_text.strip().splitlines()

        for i, line in enumerate(lines):
            if line.startswith("REASONING:"):
                result["reasoning"] = line.split(":", 1)[1].strip()

            elif line.startswith("KEY_FACTORS:"):
                factors = []
                for factor_line in lines[i + 1:]:
                    stripped = factor_line.strip()
                    if stripped.startswith("- "):
                        factors.append(stripped[2:].strip())
                result["key_factors"] = factors

        if not result["reasoning"]:
            raise ValueError("REASONING field missing or empty")

    except Exception as exc:
        result["reasoning"] = f"Parse error: {exc}"
        result["key_factors"] = []

    return result


def get_signal(ticker: str, summary: dict) -> dict:
    """Generate a trading signal for a ticker via calibration + Anthropic reasoning.

    Signal and confidence are computed deterministically by calibrate_signal.
    The Anthropic API is called only to produce plain-English reasoning text.

    Args:
        ticker: The stock symbol to analyse (e.g. "AAPL").
        summary: Dict produced by indicators.get_summary — see build_prompt
            for required keys.

    Returns:
        Dict with keys: ticker, signal, confidence, reasoning, key_factors.

    Raises:
        ValueError: If summary is missing required keys (from build_prompt).
        SignalGenerationError: If the Anthropic API call fails.
    """
    signal, confidence = calibrate_signal(summary)
    prompt = build_prompt(ticker, summary, signal, confidence)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise SignalGenerationError(
            ticker,
            "Authentication failed — check that ANTHROPIC_API_KEY is set and valid",
        ) from exc
    except anthropic.APIConnectionError as exc:
        raise SignalGenerationError(
            ticker,
            f"Could not reach the Anthropic API: {exc}",
        ) from exc
    except anthropic.APIStatusError as exc:
        raise SignalGenerationError(
            ticker,
            f"Anthropic API returned an error ({exc.status_code}): {exc.message}",
        ) from exc

    parsed = parse_signal(response.content[0].text)
    result = {
        "ticker": ticker,
        "signal": signal,
        "confidence": confidence,
        **parsed,
    }
    log_signal(result, summary["current_price"])
    return result


def log_signal(signal_dict: dict, price: float) -> None:
    """Append a signal record with a timestamp to signals_log.json.

    Args:
        signal_dict: Dict returned by get_signal — expected keys: ticker,
            signal, confidence, reasoning, key_factors.
        price: The current price of the ticker at the time of logging.

    The log file is created at the repo root if it does not already exist.
    Each call appends one record; existing records are never modified.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": signal_dict["ticker"],
        "price": price,
        "signal": signal_dict["signal"],
        "confidence": signal_dict["confidence"],
        "reasoning": signal_dict["reasoning"],
        "key_factors": signal_dict["key_factors"],
    }

    records: list = []
    if _LOG_PATH.exists():
        try:
            with _LOG_PATH.open("r") as f:
                records = json.load(f)
        except json.JSONDecodeError:
            corrupt_path = _LOG_PATH.with_suffix(".corrupt.json")
            _LOG_PATH.rename(corrupt_path)
            records = []

    records.append(record)

    with _LOG_PATH.open("w") as f:
        json.dump(records, f, indent=2)


def load_signal_history(ticker: str) -> list:
    """Return all logged signal records for a given ticker.

    Args:
        ticker: The stock symbol to filter by (case-insensitive).

    Returns:
        List of record dicts in chronological order. Returns an empty list
        if the log file does not exist or contains no records for the ticker.
    """
    if not _LOG_PATH.exists():
        return []

    try:
        with _LOG_PATH.open("r") as f:
            records = json.load(f)
    except json.JSONDecodeError:
        return []

    target = ticker.upper()
    return [r for r in records if r.get("ticker", "").upper() == target]


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    test_cases = [
        ("AAPL", {
            "current_price": 213.45, "ma_10": 208.30, "ma_20": 201.75,
            "volume_signal": "ABOVE AVERAGE", "price_vs_ma10": "ABOVE", "price_vs_ma20": "ABOVE",
        }),
        ("TSLA", {
            "current_price": 178.92, "ma_10": 185.60, "ma_20": 190.14,
            "volume_signal": "BELOW AVERAGE", "price_vs_ma10": "BELOW", "price_vs_ma20": "BELOW",
        }),
        ("NVDA", {
            "current_price": 131.10, "ma_10": 129.85, "ma_20": 124.40,
            "volume_signal": "ABOVE AVERAGE", "price_vs_ma10": "ABOVE", "price_vs_ma20": "ABOVE",
        }),
        ("MSFT", {
            "current_price": 415.00, "ma_10": 418.50, "ma_20": 420.00,
            "volume_signal": "AVERAGE", "price_vs_ma10": "BELOW", "price_vs_ma20": "BELOW",
        }),
        ("AMZN", {
            "current_price": 192.30, "ma_10": 188.00, "ma_20": 185.50,
            "volume_signal": "ABOVE AVERAGE", "price_vs_ma10": "ABOVE", "price_vs_ma20": "ABOVE",
        }),
    ]

    for ticker, summary in test_cases:
        print("=" * 60)
        print(f"TICKER: {ticker}")
        sig, conf = calibrate_signal(summary)
        print(f"CALIBRATED → signal={sig}, confidence={conf}")
        print("-" * 30)
        result = get_signal(ticker, summary)
        for k, v in result.items():
            print(f"  {k}: {v}")
        print()
