import Icon from "./Icon.jsx";

export function NorthStar({ size = 520, opacity = 0.05, style = {} }) {
  const cx = 100;
  const cy = 100;
  const longR = 96;
  const shortR = 44;
  const pts = [];
  for (let i = 0; i < 16; i++) {
    const a = ((Math.PI * 2) / 16) * i - Math.PI / 2;
    const r = i % 2 === 0 ? longR : shortR;
    pts.push(`${(cx + Math.cos(a) * r).toFixed(2)},${(cy + Math.sin(a) * r).toFixed(2)}`);
  }
  return (
    <svg
      viewBox="0 0 200 200"
      className="north-star"
      style={{ width: size, height: size, opacity, ...style }}
      aria-hidden="true"
    >
      <polygon points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth="1" />
      <polygon points={pts.join(" ")} fill="currentColor" opacity="0.15" />
    </svg>
  );
}

export function GoldRule({ width = 28 }) {
  return <span className="gold-rule" style={{ width }}></span>;
}

export function Wordmark({ children = "NORTH SIGNAL DIGITAL" }) {
  return (
    <div>
      <GoldRule width={28} />
      <span className="wordmark">{children}</span>
    </div>
  );
}

/** Signal chip — BULLISH / BEARISH / NEUTRAL, colored per brand rules. */
export function SignalBadge({ signal }) {
  const cls = signal === "BULLISH" ? "bullish" : signal === "BEARISH" ? "bearish" : "neutral";
  return (
    <span className={"sig " + cls}>
      <span className="pip"></span>
      {signal}
    </span>
  );
}

const CONFIDENCE_LEVELS = { Low: 1, Moderate: 2, High: 3 };

/** Confidence meter — three bars, filled left-to-right by Low/Moderate/High. */
export function ConfidenceMeter({ confidence }) {
  const filled = CONFIDENCE_LEVELS[confidence] || 0;
  return (
    <span className="conf-meter">
      <span className="bars">
        {[1, 2, 3].map((i) => (
          <i key={i} className={i <= filled ? "on" : ""}></i>
        ))}
      </span>
      <span className="lab">{confidence || "—"}</span>
    </span>
  );
}

/** Sparkline — minimal trend polyline over a series of values (brand .spark styling). */
export function Sparkline({ values, color, width = 80, height = 24 }) {
  if (!values || values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = width / (values.length - 1 || 1);
  const points = values
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg className="spark" viewBox={`0 0 ${width} ${height}`}>
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.25" />
    </svg>
  );
}

/** Metric card — label + big number + optional delta/sub line (brand .kpi styling). */
export function MetricCard({ label, value, sub, tone }) {
  const color = tone === "gain" ? "var(--gold)" : tone === "loss" ? "var(--mute)" : undefined;
  return (
    <div className="kpi">
      <div className="lab">{label}</div>
      <div className="val" style={{ color }}>
        {value}
      </div>
      {sub != null && <div className="delta">{sub}</div>}
    </div>
  );
}

const BUTTON_VARIANTS = {
  buy: "primary",
  neutral: "ghost",
  hold: "ghost",
  sell: "danger",
  primary: "primary",
  ghost: "ghost",
  danger: "danger",
};

/** Action button — BUY / SELL / HOLD / NEUTRAL semantic variants over the shared .btn styles. */
export function Button({ variant = "neutral", size, icon, children, ...props }) {
  const cls = ["btn", BUTTON_VARIANTS[variant] || "", size === "sm" ? "sm" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={cls} {...props}>
      {icon && <Icon name={icon} size={size === "sm" ? 12 : 13} />}
      {children}
    </button>
  );
}
