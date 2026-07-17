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
- Portfolio and Discover screens are placeholders — they build on this foundation in a follow-up issue
