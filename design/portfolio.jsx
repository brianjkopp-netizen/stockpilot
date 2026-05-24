// ----- Portfolio screen -----

function PortfolioScreen({ portfolio, onSell, onSetRec }) {
  // Compute live values per position using deterministic bundles
  const positions = portfolio.positions.map(p => {
    const b = window.SP_DATA.buildBundle(p.sym);
    const mkt = b ? b.current : p.avgCost;
    const value = +(p.shares * mkt).toFixed(2);
    const cost = +(p.shares * p.avgCost).toFixed(2);
    const pl = +(value - cost).toFixed(2);
    const plPct = +(((mkt - p.avgCost)/p.avgCost) * 100).toFixed(2);
    return { ...p, mkt, value, cost, pl, plPct, series: b ? b.series.slice(-14) : [] };
  });
  const positionsValue = positions.reduce((s, p) => s + p.value, 0);
  const totalValue = positionsValue + portfolio.cash;
  const totalPL = totalValue - portfolio.startingCash;
  const totalPLPct = (totalPL / portfolio.startingCash) * 100;
  const dayPL = positions.reduce((s, p) => {
    const b = window.SP_DATA.buildBundle(p.sym);
    if(!b) return s;
    return s + (b.change * p.shares);
  }, 0);

  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow"><GoldRule width={20}/> Portfolio Intelligence</div>
          <h2>One paper account. One view.</h2>
          <p>Live position values, daily P&amp;L, and an AI recommendation on every holding — refreshed against the morning's market data.</p>
        </div>
        <div style={{ display:"flex", gap: 10 }}>
          <button className="btn ghost"><I name="refresh" size={14}/> Refresh recs</button>
          <button className="btn">Export CSV</button>
        </div>
      </div>

      <div className="kpi-grid" style={{ marginBottom: 24 }}>
        <div className="kpi">
          <div className="lab">Account value</div>
          <div className="val">{fmt$(totalValue)}</div>
          <div className="delta">Starting {fmt$(portfolio.startingCash)}</div>
        </div>
        <div className="kpi">
          <div className="lab">Total P&amp;L</div>
          <div className="val" style={{ color: totalPL >= 0 ? "var(--gold)" : "var(--mute)" }}>{(totalPL >= 0 ? "+" : "") + fmt$(totalPL)}</div>
          <div className="delta">{fmtPct(totalPLPct)} since start</div>
        </div>
        <div className="kpi">
          <div className="lab">Today's P&amp;L</div>
          <div className="val" style={{ color: dayPL >= 0 ? "var(--gold)" : "var(--mute)" }}>{(dayPL >= 0 ? "+" : "") + fmt$(dayPL)}</div>
          <div className="delta">{positions.length} positions marked-to-market</div>
        </div>
        <div className="kpi">
          <div className="lab">Cash · paper</div>
          <div className="val">{fmt$(portfolio.cash)}</div>
          <div className="delta">{((portfolio.cash/totalValue)*100).toFixed(1)}% allocation</div>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 24 }}>
        <div className="panel-hd">
          <div className="ttl">Open positions</div>
          <div className="meta">{positions.length} held · {fmt$(positionsValue)} marked</div>
        </div>
        <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Ticker</th>
              <th className="num">Shares</th>
              <th className="num">Avg cost</th>
              <th className="num">Market</th>
              <th className="num">Value</th>
              <th className="num">P&amp;L</th>
              <th>Trend · 14d</th>
              <th>AI rec</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {positions.map(p => (
              <tr className="row" key={p.sym}>
                <td>
                  <div className="ticker-cell">
                    <div className="ticker-mark">{p.sym}</div>
                    <div>
                      <div className="ticker-name">{window.SP_DATA.TICKERS[p.sym]?.name || p.sym}</div>
                      <div className="ticker-co">Opened {p.openedOn}</div>
                    </div>
                  </div>
                </td>
                <td className="num">{p.shares}</td>
                <td className="num">{fmt$(p.avgCost)}</td>
                <td className="num">{fmt$(p.mkt)}</td>
                <td className="num">{fmt$(p.value)}</td>
                <td className="num" style={{ color: p.pl >= 0 ? "var(--gold)" : "var(--mute)" }}>
                  <div>{(p.pl >= 0 ? "+" : "") + fmt$(p.pl)}</div>
                  <div style={{ fontSize: 11, color: "var(--mute)" }}>{fmtPct(p.plPct)}</div>
                </td>
                <td>
                  <Sparkline values={p.series} color={p.signal === "BULLISH" ? "var(--gold)" : p.signal === "BEARISH" ? "var(--mute)" : "var(--sky)"} />
                </td>
                <td>
                  <RecPill rec={p.aiRec} />
                </td>
                <td className="right">
                  <div style={{ display:"flex", justifyContent: "flex-end", gap: 8 }}>
                    {p.aiRec === "ADD" && <button className="btn sm primary">Add</button>}
                    {p.aiRec === "SELL" && <button className="btn sm danger" onClick={() => onSell(p.sym)}>Close</button>}
                    {p.aiRec === "HOLD" && <button className="btn sm ghost">Hold</button>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>

      {/* Reasoning rail */}
      <div className="panel subtle">
        <div className="panel-hd">
          <div className="ttl">Daily AI brief</div>
          <div className="meta">May 22, 2026 · 8:31 AM CT</div>
        </div>
        <div className="panel-bd">
          <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 18 }}>
            {positions.map(p => (
              <div key={p.sym} style={{ background: "var(--royal-2)", padding: "18px 20px", borderLeft: "2px solid " + (p.aiRec === "SELL" ? "var(--mute)" : p.aiRec === "ADD" ? "var(--gold)" : "var(--sky)") }}>
                <div style={{ display:"flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                  <div>
                    <div className="num" style={{ fontSize: 18 }}>{p.sym}</div>
                    <div style={{ fontSize: 11, color: "var(--mute)", marginTop: 2 }}>{window.SP_DATA.TICKERS[p.sym]?.name}</div>
                  </div>
                  <RecPill rec={p.aiRec} />
                </div>
                <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "rgba(255,255,255,0.92)" }}>{p.recReason}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function RecPill({rec}){
  const map = {
    HOLD: { c: "var(--sky)" },
    ADD:  { c: "var(--gold)" },
    SELL: { c: "var(--mute)" },
    BUY:  { c: "var(--gold)" },
    WATCH:{ c: "var(--sky)" },
  };
  const v = map[rec] || { c: "var(--mute)" };
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 8,
      fontSize: 10.5, letterSpacing: "0.2em", textTransform: "uppercase",
      color: v.c, padding: "5px 10px", border: "1px solid " + v.c,
      fontWeight: 500,
    }}>
      <span style={{ width: 6, height: 6, background: v.c }}></span>
      {rec}
    </span>
  );
}

window.PortfolioScreen = PortfolioScreen;
window.RecPill = RecPill;
