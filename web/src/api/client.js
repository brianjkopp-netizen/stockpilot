const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const PASSWORD_STORAGE_KEY = "stockpilot_app_password";

/** Event fired on window when a request comes back 401 — the passphrase gate listens for this. */
export const PASSPHRASE_REJECTED_EVENT = "stockpilot:passphrase-rejected";

/** Module-level getter — the single place every request reads the stored passphrase from. */
function getPassword() {
  return localStorage.getItem(PASSWORD_STORAGE_KEY) || "";
}

/** Store (or clear, when value is falsy) the shared passphrase. */
export function setPassword(value) {
  if (value) {
    localStorage.setItem(PASSWORD_STORAGE_KEY, value);
  } else {
    localStorage.removeItem(PASSWORD_STORAGE_KEY);
  }
}

export function hasPassword() {
  return getPassword().length > 0;
}

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  const headers = { ...options.headers };
  const password = getPassword();
  if (password) {
    headers["X-App-Password"] = password;
  }

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (cause) {
    throw new ApiError(
      `Could not reach the StockPilot API at ${API_BASE}. Is the server running?`,
      0,
      null,
    );
  }

  if (response.status === 401) {
    setPassword("");
    window.dispatchEvent(new Event(PASSPHRASE_REJECTED_EVENT));
    throw new ApiError("That passphrase was rejected.", 401, null);
  }

  if (!response.ok) {
    let detail = null;
    try {
      detail = (await response.json()).detail;
    } catch {
      // response body wasn't JSON — fall through with detail=null
    }
    throw new ApiError(
      detail || `Request to ${path} failed (${response.status})`,
      response.status,
      detail,
    );
  }

  return response.json();
}

/** GET /signal/{ticker} — indicators + AI signal for a ticker. */
export function getSignal(ticker, days = 30) {
  return request(`/signal/${encodeURIComponent(ticker)}?days=${days}`);
}

/** GET /signals — every logged signal record, most recent first. */
export function getSignals() {
  return request("/signals");
}

/** GET /portfolio — live positions marked to market, totals, and account. */
export function getPortfolio() {
  return request("/portfolio");
}

/** GET /portfolio/{ticker}/recommendation — HOLD / ADD / SELL verdict + AI brief. */
export function getRecommendation(ticker) {
  return request(`/portfolio/${encodeURIComponent(ticker)}/recommendation`);
}

/** GET /discover — scan the watchlist and return an AI signal for every ticker. */
export function getDiscover(days = 30) {
  return request(`/discover?days=${days}`);
}

/** POST /orders — place a paper buy or sell order. */
export function placeOrder(body) {
  return request("/orders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}
