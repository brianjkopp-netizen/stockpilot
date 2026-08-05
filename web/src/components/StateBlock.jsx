/** Consistent loading / error / empty states, shared across every screen. */

// Render's free instance spins down when idle — see web/README.md.
const WAKING_LABEL = "Waking the server, this can take up to a minute…";

export function Loading({ label = "Loading", retrying = false }) {
  return (
    <div className="panel subtle" style={{ padding: 22, display: "flex", alignItems: "center", gap: 10 }}>
      <span className="loading-dot"></span>
      <span className="loading-dot d2"></span>
      <span className="loading-dot d3"></span>
      <span style={{ fontSize: 13, color: "var(--mute)", marginLeft: 6 }}>
        {retrying ? WAKING_LABEL : label}
      </span>
    </div>
  );
}

export function ErrorPanel({ message, onRetry }) {
  return (
    <div className="panel subtle" style={{ padding: 22 }}>
      <div className="error-panel" style={{ marginTop: 0, display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
        <div>
          <span className="tag">Error</span>
          {message}
        </div>
        {onRetry && (
          <button className="btn sm" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ children }) {
  return <div className="empty-state">{children}</div>;
}
