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

From the repo root, in a separate terminal:

```
uvicorn api.main:app --reload --port 8000
```

## What's implemented (SP-34)

- Vite scaffold, routing across all four screens (Signal, Portfolio, Signal Log, Discover) with sidebar + topbar chrome
- Shared primitives (`src/components/atoms.jsx`): signal badges, confidence meter, metric cards, action buttons, brand marks
- Signal screen and Signal Log screen wired to the live API, with consistent loading/error states (`src/hooks/useAsync.js`, `src/components/StateBlock.jsx`)
- Portfolio and Discover screens are wired to the live API, including AI recommendations and a confirm-before-submit flow for placing paper orders (`src/components/ConfirmOrder.jsx`)

## Password gate (SP-46)

The API sits behind a single shared passphrase (`api/main.py`'s `require_password` dependency), gated by the `APP_PASSWORD` environment variable — see `render.yaml`. The frontend (`src/components/PasswordGate.jsx`) shows a passphrase form until one is entered, stores it in `localStorage`, and sends it as `X-App-Password` on every request (`src/api/client.js`). A 401 clears the stored passphrase and re-shows the gate with a rejection message.

`APP_PASSWORD` is unset locally, so the gate is off server-side — any non-empty passphrase you type into the local gate form is accepted (the API isn't checking it), so it's just a one-time "type anything to continue" step in local dev, not a real login.

## Testing (SP-44)

Vitest + React Testing Library. Component and screen tests mock the `src/api/client.js` boundary rather than global `fetch`, so they exercise component behavior, not the transport. `client.js` itself is the exception — its own tests mock `fetch` directly, since that's the boundary under test.

```
cd web
npm install
npm test
```

Coverage:

- `src/api/client.js` — response parsing, non-OK detail surfacing, network failure -> `ApiError` with `status: 0`
- `src/hooks/useAsync.js` — loading/data/error states and manual `run()` re-execution
- `src/lib/format.js` — null and zero inputs for every formatter
- One render smoke test per screen (Signal, Portfolio, Signal Log, Discover) for each of its three states: loading, error, loaded
- Empty states for Portfolio (no positions) and Discover (no scan results)
- Order placement: `placeOrder` is not called on the initial action click, only after the confirmation modal is confirmed
