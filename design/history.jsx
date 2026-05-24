// ----- History screen: signals_log.json viewer -----

function HistoryScreen({ history }) {
  const [filter, setFilter] = React.useState("ALL"); // ALL | BULLISH | BEARISH | NEUTRAL
  const [tickerFilter, setTickerFilter] = React.useState("ALL");

  const tickers = ["ALL", ...Array.from(new Set(history.map(h => h.sym)))];

  const filtered = history.filter(h =>
    (filter === "ALL" || h.signal === filter) &&
    (tickerFilter === "ALL" || h.sym === tickerFilter)
  );

  const counts = {
    BULLISH: history.filter(h => h.signal === "BULLISH").length,
    BEARISH: history.filter(h => h.signal === "BEARISH").length,
    NEUTRAL: history.filter(h => h.signal === "NEUTRAL").length,
  };

  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow"><GoldRule width={20}/> Signal Log</div>
          <h2>Every signal, on the record.</h2>
          <p>Each call writes a row to <code style={{fontFamily:"var(--sans)", color:"var(--sky)", background:"var(--navy-3)", padding:"1px 6px", fontSize: 12}}>signals_log.json</code>. Use the log to backtest reasoning against actual price action and tune confidence thresholds.</p>
        </div>
        <div style={{ display:"flex", gap: 10 }}>
          <button className="btn ghost">Export JSON</button>
        </div>
      </div>

      {/* Mini KPIs */}
      <div className="kpi-grid" style={{ marginBottom: 24, gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="kpi">
          <div className="lab">Signals logged</div>
          <div className="val">{history.length}</div>
          <div className="delta">Last 7 days</div>
        </div>
        <div className="kpi">
          <div className="lab">Bullish</div>
          <div className="val" style={{ color: "var(--gold)" }}>{counts.BULLISH}</div>
          <div className="delta">{((counts.BULLISH/history.length)*100).toFixed(0)}% of total</div>
        </div>
        <div className="kpi">
          <div className="lab">Bearish</div>
          <div className="val">{counts.BEARISH}</div>
          <div className="delta">{((counts.BEARISH/history.length)*100).toFixed(0)}% of total</div>
        </div>
        <div className="kpi">
          <div className="lab">Neutral</div>
          <div className="val" style={{ color: "var(--sky)" }}>{counts.NEUTRAL}</div>
          <div className="delta">{((counts.NEUTRAL/history.length)*100).toFixed(0)}% of total</div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="panel subtle" style={{ marginBottom: 24, padding: "16px 22px", display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span className="eyebrow">Signal</span>
          {["ALL","BULLISH","BEARISH","NEUTRAL"].map(s => (
            <button key={s}
              className="btn sm"
              onClick={() => setFilter(s)}
              style={{
                borderColor: filter === s ? "var(--gold)" : "var(--rule)",
                color: filter === s ? "var(--gold)" : "var(--mute)",
              }}
            >{s}</button>
          ))}
        </div>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span className="eyebrow">Ticker</span>
          <div className="field" style={{ height: 32, padding: "0 10px" }}>
            <select
              value={tickerFilter}
              onChange={(e) => setTickerFilter(e.target.value)}
              style={{ background: "transparent", border: "none", color: "var(--white)", fontFamily: "var(--sans)", fontSize: 12, outline: "none", letterSpacing: "0.08em", appearance: "none", paddingRight: 14 }}
            >
              {tickers.map(t => <option key={t} value={t} style={{ background: "var(--navy-2)" }}>{t}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginLeft: "auto", fontSize: 11, color: "var(--mute)" }}>
          Showing <span style={{ color: "var(--white)" }}>{filtered.length}</span> of {history.length}
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
              <th>Action taken</th>
              <th>Review</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((h, i) => (
              <tr className="row" key={i}>
                <td style={{ fontFamily: "var(--sans)", fontSize: 12, color: "var(--mute)", letterSpacing: "0.04em" }}>{h.ts}</td>
                <td>
                  <div className="ticker-cell">
                    <div className="ticker-mark" style={{ width: 28, height: 28, fontSize: 10 }}>{h.sym}</div>
                    <div className="ticker-name">{window.SP_DATA.TICKERS[h.sym]?.name || h.sym}</div>
                  </div>
                </td>
                <td><SignalBadge signal={h.signal} /></td>
                <td><span className="conf">{h.confidence}</span></td>
                <td className="num">{fmt$(h.price)}</td>
                <td style={{ fontSize: 12.5, color: h.acted.startsWith("BUY") || h.acted.startsWith("ADD") ? "var(--gold)" : h.acted.startsWith("SELL") ? "var(--mute)" : "var(--white)" }}>
                  {h.acted}
                </td>
                <td className="right">
                  {h.ack ? (
                    <span style={{ color: "var(--mute)", fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase" }}>✓ Reviewed</span>
                  ) : (
                    <span style={{ color: "var(--gold)", fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase" }}>● Unreviewed</span>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan="7" style={{ padding: 40, textAlign: "center", color: "var(--mute)", fontSize: 12.5 }}>No signals match the current filter.</td></tr>
            )}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}

window.HistoryScreen = HistoryScreen;
