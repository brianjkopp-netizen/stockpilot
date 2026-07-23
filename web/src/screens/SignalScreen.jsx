import { useState } from "react";
import { GoldRule, SignalBadge, ConfidenceMeter, Button } from "../components/atoms.jsx";
import { Loading, ErrorPanel } from "../components/StateBlock.jsx";
import { useAsync } from "../hooks/useAsync.js";
import { getSignal } from "../api/client.js";
import { fmt$ } from "../lib/format.js";

const TRY_TICKERS = ["AAPL", "NVDA", "TSLA", "MSFT", "AMD", "GOOG"];
const DAYS = 30;

export default function SignalScreen() {
  const [ticker, setTicker] = useState("AAPL");
  const [submitted, setSubmitted] = useState("AAPL");

  const { data: result, error, loading, run } = useAsync(
    () => getSignal(submitted, DAYS),
    [submitted],
  );

  function analyze(sym) {
    const SYM = sym.toUpperCase().trim();
    if (!SYM) return;
    setTicker(SYM);
    if (SYM === submitted) {
      run();
    } else {
      setSubmitted(SYM);
    }
  }

  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow">
            <GoldRule width={20} /> AI Signal Analysis
          </div>
          <h2>Ask the analyst.</h2>
          <p>
            Type a ticker. StockPilot pulls {DAYS} days of market data, computes indicators, and
            asks Claude for a structured signal — bullish, bearish, or neutral — with a confidence
            read and plain-language reasoning.
          </p>
        </div>
        <Button icon="refresh" onClick={() => run()} disabled={loading}>
          Re-analyze
        </Button>
      </div>

      {/* Ticker entry */}
      <div className="panel subtle" style={{ marginBottom: 24 }}>
        <div className="ticker-row" style={{ padding: 22 }}>
          <div className="field">
            <span className="label">Ticker</span>
            <input
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && analyze(ticker)}
              placeholder="e.g. AAPL, NVDA, TSLA"
              maxLength="8"
              style={{ textTransform: "uppercase", letterSpacing: "0.12em", fontSize: 15 }}
              disabled={loading}
            />
          </div>
          <div className="field ticker-row-range">
            <span className="label">Range</span>
            <input value={`${DAYS} days`} readOnly />
          </div>
          <Button variant="primary" icon="play" onClick={() => analyze(ticker)} disabled={loading}>
            {loading ? "Analyzing" : "Analyze"}
          </Button>
        </div>
        <div
          style={{
            padding: "0 22px 18px 22px",
            display: "flex",
            gap: 18,
            color: "var(--mute)",
            fontSize: 11.5,
            alignItems: "center",
          }}
        >
          <span style={{ letterSpacing: "0.16em", textTransform: "uppercase", fontSize: 10 }}>Try</span>
          {TRY_TICKERS.map((s) => (
            <button
              key={s}
              onClick={() => analyze(s)}
              disabled={loading}
              style={{ color: "var(--sky)", fontSize: 11.5, letterSpacing: "0.06em", padding: 0 }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {loading && <Loading label={`Analyzing ${submitted} — fetching data, computing indicators, consulting the AI analyst…`} />}

      {!loading && error && (
        <ErrorPanel
          message={error.detail || error.message}
          onRetry={() => run()}
        />
      )}

      {!loading && !error && result && (
        <div className="two-col">
          <div className="stack">
            {/* Headline card */}
            <div className="panel">
              <div className="panel-hd">
                <div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
                    <div className="num" style={{ fontSize: 36 }}>
                      {result.ticker}
                    </div>
                  </div>
                </div>
                <SignalBadge signal={result.signal} />
              </div>
              <div className="panel-bd">
                <div className="eyebrow">Last Close</div>
                <div className="num" style={{ fontSize: 52, marginTop: 6 }}>
                  {fmt$(result.price)}
                </div>
              </div>
            </div>

            {/* Reasoning */}
            <div className="panel subtle">
              <div className="panel-hd">
                <div className="ttl">Reasoning</div>
                <div className="meta">claude-sonnet-4-6</div>
              </div>
              <div className="panel-bd">
                <div className="reasoning">
                  <span className="lab">AI Analyst</span>
                  {result.reasoning}
                </div>
                {result.key_factors?.length > 0 && (
                  <ul className="em" style={{ marginTop: 18 }}>
                    {result.key_factors.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                )}
                <div
                  style={{
                    marginTop: 18,
                    display: "grid",
                    gridTemplateColumns: "repeat(2, 1fr)",
                    gap: 16,
                  }}
                >
                  <div>
                    <div className="eyebrow">Signal</div>
                    <div
                      className="num"
                      style={{
                        fontSize: 22,
                        marginTop: 6,
                        color:
                          result.signal === "BULLISH"
                            ? "var(--gold)"
                            : result.signal === "BEARISH"
                              ? "var(--mute)"
                              : "var(--sky)",
                      }}
                    >
                      {result.signal}
                    </div>
                  </div>
                  <div>
                    <div className="eyebrow">Confidence</div>
                    <div style={{ marginTop: 10 }}>
                      <ConfidenceMeter confidence={result.confidence} />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right rail */}
          <div className="stack">
            <div className="panel subtle">
              <div className="panel-hd">
                <div className="ttl">Indicators</div>
                <div className="meta">{DAYS}d</div>
              </div>
              <div className="panel-bd">
                <IndRow label="Current" v={fmt$(result.price)} />
                <IndRow
                  label="MA · 10"
                  v={fmt$(result.ma_10)}
                  bar={(result.price - result.ma_10) / result.ma_10}
                />
                <IndRow
                  label="MA · 20"
                  v={fmt$(result.ma_20)}
                  bar={(result.price - result.ma_20) / result.ma_20}
                />
                <IndRow
                  label="Volume"
                  v={result.volume_signal}
                  highlight={result.volume_signal === "ABOVE AVERAGE"}
                />
              </div>
            </div>

            <div className="panel subtle">
              <div className="panel-hd">
                <div className="ttl">About this signal</div>
              </div>
              <div className="panel-bd">
                <ul className="em">
                  <li>Signal and confidence are computed deterministically from price vs. moving averages.</li>
                  <li>The AI analyst only writes the plain-English reasoning above.</li>
                  <li>Every call is written to the signal log for audit.</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function IndRow({ label, v, bar, highlight }) {
  let barEl = null;
  if (typeof bar === "number") {
    const norm = Math.max(-1, Math.min(1, bar / 0.05));
    const pct = Math.abs(norm) * 50;
    barEl = (
      <div className="ind-bar" style={{ width: "100%" }}>
        <i
          style={{
            left: norm >= 0 ? "50%" : `${50 - pct}%`,
            width: pct + "%",
            background: norm >= 0 ? "var(--gold)" : "var(--mute)",
          }}
        ></i>
        <span
          style={{
            position: "absolute",
            left: "50%",
            top: -2,
            width: 1,
            height: 8,
            background: "var(--rule-strong)",
          }}
        ></span>
      </div>
    );
  }
  return (
    <div className="ind-row">
      <div className="ind-lab">{label}</div>
      <div>{barEl}</div>
      <div className="ind-val" style={{ color: highlight ? "var(--gold)" : "var(--white)" }}>
        {v}
      </div>
    </div>
  );
}
