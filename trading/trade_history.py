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
    fill_price: Optional[float],
    order_id: str,
    signal: Optional[str] = None,
    confidence: Optional[str] = None,
    signal_timestamp: Optional[str] = None,
) -> dict:
    """Append one trade record to trade_history.json and return it.

    Args:
        ticker:           Stock symbol (e.g. "AAPL").
        side:             "BUY" or "SELL".
        qty:              Number of shares traded.
        fill_price:       Alpaca's filled_avg_price, or None if the order has
                          not filled yet (e.g. placed after hours).
        order_id:         Alpaca order UUID.
        signal:           Signal that triggered the trade ("BULLISH", etc.),
                          or None when the order was placed without a signal.
        confidence:       Signal confidence ("High", "Moderate", "Low"),
                          or None when not available.
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


if __name__ == "__main__":
    print("=== Trade history smoke test (no Alpaca orders placed) ===\n")

    record1 = append_trade(
        ticker="AAPL",
        side="BUY",
        qty=2.381,
        fill_price=210.05,
        order_id="smoke-test-aapl-001",
        signal="BULLISH",
        confidence="High",
    )
    print(f"  Wrote: {record1['ticker']} {record1['side']} qty={record1['qty']} fill_price={record1['fill_price']}")

    record2 = append_trade(
        ticker="TSLA",
        side="BUY",
        qty=0.952,
        fill_price=295.50,
        order_id="smoke-test-tsla-001",
        signal="BULLISH",
        confidence="Moderate",
    )
    print(f"  Wrote: {record2['ticker']} {record2['side']} qty={record2['qty']} fill_price={record2['fill_price']}")

    history = load_trade_history()
    print(f"\nRecords in trade_history.json: {len(history)}")
    assert len(history) >= 2

    print("\nSmoke test passed.")