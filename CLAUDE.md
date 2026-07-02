# CLAUDE.md — StockPilot

This file is the project context for Claude Code. Read it at the start of every session before writing any code.

---

## What This Project Is

**StockPilot** is an AI-assisted paper trading platform built as a father-son summer project (Brian Kopp, PM + UX · Brody Kopp, engineering). It pulls real market data, generates AI trading signals via the Anthropic API, executes paper trades through Alpaca, and displays everything in a Streamlit dashboard.

**Timeline:** May 27 – August 14, 2026 · 12 weeks · 4 milestones  
**Model:** `claude-sonnet-4-6`  
**Repo:** `brianjkopp-netizen/stockpilot` (public, MIT license)

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
│   └── fetcher.py      # yfinance wrapper (STO-02)
├── analysis/           # Signal generation
│   ├── indicators.py   # Technical indicators: MA, volume, summary (STO-03)
│   └── ai_analyst.py   # Anthropic prompt + signal parsing (STO-06, STO-07)
├── trading/            # Order execution
│   └── alpaca_client.py # Paper account client: buy, sell, positions (STO-11–13)
├── portfolio/          # Portfolio intelligence
│   └── tracker.py      # Daily P&L, per-position rec engine (STO-16, STO-17)
├── app/                # Application entry point
│   └── main.py         # CLI in M1/M2 · Streamlit routing from M4 (STO-04, STO-18)
├── design/             # Design reference artifacts — NOT application code
│   ├── README.md       # Explains every file in this folder — read before building any screen
│   ├── StockPilot.html # Clickable UI prototype (North Star brand)
│   ├── StockPilot Data Flow.html  # Element-level data source + issue map
│   ├── app.jsx         # Full screen component tree (reference only)
│   ├── atoms.jsx       # Shared UI primitives reference
│   └── data.jsx        # Mock data shapes — use as field reference for Python schemas
├── signals_log.json    # Append-only signal history (created at runtime, STO-09)
├── portfolio_state.json # Local cache of Alpaca positions (created at runtime, STO-14)
├── watchlist.json      # Tickers to scan in Discover (STO-19) — committed config, not gitignored
├── requirements.txt    # All dependencies
├── .env                # API keys — never commit (see Environment section below)
├── .gitignore          # Excludes .env, __pycache__, *.pyc, and runtime *.json state files (signals_log, portfolio_state, trade_history) — watchlist.json is intentionally tracked
├── CLAUDE.md           # This file
└── README.md           # Public-facing project readme
```

---

## Milestones

| Milestone | Name | Dates | Issues | Gate |
|---|---|---|---|---|
| M1 | Data Foundation | May 27 – Jun 12 | STO-01 – STO-05 | STO-05 |
| M2 | AI Signal Engine | Jun 13 – Jul 3 | STO-06 – STO-10 | STO-10 |
| M3 | Paper Trading | Jul 4 – Jul 24 | STO-11 – STO-15 | STO-15 |
| M4 | Portfolio Dashboard | Jul 25 – Aug 14 | STO-16 – STO-20 | STO-20 |

Each milestone ends with a gate review issue. Do not start the next milestone until the gate is closed.

**Note:** M3 starts July 4. Account for the holiday week — plan accordingly.

---

## Current Milestone Focus

**Check the open issues in GitHub to determine the active sprint.** The current cycle will have 1–2 issues in "In Progress" status. Work those issues to completion before pulling new work.

When you open a GitHub issue, read the full acceptance criteria before writing any code. The criteria are the definition of done.

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

Use `claude-sonnet-4-20250514` for all AI calls. No other model.

Standard call pattern:

```python
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": prompt}
    ]
)

signal_text = response.content[0].text
```

The signal response must be parsed into a structured output. See `analysis/ai_analyst.py` and STO-07 for the expected schema: `signal` (BULLISH / BEARISH / NEUTRAL), `confidence` (High / Moderate / Low), `reasoning` (string), `key_factors` (list).

---

## Design Reference

The `design/` folder contains a clickable prototype and a data flow map. **Open `design/README.md` before building any screen.** The data flow map (`StockPilot Data Flow.html`) traces every UI element to its data source, milestone, and issue number. Use it whenever you're unsure what a component should render or where its data comes from.

The prototype uses the North Star Digital brand system. Streamlit approximates it via `.streamlit/config.toml`. Match the layout and data hierarchy from the prototype; don't spend sprint time on pixel-perfect styling until M4.

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

- Branch from `main` for each issue: `feature/STO-XX-short-description`
- Commit messages: `STO-XX: brief description of what changed`
- Open a PR when the issue acceptance criteria are met
- Linear auto-closes issues when a PR merges with the issue number in the commit or PR title (magic words configured)
- Never commit directly to `main`

---

## What This Project Is Not

- This is not a live trading system. Alpaca paper mode only.
- This is not financial advice. Signal output is for learning purposes.
- This is not a production application. Optimize for learning, not scale.

The goal is a working, well-structured project that demonstrates real engineering skills: clean API integration, structured AI output parsing, state management, and a functional dashboard. Ship something you're both proud of.
