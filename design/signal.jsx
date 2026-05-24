// ----- Signal screen: ticker -> AI analysis -----

function SignalScreen({ portfolio, onBuy }) {
  const [ticker, setTicker] = React.useState("AAPL");
  const [pending, setPending] = React.useState("AAPL");      // shown in topline
  const [bundle, setBundle] = React.useState(() => window.SP_DATA.buildBundle("AAPL"));
  const [signal, setSignal] = React.useState(() => window.SP_DATA.deriveSignal(window.SP_DATA.buildBundle("AAPL")));
  const [phase, setPhase] = React.useState("idle"); // idle | fetching | indicators | calling | parsing | done | error
  const [error, setError] = React.useState(null);
  const [reasoningText, setReasoningText] = React.useState(signal ? signal.reasoning : "");
  const [showTrade, setShowTrade] = React.useState(false);

  const phases = [
    { id: "fetching",   label: "Fetching market data",         ms: 700,  detail: "yfinance · 30d OHLCV" },
    { id: "indicators", label: "Computing indicators",         ms: 400,  detail: "MA 10 · MA 20 · volume" },
    { id: "calling",    label: "Querying Anthropic API",       ms: 1100, detail: "claude-sonnet-4 · 1 turn" },
    { id: "parsing",    label: "Parsing signal & confidence",  ms: 350,  detail: "schema validation" },
  ];

  function run(sym) {
    const SYM = sym.toUpperCase().trim();
    if(!SYM) return;
    setTicker(SYM);
    setPending(SYM);
    setError(null);
    setPhase("fetching");

    const next = window.SP_DATA.buildBundle(SYM);
    if(!next){
      // Simulate the lookup attempt, then error
      setTimeout(() => {
        setError(`Ticker '${SYM}' returned no data. Verify the symbol and try again.`);
        setPhase("error");
      }, 800);
      return;
    }

    let cumulative = 0;
    phases.forEach((p) => {
      cumulative += p.ms;
      setTimeout(() => setPhase(p.id), cumulative);
    });

    // After all phases, reveal result and typewrite the reasoning
    setTimeout(() => {
      setBundle(next);
      const s = window.SP_DATA.deriveSignal(next);
      setSignal(s);
      setReasoningText("");
      setPhase("done");
      // Typewriter
      let i = 0;
      const full = s.reasoning;
      const tick = () => {
        i = Math.min(i + 4, full.length);
        setReasoningText(full.slice(0, i));
        if(i < full.length) setTimeout(tick, 14);
      };
      tick();
    }, cumulative + 50);
  }

  const ticking = phase !== "idle" && phase !== "done" && phase !== "error";
  const phaseIndex = phases.findIndex((p) => p.id === phase);

  const inPortfolio = portfolio.positions.find(p => p.sym === pending);

  // ---- Render ----
  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow"><GoldRule width={20}/> AI Signal Analysis</div>
          <h2>Ask the analyst.</h2>
          <p>Type a ticker. StockPilot pulls 30 days of market data, computes indicators, and asks Claude for a structured signal — bullish, bearish, or neutral — with a confidence read and plain-language reasoning.</p>
        </div>
        <div style={{ display:"flex", gap: 10 }}>
          <button className="btn ghost" onClick={() => run(pending)} disabled={ticking}>
            <I name="refresh" size={14} /> Re-analyze
          </button>
        </div>
      </div>

      {/* Ticker entry */}
      <div className="panel subtle" style={{ marginBottom: 24 }}>
        <div style={{ padding: 22, display:"grid", gridTemplateColumns: "1fr auto auto", gap: 14, alignItems: "stretch" }}>
          <div className="field">
            <span className="label">Ticker</span>
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && run(ticker)}
              placeholder="e.g. AAPL, NVDA, TSLA"
              maxLength="8"
              style={{ textTransform: "uppercase", letterSpacing: "0.12em", fontSize: 15 }}
              disabled={ticking}
            />
          </div>
          <div className="field" style={{ width: 180 }}>
            <span className="label">Range</span>
            <input value="30 days" readOnly />
          </div>
          <button className="btn primary" onClick={() => run(ticker)} disabled={ticking}>
            <I name="play" size={13} /> {ticking ? "Analyzing" : "Analyze"}
          </button>
        </div>
        <div style={{ padding: "0 22px 18px 22px", display: "flex", gap: 18, color: "var(--mute)", fontSize: 11.5, alignItems: "center" }}>
          <span style={{ letterSpacing: "0.16em", textTransform: "uppercase", fontSize: 10 }}>Try</span>
          {["AAPL","NVDA","TSLA","MSFT","AMD","GOOG","CAT","ZZZZ"].map(s => (
            <button
              key={s}
              onClick={() => { setTicker(s); run(s); }}
              disabled={ticking}
              style={{ color: s === "ZZZZ" ? "var(--gold)" : "var(--sky)", fontSize: 11.5, letterSpacing: "0.06em", padding: 0 }}
            >
              {s}{s === "ZZZZ" ? " ⟵ try invalid" : ""}
            </button>
          ))}
        </div>
      </div>

      {/* Pipeline status */}
      {(ticking || phase === "error") && (
        <div className="panel subtle" style={{ marginBottom: 24, padding: 22 }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Pipeline · {pending}</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 1, background: "var(--rule)", border: "1px solid var(--rule)" }}>
            {phases.map((p, idx) => {
              const done = phaseIndex > idx || phase === "done";
              const active = phase === p.id;
              return (
                <div key={p.id} style={{
                  background: "var(--navy-3)", padding: "16px 18px",
                  borderTop: done || active ? "2px solid var(--gold)" : "2px solid transparent",
                  marginTop: done || active ? -1 : 0
                }}>
                  <div style={{ display:"flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <span className="loading-dot" style={{
                      background: done ? "var(--sky)" : active ? "var(--gold)" : "var(--mute)",
                      animation: active ? "blink 1.2s infinite" : "none",
                      opacity: done ? 1 : active ? 1 : 0.25,
                    }}></span>
                    <span style={{ fontSize: 10.5, color: "var(--mute)", letterSpacing: "0.16em", textTransform: "uppercase" }}>Step {idx+1}</span>
                  </div>
                  <div style={{ fontSize: 13, color: done || active ? "var(--white)" : "var(--mute)" }}>{p.label}</div>
                  <div style={{ fontSize: 10.5, color: "var(--mute)", marginTop: 4 }}>{p.detail}</div>
                </div>
              );
            })}
          </div>
          {phase === "error" && (
            <div style={{ marginTop: 18, padding: "14px 16px", borderLeft: "2px solid var(--gold)", background: "var(--navy-3)", fontSize: 13 }}>
              <span style={{ color: "var(--gold)", letterSpacing: "0.16em", textTransform: "uppercase", fontSize: 10, marginRight: 12 }}>Error</span>
              {error}
            </div>
          )}
        </div>
      )}

      {/* Result */}
      {phase !== "fetching" && phase !== "indicators" && phase !== "calling" && phase !== "parsing" && phase !== "error" && bundle && (
        <div className="two-col">
          <div className="stack">
            {/* Headline card */}
            <div className="panel">
              <div className="panel-hd">
                <div>
                  <div className="eyebrow" style={{ marginBottom: 6, color: "var(--sky)" }}>{bundle.sector}</div>
                  <div style={{ display:"flex", alignItems:"baseline", gap: 14 }}>
                    <div className="num" style={{ fontSize: 36 }}>{bundle.symbol}</div>
                    <div style={{ fontSize: 13, color: "var(--mute)" }}>{bundle.name}</div>
                  </div>
                </div>
                <SignalBadge signal={signal.signal} />
              </div>
              <div className="panel-bd" style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 32, alignItems: "center" }}>
                <div>
                  <div className="eyebrow">Last Close</div>
                  <div className="num" style={{ fontSize: 52, marginTop: 6 }}>{fmt$(bundle.current)}</div>
                  <div style={{ display:"flex", gap: 10, marginTop: 8 }}>
                    <span className={(bundle.change >= 0 ? "up" : "down")} style={{ fontSize: 13 }}>
                      {bundle.change >= 0 ? "▲" : "▼"} {fmt$(Math.abs(bundle.change))}
                    </span>
                    <span style={{ color: "var(--mute)", fontSize: 13 }}>{fmtPct(bundle.pct)}</span>
                  </div>
                </div>
                <div>
                  <PriceChart bundle={bundle} />
                </div>
              </div>
            </div>

            {/* Reasoning */}
            <div className="panel subtle">
              <div className="panel-hd">
                <div className="ttl">Reasoning</div>
                <div className="meta">claude-sonnet-4</div>
              </div>
              <div className="panel-bd">
                <div className="reasoning">
                  <span className="lab">AI Analyst</span>
                  {reasoningText}
                  {phase === "done" && reasoningText.length < signal.reasoning.length && <span className="caret"></span>}
                </div>
                <div style={{ marginTop: 18, display:"grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
                  <div>
                    <div className="eyebrow">Signal</div>
                    <div className="num" style={{ fontSize: 22, marginTop: 6, color: signal.signal === "BULLISH" ? "var(--gold)" : signal.signal === "BEARISH" ? "var(--mute)" : "var(--sky)" }}>
                      {signal.signal}
                    </div>
                  </div>
                  <div>
                    <div className="eyebrow">Confidence</div>
                    <div className="num" style={{ fontSize: 22, marginTop: 6 }}>{signal.confidence}</div>
                  </div>
                  <div>
                    <div className="eyebrow">Time</div>
                    <div className="num" style={{ fontSize: 22, marginTop: 6 }}>2.4<span style={{ fontSize: 14, color: "var(--mute)", fontFamily: "var(--sans)" }}>s</span></div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right rail */}
          <div className="stack">
            <div className="panel subtle">
              <div className="panel-hd"><div className="ttl">Indicators</div><div className="meta">30d</div></div>
              <div className="panel-bd">
                <IndRow label="Current" v={fmt$(bundle.current)} />
                <IndRow label="MA · 10" v={fmt$(bundle.ma10v)} bar={(bundle.current - bundle.ma10v) / bundle.ma10v} />
                <IndRow label="MA · 20" v={fmt$(bundle.ma20v)} bar={(bundle.current - bundle.ma20v) / bundle.ma20v} />
                <IndRow label="30d High" v={fmt$(bundle.range.hi)} />
                <IndRow label="30d Low" v={fmt$(bundle.range.lo)} />
                <IndRow label="Volume" v={fmtBigN(bundle.lastVol)} sub={bundle.volAbove ? "Above 10d avg" : "In line"} highlight={bundle.volAbove} />
              </div>
            </div>

            <div className="panel subtle">
              <div className="panel-hd">
                <div className="ttl">Act on signal</div>
                <div className="meta">Paper · Alpaca</div>
              </div>
              <div className="panel-bd">
                {inPortfolio ? (
                  <div>
                    <ul className="em">
                      <li>You hold <strong>{inPortfolio.shares} sh</strong> of {pending} at avg cost {fmt$(inPortfolio.avgCost)}.</li>
                      <li>AI recommendation: <strong style={{ color: "var(--gold)" }}>{inPortfolio.aiRec}</strong>.</li>
                    </ul>
                    <div style={{ display:"flex", gap: 10, marginTop: 16 }}>
                      <button className="btn sm">Review position</button>
                      {signal.signal === "BULLISH" && <button className="btn sm primary" onClick={() => setShowTrade(true)}>Add more</button>}
                      {signal.signal === "BEARISH" && <button className="btn sm danger">Close position</button>}
                    </div>
                  </div>
                ) : (
                  <div>
                    <ul className="em">
                      <li>No position held in {pending}.</li>
                      <li>AI signal: <strong>{signal.signal}</strong> ({signal.confidence}).</li>
                    </ul>
                    <div style={{ display:"flex", gap: 10, marginTop: 16 }}>
                      <button className="btn sm">Log only</button>
                      {signal.signal !== "BEARISH" && (
                        <button className="btn sm primary" onClick={() => setShowTrade(true)}>Open paper buy</button>
                      )}
                    </div>
                  </div>
                )}
                <div style={{ marginTop: 16, fontSize: 11, color: "var(--mute)", letterSpacing: "0.04em", lineHeight: 1.5 }}>
                  All trades routed through Alpaca's paper account. No real capital at risk. Signal is logged regardless of action.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showTrade && <TradeModal bundle={bundle} signal={signal} onClose={() => setShowTrade(false)} onConfirm={(qty) => { onBuy(bundle, signal, qty); setShowTrade(false); }} />}
    </div>
  );
}

