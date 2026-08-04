# StockPilot

StockPilot is an AI-powered stock analysis and paper-trading assistant. It pulls real market data, runs it through technical indicators, asks Claude (via the Anthropic API) for a plain-language BULLISH / BEARISH / NEUTRAL signal with reasoning, and — in later phases — acts on those signals through Alpaca paper trading and surfaces everything in a Streamlit dashboard.

## Live deployment (M5)

- **Web app:** [stockpilot.northsignaldigital.com](https://stockpilot.northsignaldigital.com) (Vercel)
- **API:** [stockpilot-api.northsignaldigital.com](https://stockpilot-api.northsignaldigital.com) (Render, `render.yaml`)

The API trades on a paper (simulated) Alpaca account only, and access is gated behind a shared passphrase.

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
├── .python-version         # pyenv pin, 3.11.9 — matches render.yaml's PYTHON_VERSION
├── CLAUDE.md
├── requirements.txt        # direct dependencies, pinned
├── requirements-lock.txt   # full pip freeze — what render.yaml actually installs
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

`requirements-lock.txt` is what actually gets installed — same file Render installs in production, so your local environment matches deploy exactly. See [Dependencies](#dependencies) below before adding or upgrading a package.

Required environment variables (see `.env.example`):

- `ANTHROPIC_API_KEY` — Claude API key for signal generation
- `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` / `APCA_API_BASE_URL` — Alpaca paper trading credentials

## Dependencies

Two files, both committed:

- **`requirements.txt`** — the direct dependencies this project actually imports, each pinned to an exact version (`==`). This is the human-edited list.
- **`requirements-lock.txt`** — the full `pip freeze` output: every direct *and* transitive dependency, exact versions. This is what `render.yaml`'s `buildCommand` installs, so a deploy always gets the identical dependency tree that was tested locally.

Unpinned or diverging installs are exactly what this setup prevents — see the `peewee`/`pandas` drift that motivated it. Always install from `requirements-lock.txt`, never resolve `requirements.txt` fresh, for anything other than regenerating the lock.

**To add or upgrade a dependency:**

```bash
pyenv install 3.11.9        # once, if not already installed
pyenv local 3.11.9          # confirm you're on the pinned version
rm -rf .venv && python -m venv .venv && source .venv/bin/activate
# edit requirements.txt: add the new package, or bump the version, pinned with ==
pip install -r requirements.txt
python -m pytest            # confirm the full suite passes against the new resolve
pip freeze > requirements-lock.txt
```

Commit both `requirements.txt` and the regenerated `requirements-lock.txt` together. Never hand-edit `requirements-lock.txt`.

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
