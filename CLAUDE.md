# CLAUDE.md — StockPilot

This file is the project context for Claude Code. Read it at the start of every session before writing any code.

---

## What This Project Is

**StockPilot** is an AI-assisted paper trading platform built as a father-son summer project (Brian Kopp, PM + UX · Brody Kopp, engineering). It pulls real market data, generates AI trading signals via the Anthropic API, executes paper trades through Alpaca, and displays everything in a Streamlit dashboard.

**Timeline:** Summer 2026 · 5 milestones  
**Model:** `claude-sonnet-4-6`  
**Repo:** `brianjkopp-netizen/stockpilot` (public, MIT license)  
**Issue tracker:** Linear, team **StockPilot**, issue keys `SP-##`

The functional version (M1–M4) is a Streamlit app and is complete through the M4 feature work. Milestone 5 rebuilds the same backend behind a thin API with a polished React front end. See the Milestones table for current status.

This is a learning project. Optimize for clarity and correctness over cleverness. Every function should be readable by a developer who is building real engineering skills.

---

## Tech Stack

| Layer | Tool |
|---|---|
| Market data | `yfinance` |
| AI signals | `anthropic` Python SDK |
| Paper trading | `alpaca-py` (paper account only) |
| Dashboard | `streamlit` |
| Language | Python 3.10+ |
| Package management | `pip` + `requirements.txt` |

---

## Repo Structure

```
stockpilot/
├── data/               # Market data fetching
│   └── fetcher.py      # yfinance wrapper: get_stock_data, get_company_name (SP-6)
├── analysis/           # Signal generation
│   ├── indicators.py   # Technical indicators: MA, volume, summary (SP-7)
│   └── ai_analyst.py   # Deterministic calibration + Anthropic reasoning + signal log (SP-10, SP-11, SP-13, SP-21)
├── trading/            # Order execution
│   ├── alpaca_client.py # Paper client: account, buy/sell, positions, execute_signal (SP-22, SP-23, SP-27)
│   └── trade_history.py # Append-only executed-trade log to trade_history.json (SP-25)
├── portfolio/          # Portfolio intelligence
│   ├── tracker.py      # Live mark-to-market, daily P&L, cache fallback (SP-24, SP-29)
│   └── recommender.py  # Per-position HOLD/ADD/SELL verdict + AI brief (SP-30)
├── app/                # Application entry point
│   └── main.py         # Streamlit dashboard (4 screens) with CLI fallback (SP-8, SP-12, SP-28)
├── tests/              # Pytest suite — one test_ module per source module
│   ├── conftest.py     # Shared fixtures / test isolation (SP-39)
│   └── test_*.py       # fetcher, indicators, ai_analyst, alpaca_client, trade_history, tracker, recommender
├── design/             # Design reference artifacts — NOT application code
│   ├── README.md       # Explains every file in this folder — read before building any screen
│   ├── StockPilot.html # Clickable UI prototype (North Signal brand)
│   ├── StockPilot Data Flow.html  # Element-level data source + issue map
│   ├── app.jsx         # Full screen component tree (reference only)
│   ├── atoms.jsx       # Shared UI primitives reference
│   └── data.jsx        # Mock data shapes — use as field reference for Python schemas
├── signals_log.json    # Append-only signal history (created at runtime, SP-13)
├── portfolio_state.json # Local cache of Alpaca positions (created at runtime, SP-24)
├── trade_history.json  # Append-only executed-trade log (created at runtime, SP-25)
├── watchlist.json      # Tickers to scan in Discover (SP-31) — committed config, not gitignored
├── requirements.txt    # All dependencies
├── .env                # API keys — never commit (see Environment section below)
├── .gitignore          # Excludes .env, .venv, __pycache__, *.pyc, and runtime *.json state files (signals_log, portfolio_state, trade_history) — watchlist.json is intentionally tracked
├── CLAUDE.md           # This file
└── README.md           # Public-facing project readme
```

---

## Milestones

| Milestone | Name | Issues | Gate | Status |
|---|---|---|---|---|
| M1 | Data Foundation | SP-5 – SP-9 | SP-9 | Done |
| M2 | AI Signal Engine | SP-10 – SP-14 | SP-14 | Done |
| M3 | Paper Trading | SP-19 – SP-27, SP-39 | SP-26 | Done |
| M4 | Portfolio Dashboard | SP-28 – SP-31 | SP-32 | Features done · gate SP-32 open (Brian to run) |
| M5 | Polished Web App (React) | SP-33 – SP-37 | SP-38 | Not started (Backlog) |

Each milestone ends with a gate review issue owned by Brian. Do not start the next milestone until the gate is closed.

