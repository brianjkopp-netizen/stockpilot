const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

const PASSWORD_STORAGE_KEY = "stockpilot_app_password";

/** Event fired on window when a request comes back 401 — the passphrase gate listens for this. */
export const PASSPHRASE_REJECTED_EVENT = "stockpilot:passphrase-rejected";

/** Event fired on window before each retry — useAsync listens for this to show a waking-up state. */
export const RETRYING_EVENT = "stockpilot:retrying";

// Render's free instance spins down when idle; the first request afterward can
// come back 503 while it wakes (see web/README.md). REQUEST_TIMEOUT_MS bounds a
// single attempt instead of relying on the browser's default (which can hang
// far longer than is useful here); the retry loop is what actually rides out
// the wake-up, since a cold instance tends to fail fast rather than hang.
const REQUEST_TIMEOUT_MS = 10000;
const MAX_RETRIES = 4;
const RETRY_BASE_DELAY_MS = 1000;
const RETRYABLE_STATUSES = new Set([502, 503, 504]);

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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isRetryable(err) {
  return err instanceof ApiError && (err.status === 0 || RETRYABLE_STATUSES.has(err.status));
}

/** A single fetch attempt: applies the timeout and turns non-OK responses into
 * ApiError. Does not retry — request() below owns that. */
async function attemptRequest(path, options, headers) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response;
  try {
    try {
      response = await fetch(`${API_BASE}${path}`, { ...options, headers, signal: controller.signal });
    } catch (cause) {
      throw new ApiError(
        `Could not reach the StockPilot API at ${API_BASE}. Is the server running?`,
        0,
        null,
      );
    }
  } finally {
    clearTimeout(timeoutId);
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

/**
 * Network errors and 502/503/504 are treated as transient (a cold Render
 * instance waking up looks exactly like this) and retried with exponential
 * backoff, bounded to MAX_RETRIES attempts. 401, 422, and 429 are terminal by
 * design — a rejected passphrase, a bad ticker, and a rate limit are never
 * retried.
 */
async function request(path, options = {}) {
  const headers = { ...options.headers };
  const password = getPassword();
  if (password) {
    headers["X-App-Password"] = password;
  }

  let attempt = 0;
  for (;;) {
    try {
      return await attemptRequest(path, options, headers);
    } catch (err) {
      if (!isRetryable(err) || attempt >= MAX_RETRIES) {
        throw err;
      }
      attempt += 1;
      window.dispatchEvent(new CustomEvent(RETRYING_EVENT, { detail: { path, attempt } }));
      await sleep(RETRY_BASE_DELAY_MS * 2 ** (attempt - 1));
    }
  }
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
