"""Append-only trade history for StockPilot.

Records every executed trade to trade_history.json at the repo root.
Mirrors the append-only pattern from signals_log.json. The file is
gitignored — it stores local runtime state only.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_HISTORY_PATH = Path(__file__).parent.parent / "trade_history.json"

logging.basicConfig(
    format="%(asctime)s [trade_history] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
_log = logging.getLogger(__name__)


def _load_history() -> list:
    """Load trade_history.json, returning an empty list if missing or corrupt."""
    if not _HISTORY_PATH.exists():
        return []
    try:
        with _HISTORY_PATH.open() as f:
            data = json.load(f)
        if not isinstance(data, list):
            _log.warning("trade_history.json is not a JSON array — resetting to empty")
            return []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        _log.warning("Could not read trade_history.json (%s) — treating as empty", exc)
        return []


def append_trade(
    ticker: str,
    side: str,
    qty: float,
    fill_price: float,
    order_id: str,
    signal: str,
    confidence: str,
    signal_timestamp: Optional[str] = None,
) -> dict:
    """Append one trade record to trade_history.json and return it.

    Args:
        ticker:           Stock symbol (e.g. "AAPL").
        side:             "BUY" or "SELL".
        qty:              Number of shares traded.
        fill_price:       Price per share at fill time.
        order_id:         Alpaca order UUID.
        signal:           Signal that triggered the trade ("BULLISH", etc.).
        confidence:       Signal confidence ("High", "Moderate", "Low").
        signal_timestamp: ISO-8601 timestamp of the originating entry in
                          signals_log.json, enabling cross-file linkage.
                          Pass None when no signal timestamp is available.

    Returns:
        The complete trade record dict that was written.
    """
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker.upper(),
        "side": side,
        "qty": qty,
        "fill_price": fill_price,
        "order_id": order_id,
        "signal": signal,
        "confidence": confidence,
        "signal_timestamp": signal_timestamp,
    }

    history = _load_history()
    history.append(record)

    with _HISTORY_PATH.open("w") as f:
        json.dump(history, f, indent=2)

    _log.info(
        "Trade recorded — %s %s x %.4f @ $%.2f  order_id=%s",
        side,
        ticker,
        qty,
        fill_price,
        order_id,
    )
    return record


def get_trades_for_ticker(ticker: str) -> list[dict]:
    """Return all trade records for the given ticker, oldest-first.

    Args:
        ticker: Stock symbol to filter by (case-insensitive).

    Returns:
        List of trade record dicts. Empty list if none found.
    """
    upper = ticker.upper()
    return [r for r in _load_history() if r.get("ticker", "").upper() == upper]


def load_trade_history() -> list[dict]:
    """Return the full trade history as a list of dicts, oldest-first.

    Returns an empty list if the file does not exist or cannot be parsed.
    """
    return _load_history()