function IndRow({label, v, sub, bar, highlight}){
  // bar is a signed proportion (-0.1 .. +0.1 typical) — render as a centered fill
  let barEl = null;
  if(typeof bar === "number"){
    const norm = Math.max(-1, Math.min(1, bar / 0.05)); // ±5% saturates
    const pct = Math.abs(norm) * 50;
    barEl = (
      <div className="ind-bar" style={{ width: "100%" }}>
        <i style={{
          left: norm >= 0 ? "50%" : `${50 - pct}%`,
          width: pct + "%",
          background: norm >= 0 ? "var(--gold)" : "var(--mute)",
        }}></i>
        <span style={{ position: "absolute", left: "50%", top: -2, width: 1, height: 8, background: "var(--rule-strong)" }}></span>
      </div>
    );
  }
  return (
    <div className="ind-row">
      <div className="ind-lab">{label}</div>
      <div>{barEl || <div style={{ fontSize: 11, color: "var(--mute)" }}>{sub || ""}</div>}</div>
      <div className="ind-val" style={{ color: highlight ? "var(--gold)" : "var(--white)" }}>{v}</div>
    </div>
  );
}

function TradeModal({bundle, signal, onClose, onConfirm}){
  const [qty, setQty] = React.useState(10);
  const cost = +(qty * bundle.current).toFixed(2);
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-hd">
          <div>
            <div className="eyebrow"><GoldRule width={16}/> Paper buy order</div>
            <div className="display" style={{ fontSize: 22, marginTop: 6 }}>{bundle.symbol} · {bundle.name}</div>
          </div>
          <button className="close-x" onClick={onClose}><I name="x"/></button>
        </div>
        <div className="modal-bd">
          <ul className="em" style={{ marginBottom: 18 }}>
            <li>Signal <strong>{signal.signal}</strong> · confidence {signal.confidence}</li>
            <li>Market price <strong>{fmt$(bundle.current)}</strong>, last change {fmtPct(bundle.pct)}</li>
            <li>Routed through Alpaca paper API · executes at next print</li>
          </ul>
          <div style={{ display:"grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div className="field">
              <span className="label">Shares</span>
              <input type="number" value={qty} min="1" onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 0))} />
            </div>
            <div className="field">
              <span className="label">Type</span>
              <input value="MARKET" readOnly />
            </div>
          </div>
          <div style={{ marginTop: 18, padding: "14px 16px", background: "var(--navy-3)", borderLeft: "2px solid var(--gold)", display:"flex", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11, letterSpacing: "0.16em", textTransform: "uppercase", color: "var(--mute)" }}>Est. cost</span>
            <span className="num" style={{ fontSize: 22 }}>{fmt$(cost)}</span>
          </div>
        </div>
        <div className="modal-ft">
          <div style={{ fontSize: 11, color: "var(--mute)" }}>Paper capital only · no real funds</div>
          <div style={{ display:"flex", gap: 10 }}>
            <button className="btn sm" onClick={onClose}>Cancel</button>
            <button className="btn sm primary" onClick={() => onConfirm(qty)}>Submit order</button>
          </div>
        </div>
      </div>
    </div>
  );
}

window.SignalScreen = SignalScreen;
