// ----- Discover screen: AI-recommended stocks outside current portfolio -----

function DiscoverScreen({ discover, onBuy }) {
  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow"><GoldRule width={20}/> Discover</div>
          <h2>Ideas worth looking at.</h2>
          <p>The AI scans a watchlist outside your current holdings and surfaces names with constructive setups. Click into any card to see the full analysis, or open a paper position directly.</p>
        </div>
        <div style={{ display:"flex", gap: 10 }}>
          <button className="btn ghost"><I name="refresh" size={14}/> Refresh scan</button>
          <button className="btn">Edit watchlist</button>
        </div>
      </div>

      <div className="panel subtle" style={{ marginBottom: 24, padding: "16px 22px", display: "flex", gap: 20, alignItems: "center" }}>
        <span className="pip-i"></span>
        <span style={{ fontSize: 12.5, color: "rgba(255,255,255,0.92)" }}>
          Scan run <strong>May 22, 2026 · 8:31 AM CT</strong> against a 14-name watchlist. 3 candidates surfaced. 2 actionable, 1 watch-only.
        </span>
      </div>

      <div className="card-grid">
        {discover.map(d => {
          const b = window.SP_DATA.buildBundle(d.sym);
          return (
            <div className="disc-card" key={d.sym}>
              <div className="head">
                <div>
                  <div className="num" style={{ fontSize: 24 }}>{d.sym}</div>
                  <div style={{ fontSize: 11.5, color: "var(--mute)", marginTop: 4 }}>{window.SP_DATA.TICKERS[d.sym]?.name}</div>
                </div>
                <SignalBadge signal={d.signal} />
              </div>

              <div style={{ display: "flex", alignItems: "flex-end", gap: 18 }}>
                <div>
                  <div className="eyebrow">Last</div>
                  <div className="num" style={{ fontSize: 22, marginTop: 4 }}>{fmt$(d.price)}</div>
                  <div style={{ fontSize: 12, color: "var(--gold)", marginTop: 2 }}>{d.drift} · 5d</div>
                </div>
                <div style={{ flex: 1, height: 60 }}>
                  {b && <Sparkline values={b.series.slice(-14)} color="var(--sky)" width={200} height={60} />}
                </div>
              </div>

              <div style={{ fontSize: 12.5, lineHeight: 1.6, color: "rgba(255,255,255,0.92)" }}>{d.thesis}</div>

              <div style={{ borderTop: "1px solid var(--rule)", paddingTop: 14, display:"flex", justifyContent:"space-between", alignItems:"center", marginTop: "auto" }}>
                <div>
                  <div className="eyebrow">Rec size</div>
                  <div style={{ fontSize: 12.5, marginTop: 2, color: d.recSize === "Watch" ? "var(--sky)" : "var(--white)" }}>{d.recSize}</div>
                </div>
                <div style={{ display:"flex", gap: 8 }}>
                  <button className="btn sm">Inspect</button>
                  {d.recSize !== "Watch" && b && (
                    <button className="btn sm primary" onClick={() => onBuy(b, { signal: d.signal, confidence: d.confidence, reasoning: d.thesis }, parseInt(d.recSize.match(/\d+/)?.[0] || "10"))}>
                      Open paper buy
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="panel subtle" style={{ marginTop: 24 }}>
        <div className="panel-hd">
          <div className="ttl">Watchlist universe</div>
          <div className="meta">14 names · 1 scan/day</div>
        </div>
        <div className="panel-bd">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {["CAT","AMD","GOOG","ASML","COST","TSM","UNH","V","JPM","ABBV","LIN","NEE","DUK","RKT"].map(s => (
              <span key={s} style={{
                fontSize: 11.5, padding: "6px 12px",
                border: "1px solid var(--rule)",
                color: "var(--mute)",
                letterSpacing: "0.04em",
                fontFamily: "var(--sans)",
              }}>{s}</span>
            ))}
            <button className="btn sm ghost" style={{ height: 28 }}>+ Add ticker</button>
          </div>
        </div>
      </div>
    </div>
  );
}

window.DiscoverScreen = DiscoverScreen;
