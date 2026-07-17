const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options) {
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch (cause) {
    throw new ApiError(
      `Could not reach the StockPilot API at ${API_BASE}. Is the server running?`,
      0,
      null,
    );
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
