import { useEffect, useState } from "react";
import { NorthStar, Wordmark } from "./atoms.jsx";
import Icon from "./Icon.jsx";
import { hasPassword, setPassword, PASSPHRASE_REJECTED_EVENT } from "../api/client.js";

/**
 * Blocks the app behind a single shared passphrase. Nothing sensitive lives
 * here or in the bundle — the passphrase is only ever checked server-side;
 * this component just decides whether to render its children.
 */
export default function PasswordGate({ children }) {
  const [unlocked, setUnlocked] = useState(() => hasPassword());
  const [input, setInput] = useState("");
  const [rejected, setRejected] = useState(false);

  useEffect(() => {
    function onRejected() {
      setUnlocked(false);
      setRejected(true);
    }
    window.addEventListener(PASSPHRASE_REJECTED_EVENT, onRejected);
    return () => window.removeEventListener(PASSPHRASE_REJECTED_EVENT, onRejected);
  }, []);

  if (unlocked) {
    return children;
  }

  function handleSubmit(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setPassword(trimmed);
    setRejected(false);
    setUnlocked(true);
  }

  return (
    <div className="gate">
      <NorthStar size={520} opacity={0.05} style={{ position: "absolute", top: -140, right: -140 }} />
      <div className="gate-panel panel subtle">
        <Wordmark />
        <div className="gate-title display">
          StockPilot<span className="dot"></span>
        </div>
        <p className="gate-sub">
          AI-assisted paper trading — Minnesota-built, board-room serious. Enter the shared
          passphrase to continue.
        </p>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <span className="label">Passphrase</span>
            <input
              type="password"
              autoFocus
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                if (rejected) setRejected(false);
              }}
              placeholder="Enter passphrase"
            />
          </div>
          <button className="btn primary gate-submit" type="submit">
            <Icon name="play" size={13} /> Enter
          </button>
        </form>
        {rejected && (
          <div className="error-panel gate-error">
            <span className="tag">Error</span> That passphrase was rejected. Try again.
          </div>
        )}
      </div>
    </div>
  );
}
