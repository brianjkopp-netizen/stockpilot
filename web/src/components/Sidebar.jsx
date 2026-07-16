import { NavLink } from "react-router-dom";
import { NorthStar, Wordmark, GoldRule } from "./atoms.jsx";
import Icon from "./Icon.jsx";

const NAV_ITEMS = [
  { section: "Trade", items: [
    { to: "/signal", label: "Signal", icon: "signal" },
    { to: "/portfolio", label: "Portfolio", icon: "portfolio" },
    { to: "/discover", label: "Discover", icon: "discover" },
  ]},
  { section: "Activity", items: [
    { to: "/history", label: "Signal log", icon: "history" },
  ]},
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <NorthStar size={420} opacity={0.04} style={{ position: "absolute", top: -120, left: -120 }} />

      <div className="brand">
        <Wordmark />
        <div className="product">
          StockPilot<span className="dot"></span>
        </div>
        <div className="tagline">AI-assisted paper trading — Minnesota-built, board-room serious.</div>
      </div>

      <nav className="nav">
        {NAV_ITEMS.map((group) => (
          <div key={group.section}>
            <div className="nav-section">{group.section}</div>
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => "nav-item" + (isActive ? " active" : "")}
              >
                <Icon name={item.icon} /> {item.label}
              </NavLink>
            ))}
          </div>
        ))}
        <button className="nav-item" disabled style={{ opacity: 0.5, cursor: "default" }}>
          <Icon name="settings" /> Settings
        </button>
      </nav>

      <div className="footer-area">
        <div className="acct">
          <div className="av">BK</div>
          <div>
            <div className="name">Brian Kopp</div>
            <div className="role">Portfolio Manager</div>
          </div>
        </div>
        <div style={{ fontSize: 10, letterSpacing: "0.18em", textTransform: "uppercase", color: "var(--mute)" }}>
          <GoldRule width={14} /> v1.0 · M5 build
        </div>
      </div>
    </aside>
  );
}
