"""Discover-screen scan pipeline.

Provides scan_ticker() — the single entry point for the Discover screen and
the future SP-33 API layer. All orchestration (fetch → indicators → signal →
drift → sparkline) lives here so app/main.py is render-only.
"""

from data.fetcher import get_stock_data, get_company_name
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary
from analysis.ai_analyst import get_signal

_MA_WINDOWS = [10, 20]


def compute_drift_5d(closes: list) -> float:
    """Return the 5-trading-day price drift as a decimal fraction.

    Uses the last 6 closes (today vs 5 sessions ago). Falls back to the
    full range if fewer than 6 closes are available, or 0.0 if fewer than 2.

    Args:
        closes: Ordered list of close prices (oldest first).

    Returns:
        Drift as a decimal (e.g. 0.03 means +3%). Always a float.
    """
    if len(closes) >= 6:
        return (closes[-1] - closes[-6]) / closes[-6]
    if len(closes) >= 2:
        return (closes[-1] - closes[0]) / closes[0]
    return 0.0


def compute_sparkline(closes: list, n: int = 14) -> list:
    """Return the last n close prices for sparkline rendering.

    Args:
        closes: Ordered list of close prices (oldest first).
        n: Number of trailing sessions to return (default 14).

    Returns:
        List of floats, length <= n. Empty list if closes is empty.
    """
    return closes[-n:] if closes else []


def scan_ticker(ticker: str, days: int) -> dict:
    """Run the full analysis pipeline for one ticker and return a result dict.

    Fetches price data, computes indicators, generates an AI signal, and derives
    the 14d sparkline and 5d drift from the same DataFrame — no redundant network
    calls. Company name is fetched separately via yfinance .info.

    Args:
        ticker: Ticker symbol (e.g. "AAPL").
        days: Calendar days of history to fetch.

    Returns:
        Dict with keys: ticker, company_name, signal, confidence, price,
        drift_5d (float or None), sparkline (list), reasoning, _signal_obj
        (dict or None), error (str or None). On failure all price/signal fields
        are degraded and error contains the exception message.
    """
    try:
        df = get_stock_data(ticker, days)
        df = add_moving_averages(df, _MA_WINDOWS)
        df = add_volume_signal(df)
        summary = get_summary(df)
        signal = get_signal(ticker, summary)

        closes = df["Close"].dropna().tolist()
        sparkline = compute_sparkline(closes)
        drift_5d = compute_drift_5d(closes)
        company_name = get_company_name(ticker)

        return {
            "ticker": ticker,
            "company_name": company_name,
            "signal": signal["signal"],
            "confidence": signal["confidence"],
            "price": summary["current_price"],
            "drift_5d": drift_5d,
            "sparkline": sparkline,
            "reasoning": signal["reasoning"],
            "_signal_obj": signal,
            "error": None,
        }
    except Exception as exc:
        return {
            "ticker": ticker,
            "company_name": ticker,
            "signal": "ERROR",
            "confidence": "—",
            "price": None,
            "drift_5d": None,
            "sparkline": [],
            "reasoning": str(exc),
            "_signal_obj": None,
            "error": str(exc),
        }