# StockPilot

StockPilot is an AI-powered stock analysis and paper-trading assistant. It pulls real market data, runs it through technical indicators, asks Claude (via the Anthropic API) for a plain-language BULLISH / BEARISH / NEUTRAL signal with reasoning, and — in later phases — acts on those signals through Alpaca paper trading and surfaces everything in a Streamlit dashboard.

## Live deployment (M5)

- **Web app:** [stockpilot.northsignaldigital.com](https://stockpilot.northsignaldigital.com) (Vercel)
- **API:** [stockpilot-api.northsignaldigital.com](https://stockpilot-api.northsignaldigital.com) (Render, `render.yaml`)

The API trades on a paper (simulated) Alpaca account only, and access is gated behind a shared passphrase.

### Data persistence (accepted limitation, SP-60)

`signals_log.json`, `trade_history.json`, and `portfolio_state.json` live on the deployed API instance's local disk. Render's free plan gives that instance no persistent disk, so **all three reset to empty on every deploy** — a deploy of `api/` wipes the signal log and trade history along with it.

This is an accepted constraint of running on Render's free tier, not a bug: adding durable storage (a paid persistent disk, or a hosted database) wasn't judged worth the added cost and complexity for a learning project. The Signal Log screen's copy reflects this — it describes the log as a running record since the last deploy, not a long-term archive. `portfolio_state.json` is a cache that rebuilds from live Alpaca data on every read, so losing it costs nothing. See `CLAUDE.md`'s "Data Persistence" section for the full reasoning and what would need to change if this is ever revisited.

## How it works

```
yfinance  →  technical indicators  →  AI signal (Anthropic)  →  paper trading (Alpaca)  →  Streamlit dashboard
```

1. **Fetch** historical OHLCV data for a ticker (`data/fetcher.py`)
2. **Analyze** the data into a readable summary — moving averages, volume signal (`analysis/indicators.py`)
3. **Signal** — send the summary to Claude and get back a signal, confidence level, and reasoning (`analysis/ai_analyst.py`)
4. **Log** every signal generated to `signals_log.json` for later review
5. **Trade** (paper) — execute buy/sell decisions through Alpaca (`trading/alpaca_client.py`)
6. **Track** portfolio positions and P&L (`portfolio/tracker.py`)
7. **Display** everything in a Streamlit dashboard styled with the North Signal Digital brand system (`app/`)

## Project structure

```
stockpilot/
├── data/
│   └── fetcher.py          # get_stock_data(ticker, days) -> DataFrame
├── analysis/
│   ├── indicators.py       # add_moving_averages, add_volume_signal, get_summary
│   └── ai_analyst.py       # build_prompt, get_signal
├── trading/
│   └── alpaca_client.py    # paper trading execution
├── portfolio/
│   └── tracker.py          # position tracking, P&L
├── app/
│   └── main.py             # CLI entry point (--ticker, --days)
├── design/                 # design reference artifacts (not application code)
├── .env.example
├── .gitignore
├── .python-version              # pyenv pin, 3.11.9 — matches render.yaml's PYTHON_VERSION
├── CLAUDE.md
├── requirements.txt             # API deps only, pinned — what render.yaml installs
├── requirements-lock.txt        # full pip freeze of the API tree, direct + transitive
├── requirements-streamlit.txt   # Streamlit dashboard (app/main.py) — layered on top of requirements.txt
├── requirements-test.txt        # pytest + test-only deps — layered on top of requirements.txt
└── README.md
```

## Setup

Local development uses the same Python version as the deployed Render instance: **3.11.9**, pinned in `.python-version` (pyenv) and in `render.yaml`'s `PYTHON_VERSION`. Install it once with `pyenv install 3.11.9`, then:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-lock.txt
cp .env.example .env   # then fill in your real API keys — never commit .env
```

That installs the API only — the same tree Render installs in production. If you also want to run the Streamlit dashboard or the test suite, layer the matching file on top (see [Dependencies](#dependencies)).

Required environment variables (see `.env.example`):

- `ANTHROPIC_API_KEY` — Claude API key for signal generation
- `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` / `APCA_API_BASE_URL` — Alpaca paper trading credentials

## Dependencies

Four files, all committed. `requirements.txt` covers only what `api/`, `data/`, `analysis/`, `portfolio/`, and `trading/` actually import (plus `uvicorn`, which isn't imported but is required by `render.yaml`'s `startCommand` to serve the app). Streamlit and the test runner are not API dependencies, so they live in their own files layered on top:

| File | What it's for | Install it for |
|---|---|---|
| `requirements.txt` | API direct dependencies, pinned (`==`) | Always — the base every other file builds on |
| `requirements-lock.txt` | Full `pip freeze` of the API tree (direct + transitive) | Deploying or matching Render exactly — this is what `render.yaml`'s `buildCommand` installs |
| `requirements-streamlit.txt` | Streamlit itself | Running `app/main.py` locally: `pip install -r requirements.txt -r requirements-streamlit.txt` |
| `requirements-test.txt` | `pytest`, `httpx` (used directly by the test suite) | Running `pytest`: `pip install -r requirements.txt -r requirements-test.txt` |

Render only ever installs `requirements-lock.txt` — Streamlit, `pyarrow`, and the rest of the Streamlit dependency tree never reach the API instance.

Unpinned or diverging installs are exactly what the pinning setup prevents — see the `peewee`/`pandas` drift that motivated it. Always install from `requirements-lock.txt` for the API tree, never resolve `requirements.txt` fresh, for anything other than regenerating the lock.

**To add or upgrade a dependency:**

```bash
pyenv install 3.11.9        # once, if not already installed
pyenv local 3.11.9          # confirm you're on the pinned version
rm -rf .venv && python -m venv .venv && source .venv/bin/activate
# edit the right file: requirements.txt for an API dep, requirements-streamlit.txt
# or requirements-test.txt for those, pinned with ==
pip install -r requirements.txt
python -m pytest            # confirm the full suite passes against the new resolve (needs -r requirements-test.txt too)
pip freeze > requirements-lock.txt   # regenerate only after installing requirements.txt alone, so the lock stays API-only
```

Commit `requirements.txt` (or whichever of `requirements-streamlit.txt` / `requirements-test.txt` you touched) together with the regenerated `requirements-lock.txt`. Never hand-edit `requirements-lock.txt`.

## Usage

```bash
python app/main.py --ticker AAPL --days 30
```

Prints a formatted summary of the ticker's recent price action, technical indicators, and the AI-generated signal with reasoning.

## Roadmap

StockPilot is being built in four milestones (see `GITHUB_ISSUES.md` and `LINEAR_SETUP.md` for full issue specs):

### Phase 1 — Data Foundation
- [x] Project repo structure and dev environment set up
- [x] Stock data fetcher (`get_stock_data`)
- [x] Technical indicators module (`get_summary`)
- [x] CLI entry point wiring the pipeline end to end

### Phase 2 — AI Signal Engine
- [x] AI analyst prompt construction (`build_prompt`)
- [x] Structured signal parsing (`parse_signal`) — extracts signal, confidence, reasoning, key_factors
- [x] Anthropic API integration (`get_signal`)
- [x] Signal wired into the CLI output
- [x] Signal history logging (`signals_log.json`) — `log_signal` appends, `load_signal_history` retrieves by ticker

### Phase 3 — Paper Trading
- [ ] Alpaca client integration
- [ ] Buy/sell execution based on AI signals
- [ ] Trade history and account state tracking

### Phase 4 — Portfolio Dashboard
- [ ] Streamlit UI (Signal, Portfolio, Signal Log, Discover screens)
- [ ] Daily P&L and position display
- [ ] AI recommendations surfaced in the dashboard

## Design reference

The `design/` folder contains a clickable HTML prototype, a data-flow map, and React component exports from Claude Design that show the intended Streamlit screens and the North Signal Digital brand system (colors, typography, component states). See `design/README.md` for details — nothing in that folder runs in production.

## Disclaimer

StockPilot is an educational project. It trades on a **paper** (simulated) account only. Nothing here is financial advice.
