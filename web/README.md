# StockPilot — Web (M5)

React/Vite front end for the StockPilot API (`api/main.py`, SP-33). Brand system: North Signal Digital (Fraunces + DM Sans).

## Setup

```
cd web
npm install
npm run dev
```

Runs at `http://localhost:5173`. The API client defaults to `http://localhost:8000` — override with a `.env.local` file (see `.env.example`) if the API runs elsewhere.

## Running the API alongside it

From the repo root, in a separate terminal, with the API dependencies installed (`pip install -r requirements.txt` — this is the only requirements file the API needs; `requirements-streamlit.txt` and `requirements-test.txt` are for the Streamlit dashboard and the test suite, not the API, see the root `README.md`'s Dependencies section):

```
uvicorn api.main:app --reload --port 8000
```

## What's implemented (SP-34)

- Vite scaffold, routing across all four screens (Signal, Portfolio, Signal Log, Discover) with sidebar + topbar chrome
- Shared primitives (`src/components/atoms.jsx`): signal badges, confidence meter, metric cards, action buttons, brand marks
- Signal screen and Signal Log screen wired to the live API, with consistent loading/error states (`src/hooks/useAsync.js`, `src/components/StateBlock.jsx`)
- Portfolio and Discover screens are wired to the live API, including AI recommendations and a confirm-before-submit flow for placing paper orders (`src/components/ConfirmOrder.jsx`)

## Password gate (SP-46)

The API sits behind a shared passphrase (`api/main.py`'s `require_password` dependency), gated by the `APP_PASSWORD` environment variable — see `render.yaml`. The frontend (`src/components/PasswordGate.jsx`) shows a passphrase form until one is entered, calls `GET /auth/whoami` to verify it and learn the access role it grants, stores both in `localStorage`, and sends the passphrase as `X-App-Password` on every request (`src/api/client.js`). A 401 clears the stored passphrase and role and re-shows the gate with a rejection message.

`APP_PASSWORD` is unset locally, so the gate is off server-side — any non-empty passphrase you type into the local gate form is accepted (the API isn't checking it), so it's just a one-time "type anything to continue" step in local dev, not a real login.

A second, optional passphrase — `APP_PASSWORD_VIEWER` — grants read-only "viewer" access: `/auth/whoami` reports it as `role: "viewer"`, and `src/api/client.js`'s `isViewer()` helper (backed by the stored role) drives the UI to hide the buy/sell controls on the Portfolio and Discover screens in favor of a "View only" label. This is UI-level convenience only — the real enforcement is server-side: mutating routes (`POST /orders`, `POST /watchlist`, `DELETE /watchlist/{ticker}`) depend on `require_write_access`, which rejects the viewer role with a 403 regardless of what the client sends. Hand the viewer passphrase out to anyone you want to show the dashboard to without giving them the ability to place paper trades.

## Cold starts on the deployed API (SP-58)

The Render free plan spins the API instance down after a period of inactivity, and Render's own docs warn the first request afterward can take 50 seconds or more to come back. In practice the instance tends to answer fast with a 502/503/504 rather than hang, so `src/api/client.js`'s `request()` treats those statuses (plus a bare network error) as transient: it retries automatically with exponential backoff, bounded to a small number of attempts, and applies its own timeout via `AbortController` instead of relying on the browser default. `401`, `422`, and `429` are never retried — a rejected passphrase, a bad ticker, and a rate limit are all terminal by design.

While a retry is in flight, `useAsync`'s `retrying` flag goes true (driven by the `RETRYING_EVENT` window event `client.js` dispatches before each retry), and every screen swaps its normal loading label for "Waking the server, this can take up to a minute…" (see `src/components/StateBlock.jsx`'s `Loading`) instead of showing an error. If you hit the deployed app cold, that's expected — give it a few seconds rather than assuming it's broken.

## Orders never retry (SP-65)

The retry behavior above is only safe for reads: a GET can be repeated freely because it can't change anything. `request()` retries by default for exactly that reason, but `placeOrder()` (`POST /orders`) explicitly passes `retry: false` to opt out — placing an order isn't idempotent, and a timeout or gateway error doesn't tell the client whether Alpaca already received the request. Retrying blindly could double a fill instead of just re-fetching data. `POST /watchlist` and `DELETE /watchlist/{ticker}` are idempotent server-side, so an accidental retry there would be cosmetic rather than state-changing, but neither is currently called from `client.js`; if that changes, follow `placeOrder`'s example rather than assuming the default is safe for a write.

Because a single attempt has to cover the whole cold-start path on its own, `placeOrder` uses a longer timeout (`ORDER_TIMEOUT_MS`, 45s) than reads (`REQUEST_TIMEOUT_MS`, 10s) — `route_place_order` in `api/main.py` does a `yfinance` quote fetch and an Alpaca round trip before responding, and on a cold instance that alone can exceed the read timeout.

When an order attempt fails with what would otherwise be a retryable error (a timeout, a network failure, or a 502/503/504), `client.js` marks the thrown `ApiError` with `unconfirmed: true` — the outcome is genuinely unknown, not a confirmed failure. `PortfolioScreen` and `DiscoverScreen` check that flag and show `UNCONFIRMED_ORDER_MESSAGE` ("We could not confirm this order — check your portfolio before retrying.") instead of a plain error, and never render a "Placed" success state for an unconfirmed result. A terminal rejection (422 from bad input, 403 from the viewer role) is not marked unconfirmed — the server evaluated the request before touching Alpaca and gave a definitive answer.

### Retrying an unconfirmed order safely (idempotency key)

An unconfirmed result isn't the end of the road — both screens show a **Retry** button next to it. What makes that safe (instead of reintroducing the exact double-order risk this issue started from) is a client-generated idempotency key:

- `requestAdd`/`requestClose` (Portfolio) and `requestBuy` (Discover) call `client.js`'s `newIdempotencyKey()` **once**, when the confirmation modal opens, and store it on the pending order. The initial submit and every later Retry of that same order reuse that one key — a screen must not call `newIdempotencyKey()` again for a retry, since a fresh key would protect nothing.
- The key rides along as `idempotency_key` in the `POST /orders` body. `api/main.py`'s `OrderRequest.idempotency_key` forwards it to `place_buy_order`/`place_sell_order` as `client_order_id` — Alpaca's own order field.
- `trading/alpaca_client.py`'s `_place_order()` checks for an existing order under that `client_order_id` (via Alpaca's `get_order_by_client_id`) before submitting, and again if the submit itself errors (which is what a duplicate `client_order_id` looks like from the client's side). Either way, if the order already exists, it's returned as-is instead of being placed a second time. This leans on Alpaca as the source of truth rather than a cache StockPilot would have to maintain — consistent with [SP-60](../CLAUDE.md)'s decision not to add persistence for this project.
- A brand new order (clicking Add/Buy again, not Retry) always gets a brand new key, so it's never mistaken for a retry of a previous one.

## Testing (SP-44)

Vitest + React Testing Library. Component and screen tests mock the `src/api/client.js` boundary rather than global `fetch`, so they exercise component behavior, not the transport. `client.js` itself is the exception — its own tests mock `fetch` directly, since that's the boundary under test.

```
cd web
npm install
npm test
```

Coverage:

- `src/api/client.js` — response parsing, non-OK detail surfacing, network failure -> `ApiError` with `status: 0`, explicit `AbortController` timeout, retry-with-backoff on network errors and 502/503/504 (including giving up after the bounded attempt count), no retry on 401/422/429, and `RETRYING_EVENT` dispatch. These tests use fake timers (`vi.useFakeTimers()`) so the backoff delays run instantly instead of for real
  - `placeOrder` specifically: a timed-out or gateway-error order is not retried (single `fetch` call, `RETRYING_EVENT` never fires) and the thrown error carries `unconfirmed: true`; a terminal 422 does not get that flag; and the order timeout outlasts the read timeout so a slow-but-successful cold-start order still resolves
- `src/hooks/useAsync.js` — loading/data/error states, manual `run()` re-execution, and the `retrying` flag toggling on `RETRYING_EVENT`
- `src/lib/format.js` — null and zero inputs for every formatter
- One render smoke test per screen (Signal, Portfolio, Signal Log, Discover) for each of its three states: loading, error, loaded
- Empty states for Portfolio (no positions) and Discover (no scan results)
- Order placement: `placeOrder` is not called on the initial action click, only after the confirmation modal is confirmed
- Order placement: an unconfirmed `placeOrder` failure (timeout/gateway error) shows the unresolved-outcome message on Portfolio and Discover, never a silent success
- Order placement: clicking Retry after an unconfirmed order resubmits with the exact same `idempotency_key` from the original attempt, on both screens
- `newIdempotencyKey()` returns a fresh value every call — the screens, not the helper, are what makes reuse happen