M3 also absorbed hardening issues that surfaced in the M2 gate review (SP-19, SP-20, SP-21) and the M3 gate review (SP-27, SP-39). Expect gate reviews to spawn follow-up bug/chore issues inside the same milestone.

M5 is a distinct architecture: a thin FastAPI/Flask layer (SP-33) over the existing Python backend, with a React front end (SP-34–SP-36) and deployment (SP-37). The backend must stay the single source of truth — no business logic in the front end.

---

## Current Milestone Focus

**Check open issues in Linear (team StockPilot) to determine the active sprint.** As of the last update: M1–M4 feature work is complete, the M4 gate (SP-32) is open and owned by Brian, and all of Milestone 5 (SP-33 – SP-38) is in Backlog and not yet started.

The active cycle will have 1–2 issues "In Progress." Work those to completion before pulling new work. When you open an issue, read the full acceptance criteria before writing any code. The criteria are the definition of done.

---

## Environment Setup

All secrets live in `.env` at the repo root. This file is gitignored and must never be committed.

```
ANTHROPIC_API_KEY=your_key_here
APCA_API_KEY_ID=your_alpaca_paper_key
APCA_API_SECRET_KEY=your_alpaca_paper_secret
```

Load with `python-dotenv`:

```python
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")
```

Alpaca is configured for **paper trading only**. The base URL is `https://paper-api.alpaca.markets`. Never use the live trading URL.

---

## Anthropic API Usage

Use `claude-sonnet-4-6` for all AI calls. No other model.

Standard call pattern:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": prompt}
    ]
)

signal_text = response.content[0].text
```

The signal response is parsed into a structured output. See `analysis/ai_analyst.py` (SP-10, SP-11) for the schema: `signal` (BULLISH / BEARISH / NEUTRAL), `confidence` (High / Moderate / Low), `reasoning` (string), `key_factors` (list).

**Design note (SP-21):** `signal` and `confidence` are computed deterministically in Python by `calibrate_signal()`, not by the model. The Anthropic call only writes the plain-English `reasoning`. The per-position HOLD/ADD/SELL verdict in `portfolio/recommender.py` (SP-30) follows the same pattern: `compute_verdict()` decides, the model only explains. Keep this boundary — the model never decides a trade or a verdict.

---

## Design Reference

The `design/` folder contains a clickable prototype and a data flow map. **Open `design/README.md` before building any screen.** The data flow map (`StockPilot Data Flow.html`) traces every UI element to its data source, milestone, and issue number. Use it whenever you're unsure what a component should render or where its data comes from.

The prototype uses the North Signal Digital brand system. The M4 Streamlit app approximates it via `.streamlit/config.toml` and optimizes for a working dashboard, not presentation quality. Match the layout and data hierarchy from the prototype; full brand fidelity (palette, Fraunces/DM Sans typography, prototype atoms and states) is the job of the M5 React build, not the Streamlit version.

---

## Code Standards

**Python version:** 3.10+

**Style:**
- Functions over classes where possible — keep modules simple and readable
- Type hints on all function signatures
- Docstrings on every public function: what it does, what it takes, what it returns
- Raise meaningful exceptions with clear messages — don't swallow errors silently

**Error handling:**
- `data/fetcher.py` must raise on invalid ticker symbols and network failures
- `analysis/ai_analyst.py` must handle malformed API responses without crashing
- `trading/alpaca_client.py` must log every order attempt and result

**No hardcoded values:**
- API keys always from `.env`
- Ticker symbols always passed as arguments, never hardcoded
- Date ranges always computed from `datetime`, never as string literals

**Testing:** Write a `test_` function for each module as you complete it. A passing smoke test is part of the gate review criteria for each milestone.

---

## Git Workflow

- Branch from `main` for each issue: `feature/SP-XX-short-description`
- Commit messages: `SP-XX: brief description of what changed`
- Open a PR when the issue acceptance criteria are met
- Linear auto-closes issues when a PR merges with the issue number in the commit or PR title (magic words configured)
- **Put the correct SP number in the branch name and commits.** Magic words close whatever issue you name. PR #14 was labeled `SP-38` while doing `trade_history` work and auto-closed the Milestone 5 review gate by mistake. Double-check the number before opening a PR.
- Never commit directly to `main`

---

## What This Project Is Not

- This is not a live trading system. Alpaca paper mode only.
- This is not financial advice. Signal output is for learning purposes.
- This is not a production application. Optimize for learning, not scale.

The goal is a working, well-structured project that demonstrates real engineering skills: clean API integration, structured AI output parsing, state management, and a functional dashboard. Ship something you're both proud of.
