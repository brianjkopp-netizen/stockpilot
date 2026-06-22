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


def build_prompt(ticker: str, summary: dict) -> str:
    """Construct a structured Anthropic API prompt for a single ticker.

    Args:
        ticker: The stock symbol being analysed (e.g. "AAPL").
        summary: Dict produced by indicators.get_summary — expected keys:
            current_price, ma_10, ma_20, volume_signal,
            price_vs_ma10, price_vs_ma20.

    Returns:
        A formatted prompt string ready to pass as the user message
        to the Anthropic API.

    Raises:
        ValueError: If any required key is missing from summary.
    """
    missing = _REQUIRED_SUMMARY_KEYS - summary.keys()
    if missing:
        raise ValueError(
            f"build_prompt: summary is missing required keys: {sorted(missing)}"
        )

    return f"""You are a quantitative trading analyst. Analyse the following technical data for {ticker} and produce a trading signal.

MARKET DATA FOR {ticker}
------------------------
Current price  : ${summary['current_price']:.2f}
10-day MA      : ${summary['ma_10']:.2f}  (price is {summary['price_vs_ma10']} this level)
20-day MA      : ${summary['ma_20']:.2f}  (price is {summary['price_vs_ma20']} this level)
Volume         : {summary['volume_signal']}

Based solely on this technical data, provide your assessment.

Respond using EXACTLY this format and no other text:

SIGNAL: <BULLISH|BEARISH|NEUTRAL>
CONFIDENCE: <High|Moderate|Low>
REASONING: <2-3 sentences explaining the key drivers behind your signal>
KEY_FACTORS:
- <factor 1>
- <factor 2>
- <factor 3>"""


def parse_signal(raw_text: str) -> dict:
    """Parse the raw Anthropic API response text into a structured signal dict.

    Args:
        raw_text: The text content from the API response, expected to follow
            the format defined in build_prompt.

    Returns:
        Dict with keys: signal, confidence, reasoning, key_factors.
        On parse failure, signal is "NEUTRAL", confidence is "Low",
        reasoning describes the error, and key_factors is an empty list.
    """
    result = {
        "signal": "NEUTRAL",
        "confidence": "Low",
        "reasoning": "",
        "key_factors": [],
    }

    try:
        lines = raw_text.strip().splitlines()

        for i, line in enumerate(lines):
            if line.startswith("SIGNAL:"):
                value = line.split(":", 1)[1].strip().upper()
                if value in {"BULLISH", "BEARISH", "NEUTRAL"}:
                    result["signal"] = value

            elif line.startswith("CONFIDENCE:"):
                value = line.split(":", 1)[1].strip().capitalize()
                if value in {"High", "Moderate", "Low"}:
                    result["confidence"] = value

            elif line.startswith("REASONING:"):
                result["reasoning"] = line.split(":", 1)[1].strip()

            elif line.startswith("KEY_FACTORS:"):
                factors = []
                for factor_line in lines[i + 1 :]:
                    stripped = factor_line.strip()
                    if stripped.startswith("- "):
                        factors.append(stripped[2:].strip())
                result["key_factors"] = factors

        if not result["reasoning"]:
            raise ValueError("REASONING field missing or empty")

    except Exception as exc:
        result["signal"] = "NEUTRAL"
        result["confidence"] = "Low"
        result["reasoning"] = f"Parse error: {exc}"
        result["key_factors"] = []

    return result


def get_signal(ticker: str, summary: dict) -> dict:
    """Call the Anthropic API to generate a trading signal for a ticker.

    Args:
        ticker: The stock symbol to analyse (e.g. "AAPL").
        summary: Dict produced by indicators.get_summary — see build_prompt
            for required keys.

    Returns:
        Dict with keys: ticker, signal, confidence, reasoning, key_factors.

    Raises:
        ValueError: If summary is missing required keys (from build_prompt).
        SignalGenerationError: If the Anthropic API call fails for any reason,
            including connection errors, timeouts, and authentication failures.
    """
    prompt = build_prompt(ticker, summary)

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
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
    result = {"ticker": ticker, **parsed}
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

    # Raw-response inspection helper — bypasses parse_signal so we can verify
    # the model is actually following the prompt format before trusting the parser.
    def _raw_get_signal(ticker: str, summary: dict) -> tuple[str, dict]:
        """Return (raw_text, parsed_dict) for side-by-side inspection."""
        prompt = build_prompt(ticker, summary)
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text
        parsed = parse_signal(raw)
        return raw, {"ticker": ticker, **parsed}

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
        print("-" * 30)
        raw, parsed = _raw_get_signal(ticker, summary)
        print("RAW RESPONSE:")
        print(raw)
        print("\nPARSED RESULT:")
        for k, v in parsed.items():
            print(f"  {k}: {v}")
        print()
