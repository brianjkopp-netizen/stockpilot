import { Button } from "./atoms.jsx";
import Icon from "./Icon.jsx";
import { fmt$, fmtN } from "../lib/format.js";

/**
 * Confirmation modal for a paper order. Purely presentational — the numbers shown
 * are a display-only estimate of what the backend will do; POST /orders remains the
 * sole source of truth for the actual order and fill.
 */
export default function ConfirmOrder({ order, submitting, onConfirm, onCancel }) {
  if (!order) return null;
  const { ticker, side, qty, notional, price, isClose } = order;
  const isBuy = side === "buy";

  return (
    <div className="modal-bg" onClick={onCancel}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-hd">
          <div className="ttl">
            Confirm {isBuy ? "buy" : "sell"} — {ticker}
          </div>
          <span className="close-x" onClick={onCancel} role="button" aria-label="Cancel">
            <Icon name="close" size={14} />
          </span>
        </div>
        <div className="modal-bd">
          {isClose && (
            <p style={{ marginBottom: 16, fontSize: 13, color: "rgba(255,255,255,0.92)" }}>
              This closes the entire position — sells all {fmtN(qty)} shares of {ticker}.
            </p>
          )}
          <div style={{ display: "grid", gap: 10, fontSize: 13 }}>
            <ConfirmRow label="Side" value={isBuy ? "BUY" : "SELL"} />
            <ConfirmRow label="Estimated shares" value={qty != null ? fmtN(Number(qty.toFixed(4))) : "—"} />
            <ConfirmRow label="Estimated notional" value={fmt$(notional)} />
            <ConfirmRow label="Based on last known price" value={fmt$(price)} />
          </div>
          <p style={{ marginTop: 18, fontSize: 11.5, color: "var(--mute)", lineHeight: 1.6 }}>
            This estimate is indicative. The order submits at market, so the actual fill price and share
            count may differ.
          </p>
        </div>
        <div className="modal-ft">
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant={isBuy ? "primary" : "danger"} onClick={onConfirm} disabled={submitting}>
            {submitting ? "Placing…" : `Confirm ${isBuy ? "buy" : "sell"}`}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ConfirmRow({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "var(--mute)", textTransform: "uppercase", fontSize: 10.5, letterSpacing: "0.14em" }}>
        {label}
      </span>
      <span className="num">{value}</span>
    </div>
  );
}
