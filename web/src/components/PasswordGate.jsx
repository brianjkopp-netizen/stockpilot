import { useEffect, useState } from "react";
import { NorthStar, Wordmark } from "./atoms.jsx";
import Icon from "./Icon.jsx";
import { hasPassword, setPassword, setRole, whoAmI, PASSPHRASE_REJECTED_EVENT } from "../api/client.js";

/**
 * Blocks the app behind a shared passphrase. Nothing sensitive lives here or
 * in the bundle — the passphrase is only ever checked server-side, via
 * /auth/whoami, which also reports whether it grants full or viewer
 * (read-only) access so the rest of the app knows which controls to show.
 */
export default function PasswordGate({ children }) {
  const [unlocked, setUnlocked] = useState(() => hasPassword());
  const [input, setInput] = useState("");
  const [rejected, setRejected] = useState(false);
  const [verifying, setVerifying] = useState(false);

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

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || verifying) return;
    setPassword(trimmed);
    setVerifying(true);
    try {
      const { role } = await whoAmI();
      setRole(role);
      setRejected(false);
      setUnlocked(true);
    } catch {
      // A 401 already re-locks via the PASSPHRASE_REJECTED_EVENT listener
      // above; any other failure (e.g. a cold API waking up) just leaves the
      // form in place so the user can retry.
    } finally {
      setVerifying(false);
    }
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
          <button className="btn primary gate-submit" type="submit" disabled={verifying}>
            <Icon name="play" size={13} /> {verifying ? "Verifying…" : "Enter"}
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
