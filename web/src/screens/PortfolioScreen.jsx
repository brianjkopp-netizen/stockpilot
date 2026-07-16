import { GoldRule } from "../components/atoms.jsx";

export default function PortfolioScreen() {
  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow">
            <GoldRule width={20} /> Paper Portfolio
          </div>
          <h2>Coming next.</h2>
          <p>
            The Portfolio screen — live positions, mark-to-market P&amp;L, and the HOLD / ADD / SELL
            recommendation panel — builds on this UI foundation in a follow-up issue.
          </p>
        </div>
      </div>
      <div className="panel subtle">
        <div className="empty-state">Portfolio screen not yet implemented.</div>
      </div>
    </div>
  );
}
