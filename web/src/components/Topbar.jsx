import { useEffect, useState } from "react";

const TITLES = {
  "/signal": { ttl: "Signal Analysis", sub: "Run any ticker through the AI analyst." },
  "/portfolio": { ttl: "Paper Portfolio", sub: "Marked-to-market against the morning's close." },
  "/history": { ttl: "Signal Log", sub: "Every signal generated, with audit trail." },
  "/discover": { ttl: "Discover", sub: "Ideas from your watchlist universe." },
};

export default function Topbar({ path }) {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  const titles = TITLES[path] || TITLES["/signal"];
  const isMarketOpen = now.getHours() >= 8 && now.getHours() < 15;

  return (
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
        <div className="ind" style={{ borderLeft: "1px solid var(--rule)", paddingLeft: 22 }}>
          <span style={{ letterSpacing: "0.14em", textTransform: "uppercase", fontSize: 10 }}>Local</span>
          <span className="v mono-num">{now.toLocaleTimeString("en-US", { hour12: false })}</span>
        </div>
      </div>
    </header>
  );
}
