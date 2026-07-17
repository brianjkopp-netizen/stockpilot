// ----- Reusable atoms -----

function NorthStar({size=520, opacity=0.05, className=""}) {
  // 8-pointed star outline (long + short pts) — flat stroke, no gradient/shadow
  const cx = 100, cy = 100;
  const longR = 96, shortR = 44;
  const pts = [];
  for(let i=0;i<16;i++){
    const a = (Math.PI*2 / 16) * i - Math.PI/2;
    const r = (i % 2 === 0) ? longR : shortR;
    pts.push(`${(cx + Math.cos(a)*r).toFixed(2)},${(cy + Math.sin(a)*r).toFixed(2)}`);
  }
  return (
    <svg
      viewBox="0 0 200 200"
      className={"north-star " + className}
      style={{ width: size, height: size, opacity }}
      aria-hidden="true"
    >
      <polygon points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth="1" />
      <polygon points={pts.join(" ")} fill="currentColor" opacity="0.15" />
    </svg>
  );
}

function GoldRule({width=28}){
  return <span className="gold-rule" style={{ width }}></span>;
}

function Wordmark({children="NORTH SIGNAL DIGITAL"}){
  return (
    <div>
      <GoldRule width={28} />
      <span className="wordmark">{children}</span>
    </div>
  );
}

