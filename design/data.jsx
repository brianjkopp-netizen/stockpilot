// ----- Mock data for StockPilot prototype -----

// Deterministic pseudo-random so charts feel real but don't jitter on re-render
function seedRand(seed){
  let s = seed % 2147483647;
  return () => (s = s * 16807 % 2147483647) / 2147483647;
}

function genSeries(seed, len, start, drift, vol){
  const r = seedRand(seed);
  const out = [];
  let p = start;
  for(let i=0;i<len;i++){
    const shock = (r() - 0.5) * vol;
    p = p + drift + shock;
    if(p < 1) p = 1;
    out.push(+p.toFixed(2));
  }
  return out;
}
function genVolume(seed, len, base){
  const r = seedRand(seed + 9);
  const out = [];
  for(let i=0;i<len;i++){
    out.push(Math.round(base * (0.6 + r()*0.9)));
  }
  return out;
}
function ma(series, w){
  const out = [];
  for(let i=0;i<series.length;i++){
    if(i < w-1){ out.push(null); continue; }
    let s=0;
    for(let j=0;j<w;j++) s += series[i-j];
    out.push(+(s/w).toFixed(2));
  }
  return out;
}

const TICKERS = {
  AAPL: { name: "Apple Inc.", sector: "Technology", seed: 11, start: 178, drift: 0.18, vol: 3.2, baseVol: 58_000_000 },
  NVDA: { name: "NVIDIA Corp.", sector: "Semiconductors", seed: 27, start: 112, drift: 0.42, vol: 4.0, baseVol: 220_000_000 },
  MSFT: { name: "Microsoft Corp.", sector: "Software", seed: 41, start: 412, drift: 0.22, vol: 5.5, baseVol: 24_000_000 },
  TSLA: { name: "Tesla, Inc.", sector: "Automotive", seed: 73, start: 232, drift: -0.05, vol: 8.5, baseVol: 110_000_000 },
  AMD:  { name: "Adv. Micro Devices", sector: "Semiconductors", seed: 97, start: 154, drift: 0.10, vol: 4.5, baseVol: 65_000_000 },
  GOOG: { name: "Alphabet Inc.", sector: "Technology", seed: 53, start: 168, drift: 0.12, vol: 3.0, baseVol: 28_000_000 },
  TGT:  { name: "Target Corp.", sector: "Consumer Retail", seed: 88, start: 158, drift: -0.02, vol: 2.4, baseVol: 4_500_000 },
  CAT:  { name: "Caterpillar Inc.", sector: "Industrials", seed: 19, start: 348, drift: 0.20, vol: 4.8, baseVol: 2_800_000 },
  ZZZZ: { name: "Unknown / not listed", sector: "—", invalid: true },
};

function buildBundle(sym){
  const t = TICKERS[sym];
  if(!t || t.invalid) return null;
  const days = 30;
  const series = genSeries(t.seed, days, t.start, t.drift, t.vol);
  const vols = genVolume(t.seed, days, t.baseVol);
  const ma10 = ma(series, 10);
  const ma20 = ma(series, 20);
  const last = series[series.length-1];
  const prev = series[series.length-2];
  const m10 = ma10[ma10.length-1];
  const m20 = ma20[ma20.length-1];
  const avgVol10 = vols.slice(-10).reduce((a,b)=>a+b,0)/10;
  const lastVol = vols[vols.length-1];
  const volAbove = lastVol > avgVol10 * 1.05;
  // Generate dates ending 2026-05-22
  const dates = [];
  const end = new Date(2026, 4, 22);
  for(let i=days-1;i>=0;i--){
    const d = new Date(end); d.setDate(end.getDate()-i);
    dates.push(d);
  }
  return {
    symbol: sym, name: t.name, sector: t.sector,
    series, vols, ma10, ma20, dates,
    current: last,
    prevClose: prev,
    change: +(last - prev).toFixed(2),
    pct: +(((last - prev)/prev)*100).toFixed(2),
    ma10v: m10, ma20v: m20,
    avgVol10, lastVol, volAbove,
    range: { lo: Math.min(...series), hi: Math.max(...series) },
  };
}

// Derive a deterministic AI signal from the bundle
function deriveSignal(b){
  if(!b) return null;
  let score = 0;
  if(b.current > b.ma10v) score += 1;
  if(b.current > b.ma20v) score += 1;
  if(b.ma10v > b.ma20v) score += 1;
  if(b.volAbove) score += 1;
  if(b.pct > 0) score += 0.5; else score -= 0.5;

  let signal, confidence, reasoning;
  if(score >= 3) {
    signal = "BULLISH";
    confidence = score >= 3.5 ? "High" : "Moderate";
    reasoning = `Price ($${b.current.toFixed(2)}) is trading above both the 10-day ($${b.ma10v.toFixed(2)}) and 20-day ($${b.ma20v.toFixed(2)}) moving averages, with the shorter MA above the longer — a constructive trend structure. ${b.volAbove ? "Volume is running above the 10-day average, suggesting institutional participation in the move." : "Volume is in line with the 10-day average."} Near-term momentum favors continuation, though watch for resistance near the 30-day high of $${b.range.hi.toFixed(2)}.`;
  } else if(score <= 0) {
    signal = "BEARISH";
    confidence = score <= -0.5 ? "Moderate" : "Low";
    reasoning = `Price ($${b.current.toFixed(2)}) is trading below both moving averages, with the 10-day MA ($${b.ma10v.toFixed(2)}) crossing below the 20-day ($${b.ma20v.toFixed(2)}) — a near-term distribution signal. ${b.volAbove ? "Elevated volume on the down move increases conviction in the weakness." : "Volume is muted, suggesting absence of dip buyers rather than active selling."} Watch the 30-day low of $${b.range.lo.toFixed(2)} as the next risk level.`;
  } else {
    signal = "NEUTRAL";
    confidence = "Moderate";
    reasoning = `Price is straddling the moving averages with no clean trend signal. The 10-day MA ($${b.ma10v.toFixed(2)}) and 20-day ($${b.ma20v.toFixed(2)}) are tightly clustered, indicating a consolidation regime. ${b.volAbove ? "Volume is above average but without directional follow-through." : "Volume is unremarkable."} Wait for a decisive close outside the range ($${b.range.lo.toFixed(2)}–$${b.range.hi.toFixed(2)}) before committing capital.`;
  }
  return { signal, confidence, reasoning };
}

