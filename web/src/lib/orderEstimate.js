// Mirrors decide_order()'s buy-notional-by-confidence rule in trading/alpaca_client.py,
// for display only — the backend recomputes this independently and is the source of truth.
const BUY_NOTIONAL_BY_CONFIDENCE = { High: 500, Moderate: 200 };

/** Indicative shares/notional for a BULLISH buy, given confidence and a last-known price. */
export function estimateBuyOrder(confidence, price) {
  const notional = BUY_NOTIONAL_BY_CONFIDENCE[confidence] ?? 0;
  const qty = price ? notional / price : null;
  return { notional, qty };
}
