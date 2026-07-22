import { useState } from "react";
import { GoldRule, SignalBadge, Sparkline, Button } from "../components/atoms.jsx";
import { Loading, ErrorPanel, EmptyState } from "../components/StateBlock.jsx";
import ConfirmOrder from "../components/ConfirmOrder.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { getDiscover, placeOrder } from "../api/client.js";
import { fmt$, fmtPct, fmtTimestamp } from "../lib/format.js";
import { estimateBuyOrder } from "../lib/orderEstimate.js";

const DAYS = 30;

export default function DiscoverScreen() {
  const { data, error, loading, run } = useAsync(() => getDiscover(DAYS), []);
  const [orderState, setOrderState] = useState({});
  const [confirm, setConfirm] = useState(null);

  const results = data?.results ?? [];
  const counts = data?.counts ?? { BULLISH: 0, BEARISH: 0, NEUTRAL: 0 };

  async function handleBuy(row) {
    setOrderState((s) => ({ ...s, [row.ticker]: { loading: true, error: null, placed: null } }));
    try {
      const result = await placeOrder({
        ticker: row.ticker,
        side: "buy",
        signal: row.signal,
        confidence: row.confidence,
      });
      setOrderState((s) => ({
        ...s,
        [row.ticker]: { loading: false, error: result.placed ? null : result.reason || "Order not placed", placed: result.placed },
      }));
    } catch (err) {
      setOrderState((s) => ({
        ...s,
        [row.ticker]: { loading: false, error: err.detail || err.message, placed: false },
      }));
    }
  }

  function requestBuy(row) {
    const { qty, notional } = estimateBuyOrder(row.confidence, row.price);
    setConfirm({ ticker: row.ticker, side: "buy", price: row.price, qty, notional, isClose: false, row });
  }

  async function handleConfirm() {
    if (!confirm || confirm.submitting) return;
    const { row } = confirm;
    setConfirm((c) => (c ? { ...c, submitting: true } : c));
    await handleBuy(row);
    setConfirm(null);
  }

  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow">
            <GoldRule width={20} /> Discover
          </div>
          <h2>Ideas worth looking at.</h2>
          <p>
            The AI scans your watchlist and surfaces a signal, price, and trend for every name — open
            a paper position directly from a result you like.
          </p>
        </div>
        <Button variant="ghost" icon="refresh" onClick={() => run()} disabled={loading}>
          {loading ? "Scanning" : "Refresh scan"}
        </Button>
      </div>

      {loading && <Loading label="Scanning your watchlist — running indicators and AI signals for every ticker…" />}

      {!loading && error && (
        <ErrorPanel message={error.detail || error.message} onRetry={() => run()} />
      )}

      {!loading && !error && data && (
        <>
          <div
            className="panel subtle"
            style={{ marginBottom: 24, padding: "16px 22px", display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}
          >
            <span className="pip-i"></span>
            <span style={{ fontSize: 12.5, color: "rgba(255,255,255,0.92)" }}>
              Scan run <strong>{fmtTimestamp(data.scanned_at)}</strong> against a {data.total}-name watchlist.{" "}
              {counts.BULLISH} bullish · {counts.BEARISH} bearish · {counts.NEUTRAL} neutral.
            </span>
          </div>

          {results.length === 0 ? (
            <div className="panel subtle">
              <EmptyState>Your watchlist is empty. Add tickers to watchlist.json to scan for candidates.</EmptyState>
            </div>
          ) : (
            <div className="panel">
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Signal</th>
                      <th className="num">Price</th>
                      <th className="num">5d drift</th>
                      <th>Trend · 14d</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((r) => (
                      <ResultRow
                        key={r.ticker}
                        row={r}
                        orderState={orderState[r.ticker]}
                        onBuy={() => requestBuy(r)}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ResultRow({ row: r, orderState, onBuy }) {
  const busy = orderState?.loading;

  if (r.error) {
    return (
      <tr className="row">
        <td>
          <div className="ticker-cell">
            <div className="ticker-mark">{r.ticker}</div>
            <div>
              <div className="ticker-name">{r.ticker}</div>
              <div className="ticker-co">{r.company_name}</div>
            </div>
          </div>
        </td>
        <td colSpan="5" style={{ fontSize: 12.5, color: "var(--mute)" }}>
          Scan failed for {r.ticker} — {r.error}
        </td>
      </tr>
    );
  }

  const driftColor = r.drift_5d > 0 ? "up" : r.drift_5d < 0 ? "down" : "flat";
  const sparkColor = r.drift_5d > 0 ? "var(--gold)" : r.drift_5d < 0 ? "var(--mute)" : "var(--sky)";

  return (
    <tr className="row">
      <td>
        <div className="ticker-cell">
          <div className="ticker-mark">{r.ticker}</div>
          <div>
            <div className="ticker-name">{r.ticker}</div>
            <div className="ticker-co">{r.company_name}</div>
          </div>
        </div>
      </td>
      <td>
        <SignalBadge signal={r.signal} />
      </td>
      <td className="num">{fmt$(r.price)}</td>
      <td className={"num " + driftColor}>{fmtPct(r.drift_5d * 100)}</td>
      <td>
        <Sparkline values={r.sparkline} color={sparkColor} />
      </td>
      <td className="right">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
          <Button variant="primary" size="sm" onClick={onBuy} disabled={busy}>
            {busy ? "Placing…" : "Open paper buy"}
          </Button>
          {orderState?.placed === true && (
            <div style={{ fontSize: 10.5, color: "var(--gold)" }}>Placed</div>
          )}
          {orderState?.error && (
            <div style={{ fontSize: 10.5, color: "var(--mute)", maxWidth: 160, textAlign: "right" }}>
              {orderState.error}
            </div>
          )}
        </div>
      </td>
    </tr>
  );
}
