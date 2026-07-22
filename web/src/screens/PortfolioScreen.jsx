import { useState } from "react";
import { GoldRule, Sparkline, Button } from "../components/atoms.jsx";
import { Loading, ErrorPanel, EmptyState } from "../components/StateBlock.jsx";
import ConfirmOrder from "../components/ConfirmOrder.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { getPortfolio, getRecommendation, placeOrder } from "../api/client.js";
import { fmt$, fmtN, fmtPct } from "../lib/format.js";
import { estimateBuyOrder } from "../lib/orderEstimate.js";

const REC_COLORS = { HOLD: "var(--sky)", ADD: "var(--gold)", SELL: "var(--mute)" };

async function fetchRecommendations(tickers) {
  const entries = await Promise.all(
    tickers.map(async (ticker) => {
      try {
        const rec = await getRecommendation(ticker);
        return [ticker, rec];
      } catch (err) {
        return [ticker, { ticker, error: err.detail || err.message }];
      }
    }),
  );
  return Object.fromEntries(entries);
}

export default function PortfolioScreen() {
  const {
    data: portfolio,
    error: portfolioError,
    loading: portfolioLoading,
    run: refetchPortfolio,
  } = useAsync(getPortfolio, []);

  const positions = portfolio?.positions ?? [];
  const tickers = positions.map((p) => p.ticker);
  const tickersKey = tickers.join(",");

  const {
    data: recsByTicker,
    loading: recsLoading,
    run: refetchRecs,
  } = useAsync(() => fetchRecommendations(tickers), [tickersKey], { immediate: tickers.length > 0 });

  const [orderState, setOrderState] = useState({});
  const [confirm, setConfirm] = useState(null);

  async function handleOrder(ticker, body) {
    setOrderState((s) => ({ ...s, [ticker]: { loading: true, error: null } }));
    try {
      const result = await placeOrder({ ticker, ...body });
      if (!result.placed) {
        setOrderState((s) => ({
          ...s,
          [ticker]: { loading: false, error: result.reason || "Order not placed" },
        }));
        return;
      }
      setOrderState((s) => ({ ...s, [ticker]: { loading: false, error: null } }));
      await refetchPortfolio();
    } catch (err) {
      setOrderState((s) => ({ ...s, [ticker]: { loading: false, error: err.detail || err.message } }));
    }
  }

  function requestAdd(position, rec) {
    const { qty, notional } = estimateBuyOrder(rec.confidence, position.mark_price);
    setConfirm({
      ticker: position.ticker,
      side: "buy",
      price: position.mark_price,
      qty,
      notional,
      isClose: false,
      body: { side: "buy", signal: rec.signal, confidence: rec.confidence },
    });
  }

  function requestClose(position) {
    setConfirm({
      ticker: position.ticker,
      side: "sell",
      price: position.mark_price,
      qty: position.qty,
      notional: position.qty * position.mark_price,
      isClose: true,
      body: { side: "sell", qty: position.qty },
    });
  }

  async function handleConfirm() {
    if (!confirm || confirm.submitting) return;
    const { ticker, body } = confirm;
    setConfirm((c) => (c ? { ...c, submitting: true } : c));
    await handleOrder(ticker, body);
    setConfirm(null);
  }

  if (portfolioLoading) {
    return (
      <div>
        <PortfolioHeading onRefreshRecs={refetchRecs} recsLoading={recsLoading} refreshDisabled />
        <Loading label="Loading portfolio — fetching live positions from Alpaca…" />
      </div>
    );
  }

  if (portfolioError) {
    return (
      <div>
        <PortfolioHeading onRefreshRecs={refetchRecs} recsLoading={recsLoading} refreshDisabled />
        <ErrorPanel message={portfolioError.detail || portfolioError.message} onRetry={refetchPortfolio} />
      </div>
    );
  }

  const totals = portfolio.totals;
  const account = portfolio.account;

  return (
    <div>
      <PortfolioHeading onRefreshRecs={refetchRecs} recsLoading={recsLoading} refreshDisabled={positions.length === 0} />

      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        <div className="kpi">
          <div className="lab">Account value</div>
          <div className="val">{fmt$(account.portfolio_value)}</div>
          <div className="delta">
            {positions.length} position{positions.length === 1 ? "" : "s"} · {fmt$(totals.market_value)} marked
          </div>
        </div>
        <div className="kpi">
          <div className="lab">Unrealized P&amp;L</div>
          <div className="val" style={{ color: totals.unrealized_pl >= 0 ? "var(--gold)" : "var(--mute)" }}>
            {(totals.unrealized_pl >= 0 ? "+" : "") + fmt$(totals.unrealized_pl)}
          </div>
          <div className="delta">{fmtPct(totals.unrealized_plpc * 100)} vs. cost basis</div>
        </div>
        <div className="kpi">
          <div className="lab">Today's P&amp;L</div>
          <div className="val" style={{ color: totals.daily_pl >= 0 ? "var(--gold)" : "var(--mute)" }}>
            {(totals.daily_pl >= 0 ? "+" : "") + fmt$(totals.daily_pl)}
          </div>
          <div className="delta">{fmtPct(totals.daily_plpc * 100)} today</div>
        </div>
        <div className="kpi">
          <div className="lab">Cash · paper</div>
          <div className="val">{fmt$(account.cash)}</div>
          <div className="delta">
            {account.portfolio_value ? ((account.cash / account.portfolio_value) * 100).toFixed(1) : "0.0"}% allocation
          </div>
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="panel subtle">
          <EmptyState>No open positions yet. Paper trades you place will show up here.</EmptyState>
        </div>
      ) : (
        <>
          <div className="panel" style={{ marginBottom: 24 }}>
            <div className="panel-hd">
              <div className="ttl">Open positions</div>
              <div className="meta">
                {positions.length} held · {fmt$(totals.market_value)} marked
              </div>
            </div>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Ticker</th>
                    <th className="num">Shares</th>
                    <th className="num">Avg entry</th>
                    <th className="num">Market</th>
                    <th className="num">Value</th>
                    <th className="num">Unrealized P&amp;L</th>
                    <th className="num">Daily P&amp;L</th>
                    <th>Trend · 14d</th>
                    <th>AI rec</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => (
                    <PositionRow
                      key={p.ticker}
                      position={p}
                      rec={recsByTicker?.[p.ticker]}
                      recsLoading={recsLoading}
                      orderState={orderState[p.ticker]}
                      onAdd={() => requestAdd(p, recsByTicker[p.ticker])}
                      onClose={() => requestClose(p)}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel subtle">
            <div className="panel-hd">
              <div className="ttl">Daily AI brief</div>
              <div className="meta">{recsLoading ? "Refreshing…" : `${positions.length} position${positions.length === 1 ? "" : "s"}`}</div>
            </div>
            <div className="panel-bd">
              {recsLoading && !recsByTicker ? (
                <Loading label="Consulting the AI analyst on every position…" />
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 18 }}>
                  {positions.map((p) => {
                    const rec = recsByTicker?.[p.ticker];
                    const verdict = rec?.verdict;
                    const color = REC_COLORS[verdict] || "var(--mute)";
                    return (
                      <div
                        key={p.ticker}
                        style={{ background: "var(--royal-2)", padding: "18px 20px", borderLeft: "2px solid " + color }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                          <div className="num" style={{ fontSize: 18 }}>
                            {p.ticker}
                          </div>
                          {verdict ? <RecPill rec={verdict} /> : <span style={{ fontSize: 11, color: "var(--mute)" }}>—</span>}
                        </div>
                        <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "rgba(255,255,255,0.92)" }}>
                          {rec?.error ? `Recommendation unavailable — ${rec.error}` : rec?.brief || "—"}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <ConfirmOrder
        order={confirm}
        submitting={confirm?.submitting}
        onConfirm={handleConfirm}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}

function PortfolioHeading({ onRefreshRecs, recsLoading, refreshDisabled }) {
  return (
    <div className="heading-block">
      <div className="lead">
        <div className="eyebrow">
          <GoldRule width={20} /> Portfolio Intelligence
        </div>
        <h2>One paper account. One view.</h2>
        <p>
          Live position values, daily P&amp;L, and an AI recommendation on every holding — refreshed against the
          latest market data.
        </p>
      </div>
      <Button variant="ghost" icon="refresh" onClick={onRefreshRecs} disabled={recsLoading || refreshDisabled}>
        {recsLoading ? "Refreshing" : "Refresh recs"}
      </Button>
    </div>
  );
}

function RecPill({ rec }) {
  const color = REC_COLORS[rec] || "var(--mute)";
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        fontSize: 10.5,
        letterSpacing: "0.2em",
        textTransform: "uppercase",
        color,
        padding: "5px 10px",
        border: "1px solid " + color,
        fontWeight: 500,
      }}
    >
      <span style={{ width: 6, height: 6, background: color }}></span>
      {rec}
    </span>
  );
}

function PositionRow({ position: p, rec, recsLoading, orderState, onAdd, onClose }) {
  const gainColor = p.unrealized_pl >= 0 ? "var(--gold)" : "var(--mute)";
  const dailyColor = p.daily_pl >= 0 ? "var(--gold)" : "var(--mute)";
  const verdict = rec?.verdict;
  const busy = orderState?.loading;

  return (
    <tr className="row">
      <td>
        <div className="ticker-cell">
          <div className="ticker-mark">{p.ticker}</div>
        </div>
      </td>
      <td className="num">{fmtN(p.qty)}</td>
      <td className="num">{fmt$(p.avg_entry_price)}</td>
      <td className="num">{fmt$(p.mark_price)}</td>
      <td className="num">{fmt$(p.market_value)}</td>
      <td className="num" style={{ color: gainColor }}>
        <div>{(p.unrealized_pl >= 0 ? "+" : "") + fmt$(p.unrealized_pl)}</div>
        <div style={{ fontSize: 11, color: "var(--mute)" }}>{fmtPct(p.unrealized_plpc * 100)}</div>
      </td>
      <td className="num" style={{ color: dailyColor }}>
        <div>{(p.daily_pl >= 0 ? "+" : "") + fmt$(p.daily_pl)}</div>
        <div style={{ fontSize: 11, color: "var(--mute)" }}>{fmtPct(p.daily_plpc * 100)}</div>
      </td>
      <td>
        <Sparkline values={p.sparkline} color={gainColor} />
      </td>
      <td>
        {rec?.error ? (
          <span style={{ fontSize: 11, color: "var(--mute)" }}>Unavailable</span>
        ) : verdict ? (
          <RecPill rec={verdict} />
        ) : (
          <span style={{ fontSize: 11, color: "var(--mute)" }}>{recsLoading ? "Loading…" : "—"}</span>
        )}
      </td>
      <td className="right">
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            {verdict === "ADD" && (
              <Button variant="primary" size="sm" onClick={onAdd} disabled={busy}>
                {busy ? "Placing…" : "Add"}
              </Button>
            )}
            {verdict === "SELL" && (
              <Button variant="danger" size="sm" onClick={onClose} disabled={busy}>
                {busy ? "Placing…" : "Close"}
              </Button>
            )}
            {verdict === "HOLD" && (
              <Button variant="ghost" size="sm" disabled>
                Hold
              </Button>
            )}
          </div>
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
