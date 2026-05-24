// ----- StockPilot App shell -----

const { useState, useEffect } = React;

function App() {
  const [tab, setTab] = useState("signal"); // signal | portfolio | history | discover
  const [portfolio, setPortfolio] = useState(window.SP_DATA.INITIAL_PORTFOLIO);
  const [history, setHistory] = useState(window.SP_DATA.SIGNAL_HISTORY);
  const [toast, setToast] = useState(null);

  // Clock for topbar
  const [now, setNow] = useState(new Date(2026, 4, 22, 14, 8, 12));
  useEffect(() => {
    const t = setInterval(() => setNow(d => new Date(d.getTime() + 1000)), 1000);
    return () => clearInterval(t);
  }, []);

  function showToast(t){
    setToast(t);
    setTimeout(() => setToast(null), 3200);
  }

  function onBuy(bundle, signal, qty){
    const cost = +(qty * bundle.current).toFixed(2);
    const existing = portfolio.positions.find(p => p.sym === bundle.symbol);
    let newPositions;
    if(existing){
      const totalShares = existing.shares + qty;
      const avg = +(((existing.avgCost * existing.shares) + (bundle.current * qty)) / totalShares).toFixed(2);
      newPositions = portfolio.positions.map(p => p.sym === bundle.symbol ? { ...p, shares: totalShares, avgCost: avg } : p);
    } else {
      newPositions = [...portfolio.positions, {
        sym: bundle.symbol,
        shares: qty,
        avgCost: bundle.current,
        signal: signal.signal,
        aiRec: signal.signal === "BULLISH" ? "HOLD" : "HOLD",
        recReason: signal.reasoning,
        openedOn: now.toLocaleDateString("en-US", { month:"short", day:"2-digit", year:"numeric" }),
      }];
    }
    setPortfolio({
      ...portfolio,
      cash: +(portfolio.cash - cost).toFixed(2),
      positions: newPositions,
    });
    setHistory([
      { ts: fmtTs(now), sym: bundle.symbol, signal: signal.signal, confidence: signal.confidence, price: bundle.current,
        acted: `BUY  ${qty} sh @ ${bundle.current.toFixed(2)}`, ack: true },
      ...history,
    ]);
    showToast({ ttl: "Paper order filled", msg: `${qty} sh ${bundle.symbol} @ ${fmt$(bundle.current)} · Alpaca paper` });
  }

  function onSell(sym){
    const pos = portfolio.positions.find(p => p.sym === sym);
    if(!pos) return;
    const b = window.SP_DATA.buildBundle(sym);
    const proceeds = +(pos.shares * (b ? b.current : pos.avgCost)).toFixed(2);
    setPortfolio({
      ...portfolio,
      cash: +(portfolio.cash + proceeds).toFixed(2),
      positions: portfolio.positions.filter(p => p.sym !== sym),
    });
    setHistory([
      { ts: fmtTs(now), sym, signal: "BEARISH", confidence: "Moderate", price: b ? b.current : pos.avgCost,
        acted: `SELL ${pos.shares} sh @ ${(b ? b.current : pos.avgCost).toFixed(2)}`, ack: true },
      ...history,
    ]);
    showToast({ ttl: "Position closed", msg: `${pos.shares} sh ${sym} · proceeds ${fmt$(proceeds)}` });
  }

  function fmtTs(d){
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  // Top right market summary
  const isMarketOpen = now.getHours() >= 8 && now.getHours() < 15; // 9:30-4 CT close enough
  const portValue = portfolio.positions.reduce((s, p) => {
    const b = window.SP_DATA.buildBundle(p.sym);
    return s + (b ? b.current : p.avgCost) * p.shares;
  }, 0) + portfolio.cash;

  const titles = {
    signal: { ttl: "Signal Analysis", sub: "Run any ticker through the AI analyst." },
    portfolio: { ttl: "Paper Portfolio", sub: "Marked-to-market against the morning's close." },
    history: { ttl: "Signal History", sub: "Every signal generated, with audit trail." },
    discover: { ttl: "Discover", sub: "Ideas from your watchlist universe." },
  }[tab];

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <NorthStar size={420} opacity={0.04} className="" />
        <div style={{position: "absolute", top: -120, left: -120, color: "var(--sky)" }}>
          <NorthStar size={420} opacity={0.04}/>
        </div>

        <div className="brand">
          <Wordmark />
          <div className="product">StockPilot<span className="dot"></span></div>
          <div className="tagline">AI-assisted paper trading — Minnesota-built, board-room serious.</div>
        </div>

        <nav className="nav">
          <div className="nav-section">Trade</div>
          <button className={"nav-item " + (tab==="signal" ? "active" : "")} onClick={() => setTab("signal")}>
            <I name="signal" /> Signal
          </button>
          <button className={"nav-item " + (tab==="portfolio" ? "active" : "")} onClick={() => setTab("portfolio")}>
            <I name="portfolio" /> Portfolio
            <span className="badge">{portfolio.positions.length}</span>
          </button>
          <button className={"nav-item " + (tab==="discover" ? "active" : "")} onClick={() => setTab("discover")}>
            <I name="discover" /> Discover
          </button>

          <div className="nav-section">Activity</div>
          <button className={"nav-item " + (tab==="history" ? "active" : "")} onClick={() => setTab("history")}>
            <I name="history" /> Signal log
          </button>
          <button className="nav-item" disabled style={{ opacity: 0.5, cursor: "default" }}>
            <I name="settings" /> Settings
          </button>
        </nav>

        <div className="footer-area">
          <div className="acct-kpis">
            <div className="row"><span>Paper account</span><span className="v">Active</span></div>
            <div className="row"><span>Account value</span><span className="v mono-num">{fmt$(portValue)}</span></div>
            <div className="row"><span>Cash</span><span className="v mono-num">{fmt$(portfolio.cash)}</span></div>
          </div>
          <div className="acct">
            <div className="av">BK</div>
            <div>
              <div className="name">Brian Kopp</div>
              <div className="role">Portfolio Manager</div>
            </div>
          </div>
          <div style={{ fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--mute)" }}>
            <GoldRule width={14}/> v1.0 · M4 build
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="main">
        <NorthStar size={520} opacity={0.04} className="" />

        <header className="topbar">
          <div className="crumb">
            <h1>{titles.ttl}</h1>
            <span className="sub">{titles.sub}</span>
          </div>
          <div className="market">
            <div className="ind">
              <span className="dot" style={{ background: isMarketOpen ? "var(--gold)" : "var(--mute)" }}></span>
              <span style={{ letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 10 }}>NYSE</span>
              <span className="v">{isMarketOpen ? "Open" : "Closed"}</span>
            </div>
            <div className="ind">
              <span style={{ letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 10 }}>S&amp;P 500</span>
              <span className="v">5,847.12</span>
              <span style={{ color: "var(--gold)" }}>+0.42%</span>
            </div>
            <div className="ind">
              <span style={{ letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 10 }}>VIX</span>
              <span className="v">13.84</span>
            </div>
            <div className="ind" style={{ borderLeft: "1px solid var(--rule)", paddingLeft: 22 }}>
              <span style={{ letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 10 }}>CT</span>
              <span className="v mono-num">{now.toLocaleTimeString("en-US", { hour12: false })}</span>
            </div>
          </div>
        </header>

        <section className="content">
          {tab === "signal" && <SignalScreen portfolio={portfolio} onBuy={onBuy} />}
          {tab === "portfolio" && <PortfolioScreen portfolio={portfolio} onSell={onSell} />}
          {tab === "history" && <HistoryScreen history={history} />}
          {tab === "discover" && <DiscoverScreen discover={window.SP_DATA.DISCOVER} onBuy={onBuy} />}
        </section>
      </main>

      {toast && (
        <div className="toast">
          <div className="pip-i"></div>
          <div>
            <div className="ttl">{toast.ttl}</div>
            <div className="msg">{toast.msg}</div>
          </div>
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
