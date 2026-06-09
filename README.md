# StockPilot

StockPilot is an AI-powered stock analysis and paper-trading assistant. It pulls real market data, runs it through technical indicators, asks Claude (via the Anthropic API) for a plain-language BULLISH / BEARISH / NEUTRAL signal with reasoning, and — in later phases — acts on those signals through Alpaca paper trading and surfaces everything in a Streamlit dashboard.

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
7. **Display** everything in a Streamlit dashboard styled with the North Star Digital brand system (`app/`)

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
├── CLAUDE.md
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your real API keys — never commit .env
```

Required environment variables (see `.env.example`):

- `ANTHROPIC_API_KEY` — Claude API key for signal generation
- `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY` / `APCA_API_BASE_URL` — Alpaca paper trading credentials

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
- [ ] AI analyst prompt construction (`build_prompt`)
- [ ] Anthropic API integration (`get_signal`)
- [ ] Signal wired into the CLI output
- [ ] Signal history logging (`signals_log.json`)

### Phase 3 — Paper Trading
- [ ] Alpaca client integration
- [ ] Buy/sell execution based on AI signals
- [ ] Trade history and account state tracking

### Phase 4 — Portfolio Dashboard
- [ ] Streamlit UI (Signal, Portfolio, Signal Log, Discover screens)
- [ ] Daily P&L and position display
- [ ] AI recommendations surfaced in the dashboard

## Design reference

The `design/` folder contains a clickable HTML prototype, a data-flow map, and React component exports from Claude Design that show the intended Streamlit screens and the North Star Digital brand system (colors, typography, component states). See `design/README.md` for details — nothing in that folder runs in production.

## Disclaimer

StockPilot is an educational project. It trades on a **paper** (simulated) account only. Nothing here is financial advice.