// Mock portfolio — paper account
const INITIAL_PORTFOLIO = {
  cash: 71_240.18,
  startingCash: 100_000.00,
  positions: [
    { sym: "AAPL", shares: 50,  avgCost: 182.40, signal: "BULLISH", aiRec: "HOLD",
      recReason: "Trend intact above both MAs. Continue holding through earnings window.",
      openedOn: "May 04, 2026" },
    { sym: "NVDA", shares: 30, avgCost: 104.20, signal: "BULLISH", aiRec: "ADD",
      recReason: "Strong momentum with rising volume. Position sized for an add on a pullback to the 10-day MA.",
      openedOn: "Apr 27, 2026" },
    { sym: "MSFT", shares: 12, avgCost: 408.55, signal: "BULLISH", aiRec: "HOLD",
      recReason: "Position above cost; technicals constructive. Hold for cloud-segment catalyst.",
      openedOn: "May 11, 2026" },
    { sym: "TGT",  shares: 25, avgCost: 162.10, signal: "BEARISH", aiRec: "SELL",
      recReason: "Position below cost basis and trend has deteriorated. Realize the loss and rotate.",
      openedOn: "Apr 30, 2026" },
  ],
};

// Mock signal history — newest first
const SIGNAL_HISTORY = [
  { ts: "2026-05-22 14:08:12", sym: "NVDA", signal: "BULLISH", confidence: "High",    price: 132.40, acted: "BUY  30 sh @ 104.20", ack: true },
  { ts: "2026-05-22 11:42:01", sym: "AAPL", signal: "BULLISH", confidence: "Moderate",price: 189.42, acted: "HOLD",                ack: true },
  { ts: "2026-05-21 09:33:55", sym: "MSFT", signal: "BULLISH", confidence: "Moderate",price: 414.12, acted: "BUY  12 sh @ 408.55", ack: true },
  { ts: "2026-05-21 09:31:08", sym: "TSLA", signal: "BEARISH", confidence: "High",    price: 218.05, acted: "SKIP — already flat", ack: true },
  { ts: "2026-05-20 15:50:44", sym: "TGT",  signal: "BEARISH", confidence: "Moderate",price: 159.80, acted: "HOLD (review)",       ack: false },
  { ts: "2026-05-20 10:11:30", sym: "AMD",  signal: "NEUTRAL", confidence: "Moderate",price: 156.20, acted: "WATCH",               ack: true },
  { ts: "2026-05-19 14:22:15", sym: "GOOG", signal: "BULLISH", confidence: "Low",     price: 170.95, acted: "WATCH",               ack: true },
  { ts: "2026-05-19 11:04:09", sym: "NVDA", signal: "BULLISH", confidence: "High",    price: 130.10, acted: "HOLD",                ack: true },
  { ts: "2026-05-18 15:48:50", sym: "AAPL", signal: "NEUTRAL", confidence: "Moderate",price: 186.74, acted: "HOLD",                ack: true },
  { ts: "2026-05-18 09:50:21", sym: "CAT",  signal: "BULLISH", confidence: "Moderate",price: 354.40, acted: "WATCH",               ack: true },
  { ts: "2026-05-17 14:55:02", sym: "TGT",  signal: "BEARISH", confidence: "Moderate",price: 161.20, acted: "BUY  25 sh @ 162.10", ack: true },
];

// Discover candidates (AI ideas outside current holdings)
const DISCOVER = [
  { sym: "CAT",  thesis: "Industrial bellwether with broadening earnings revisions. 10/20 MA crossover earlier this week with above-average volume.",
    signal: "BULLISH", confidence: "Moderate", price: 354.40, drift: "+4.2%", recSize: "10 sh / ≈ $3,544" },
  { sym: "AMD",  thesis: "Consolidating after a multi-week base. Volume signature constructive but trend is mid-range — wait for breakout confirmation.",
    signal: "NEUTRAL", confidence: "Moderate", price: 156.20, drift: "+1.1%", recSize: "Watch" },
  { sym: "GOOG", thesis: "Above both MAs with steady drift. Lower-conviction setup given soft volume on up days.",
    signal: "BULLISH", confidence: "Low",      price: 170.95, drift: "+0.8%", recSize: "12 sh / ≈ $2,051" },
];

window.SP_DATA = {
  TICKERS, buildBundle, deriveSignal,
  INITIAL_PORTFOLIO, SIGNAL_HISTORY, DISCOVER,
};
