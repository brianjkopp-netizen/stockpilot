import { GoldRule } from "../components/atoms.jsx";

export default function DiscoverScreen() {
  return (
    <div>
      <div className="heading-block">
        <div className="lead">
          <div className="eyebrow">
            <GoldRule width={20} /> Discover
          </div>
          <h2>Coming next.</h2>
          <p>
            The Discover screen — AI signals scanned across your watchlist — builds on this UI
            foundation in a follow-up issue.
          </p>
        </div>
      </div>
      <div className="panel subtle">
        <div className="empty-state">Discover screen not yet implemented.</div>
      </div>
    </div>
  );
}
