import { useMemo, useState } from "react";
import { GoldRule, SignalBadge, MetricCard } from "../components/atoms.jsx";
import { Loading, ErrorPanel, EmptyState } from "../components/StateBlock.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { getSignals } from "../api/client.js";
import { fmt$, fmtTimestamp } from "../lib/format.js";

const SIGNAL_FILTERS = ["ALL", "BULLISH", "BEARISH", "NEUTRAL"];

export default function SignalLogScreen() {
  const { data, error, loading, run } = useAsync(getSignals, []);
  const [signalFilter, setSignalFilter] = useState("ALL");
  const [tickerFilter, setTickerFilter] = useState("ALL");

  const records = data?.records || [];

  const tickers = useMemo(
    () => ["ALL", ...Array.from(new Set(records.map((r) => r.ticker)))],
    [records],
  );

  const filtered = records.filter(
    (r) =>
      (signalFilter === "ALL" || r.signal === signalFilter) &&
      (tickerFilter === "ALL" || r.ticker === tickerFilter),
  );

  const counts = {
    BULLISH: records.filter((r) => r.signal === "BULLISH").length,
    BEARISH: records.filter((r) => r.signal === "BEARISH").length,
    NEUTRAL: records.filter((r) => r.signal === "NEUTRAL").length,
  };
  const pct = (n) => (records.length ? ((n / records.length) * 100).toFixed(0) + "% of total" : "—");

  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow">
            <GoldRule width={20} /> Signal Log
          </div>
          <h2>Every signal, on the record.</h2>
          <p>
            Each call to the AI analyst writes a row to{" "}
            <code style={{ fontFamily: "var(--sans)", color: "var(--sky)", background: "var(--navy-3)", padding: "1px 6px", fontSize: 12 }}>
              signals_log.json
            </code>
            . Use the log to review reasoning against actual price action over time.
          </p>
        </div>
      </div>

      {loading && <Loading label="Loading signal history…" />}
      {!loading && error && <ErrorPanel message={error.detail || error.message} onRetry={() => run()} />}

      {!loading && !error && (
        <>
          <div className="kpi-grid" style={{ marginBottom: 24, gridTemplateColumns: "repeat(4, 1fr)" }}>
            <MetricCard label="Signals logged" value={records.length} sub="All time" />
            <MetricCard label="Bullish" value={counts.BULLISH} sub={pct(counts.BULLISH)} tone="gain" />
            <MetricCard label="Bearish" value={counts.BEARISH} sub={pct(counts.BEARISH)} tone="loss" />
            <MetricCard label="Neutral" value={counts.NEUTRAL} sub={pct(counts.NEUTRAL)} />
          </div>

          <div
            className="panel subtle"
            style={{ marginBottom: 24, padding: "16px 22px", display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}
          >
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span className="eyebrow">Signal</span>
              {SIGNAL_FILTERS.map((s) => (
                <button
                  key={s}
                  className="btn sm"
                  onClick={() => setSignalFilter(s)}
                  style={{
                    borderColor: signalFilter === s ? "var(--gold)" : "var(--rule)",
                    color: signalFilter === s ? "var(--gold)" : "var(--mute)",
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
              <span className="eyebrow">Ticker</span>
              <div className="field" style={{ height: 32, padding: "0 10px" }}>
                <select value={tickerFilter} onChange={(e) => setTickerFilter(e.target.value)}>
                  {tickers.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div style={{ marginLeft: "auto", fontSize: 11, color: "var(--mute)" }}>
              Showing <span style={{ color: "var(--white)" }}>{filtered.length}</span> of {records.length}
            </div>
          </div>

          <div className="panel">
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Ticker</th>
                    <th>Signal</th>
                    <th>Confidence</th>
                    <th className="num">Price</th>
                    <th>Reasoning</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((r, i) => (
                    <tr className="row" key={i}>
                      <td style={{ fontFamily: "var(--sans)", fontSize: 12, color: "var(--mute)", letterSpacing: "0.04em" }}>
                        {fmtTimestamp(r.timestamp)}
                      </td>
                      <td>
                        <div className="ticker-cell">
                          <div className="ticker-mark" style={{ width: 28, height: 28, fontSize: 10 }}>
                            {r.ticker}
                          </div>
                        </div>
                      </td>
                      <td>
                        <SignalBadge signal={r.signal} />
                      </td>
                      <td>
                        <span className="conf">{r.confidence}</span>
                      </td>
                      <td className="num">{fmt$(r.price)}</td>
                      <td style={{ fontSize: 12.5, color: "var(--mute)", maxWidth: 360 }}>{r.reasoning}</td>
                    </tr>
                  ))}
                  {filtered.length === 0 && (
                    <tr>
                      <td colSpan="6">
                        <EmptyState>No signals match the current filter.</EmptyState>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