function Sparkline({values, color, width=80, height=24}){
  if(!values || values.length === 0) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const span = (max - min) || 1;
  const stepX = width / (values.length - 1);
  const pts = values.map((v,i) => {
    const x = i*stepX;
    const y = height - ((v - min)/span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}

// Price + MA + volume chart, brand-flat
function PriceChart({bundle}){
  if(!bundle) return null;
  const W = 720, H = 220;
  const padL = 44, padR = 56, padT = 12, padB = 36;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const ys = bundle.series;
  const ma10 = bundle.ma10;
  const ma20 = bundle.ma20;
  const vols = bundle.vols;
  const n = ys.length;

  const allP = [...ys, ...ma10.filter(v=>v!=null), ...ma20.filter(v=>v!=null)];
  const yMin = Math.min(...allP);
  const yMax = Math.max(...allP);
  const yPad = (yMax - yMin) * 0.12;
  const lo = yMin - yPad, hi = yMax + yPad;

  const xAt = (i) => padL + (i/(n-1)) * innerW;
  const yAt = (v) => padT + (1 - (v - lo)/(hi - lo)) * innerH * 0.78; // top 78% is price
  const vMax = Math.max(...vols);
  const vTop = padT + innerH * 0.82;
  const vH = innerH - innerH * 0.82;
  const vY = (v) => vTop + (1 - v/vMax) * vH;

  const path = (arr) => arr.map((v,i) => v==null ? null : `${i===0||arr[i-1]==null ? "M" : "L"}${xAt(i).toFixed(1)} ${yAt(v).toFixed(1)}`).filter(Boolean).join(" ");

  const tickVals = [lo, (lo+hi)/2, hi];
  return (
    <svg className="chart" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">
      {/* Grid */}
      {tickVals.map((v, i) => (
        <g key={i}>
          <line className="grid" x1={padL} x2={W-padR} y1={yAt(v)} y2={yAt(v)} />
          <text className="axisLbl" x={W-padR+8} y={yAt(v)+3}>${v.toFixed(0)}</text>
        </g>
      ))}
      {/* Volume bars */}
      {vols.map((v, i) => {
        const x = xAt(i) - innerW/(n*2.4);
        const w = innerW/(n*1.2);
        const y = vY(v);
        const hi = bundle.vols[bundle.vols.length-1] === v && bundle.volAbove;
        return <rect key={i} x={x} y={y} width={w} height={Math.max(1, vTop + vH - y)} className={"vol" + (hi ? " hi" : "")} />;
      })}
      {/* MA20, MA10, then price */}
      <path className="ma20" d={path(ma20)} />
      <path className="ma10" d={path(ma10)} />
      <path className="price" d={path(ys)} />

      {/* X axis labels: first / mid / last date */}
      {[0, Math.floor((n-1)/2), n-1].map((i) => {
        const d = bundle.dates[i];
        const lbl = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
        return <text key={i} className="axisLbl" x={xAt(i)} y={H-12} textAnchor={i===0?"start":i===n-1?"end":"middle"}>{lbl}</text>;
      })}

      {/* Legend */}
      <g transform={`translate(${padL}, ${padT-2})`}>
        <g>
          <line x1="0" y1="0" x2="14" y2="0" stroke="var(--sky)" strokeWidth="1.5"/>
          <text className="label" x="20" y="3">Close</text>
        </g>
        <g transform="translate(70, 0)">
          <line x1="0" y1="0" x2="14" y2="0" stroke="var(--gold)" strokeWidth="1" strokeDasharray="4 3"/>
          <text className="label" x="20" y="3">MA 10</text>
        </g>
        <g transform="translate(140, 0)">
          <line x1="0" y1="0" x2="14" y2="0" stroke="var(--mute)" strokeWidth="1" strokeDasharray="2 3"/>
          <text className="label" x="20" y="3">MA 20</text>
        </g>
        <g transform="translate(210, 0)">
          <rect x="0" y="-4" width="10" height="8" fill="var(--royal-2)"/>
          <text className="label" x="16" y="3">Volume</text>
        </g>
      </g>
    </svg>
  );
}

// Tiny inline icons (stroked, brand-flat)
function I({name, size=16}){
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.5", strokeLinecap: "round", strokeLinejoin: "round" };
  switch(name){
    case "signal":
      return (<svg {...common}><path d="M3 17 L9 11 L13 14 L21 6" /><path d="M15 6 L21 6 L21 12" /></svg>);
    case "portfolio":
      return (<svg {...common}><rect x="3" y="6" width="18" height="14" /><path d="M3 10 L21 10" /><path d="M9 6 V4 H15 V6" /></svg>);
    case "history":
      return (<svg {...common}><circle cx="12" cy="12" r="9" /><path d="M12 7 V12 L15 14" /></svg>);
    case "discover":
      return (<svg {...common}><circle cx="11" cy="11" r="7" /><path d="M21 21 L16 16" /></svg>);
    case "settings":
      return (<svg {...common}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1A2 2 0 1 1 4.3 16.9l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1A2 2 0 1 1 7 4.3l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1A2 2 0 1 1 19.7 7l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>);
    case "x":
      return (<svg {...common}><path d="M18 6 L6 18 M6 6 L18 18"/></svg>);
    case "arrow-up":
      return (<svg {...common}><path d="M12 19 V5 M5 12 L12 5 L19 12"/></svg>);
    case "arrow-down":
      return (<svg {...common}><path d="M12 5 V19 M5 12 L12 19 L19 12"/></svg>);
    case "external":
      return (<svg {...common}><path d="M14 4 H20 V10 M20 4 L11 13 M19 14 V20 H4 V5 H10"/></svg>);
    case "play":
      return (<svg {...common}><path d="M6 4 L20 12 L6 20 Z"/></svg>);
    case "refresh":
      return (<svg {...common}><path d="M21 12 a9 9 0 1 1 -3-6.7"/><path d="M21 4 V10 H15"/></svg>);
    default: return null;
  }
}

function SignalBadge({signal}){
  const cls = signal === "BULLISH" ? "bullish" : signal === "BEARISH" ? "bearish" : "neutral";
  return (
    <span className={"sig " + cls}>
      <span className="pip"></span>
      {signal}
    </span>
  );
}

function fmt$(n){
  if(n == null) return "—";
  return "$" + n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function fmtN(n){
  if(n == null) return "—";
  return n.toLocaleString("en-US");
}
function fmtPct(p){
  if(p == null) return "—";
  const s = p >= 0 ? "+" : "";
  return s + p.toFixed(2) + "%";
}
function fmtBigN(n){
  if(n >= 1e9) return (n/1e9).toFixed(2) + "B";
  if(n >= 1e6) return (n/1e6).toFixed(2) + "M";
  if(n >= 1e3) return (n/1e3).toFixed(1) + "K";
  return String(n);
}

Object.assign(window, {
  NorthStar, GoldRule, Wordmark, Sparkline, PriceChart, I, SignalBadge,
  fmt$, fmtN, fmtPct, fmtBigN,
});
