# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

StockPilot is in its scaffolding phase: the module directories below exist but are empty, and `requirements.txt`/`README.md` are placeholders. There is no build, lint, or test tooling yet — that infrastructure gets created as Milestone 1 issues are completed (see `GITHUB_ISSUES.md`). When setting up the environment, use:

```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # populate with yfinance, python-dotenv, anthropic, streamlit, alpaca-py as milestones land
```

API keys (`ANTHROPIC_API_KEY`, Alpaca keys, etc.) load from a local `.env` via `python-dotenv` — never hardcode them or commit `.env`.

## Planned architecture

The project is a CLI-first stock analysis pipeline that will grow into a Streamlit dashboard. The intended module layout (defined in `GITHUB_ISSUES.md`, Issue M1-01) is:

```
data/fetcher.py          → get_stock_data(ticker, days) -> pd.DataFrame   (yfinance OHLCV)
analysis/indicators.py   → add_moving_averages, add_volume_signal, get_summary  (pandas-based technicals)
analysis/ai_analyst.py   → build_prompt, get_signal                       (Anthropic API signal generation)
trading/alpaca_client.py → paper-trading execution via Alpaca
portfolio/tracker.py     → position tracking, P&L
app/main.py              → CLI entry point (argparse: --ticker, --days)
```

Data flows one direction through this pipeline: `fetcher` → `indicators` (`get_summary()` produces a dict) → `ai_analyst` (the summary dict is the literal input to `build_prompt`/`get_signal`, returning `{ticker, signal, confidence, reasoning}`) → `app/main.py` formats and prints it, and eventually `trading`/`portfolio` act on it. Every signal gets appended to a local `signals_log.json` (timestamp, ticker, signal, confidence, reasoning, price) via `log_signal()`/`load_signal_history()`.

Anthropic integration specifics: model `claude-sonnet-4-20250514`, called via `anthropic.Anthropic().messages.create(...)`, response text parsed from `response.content[0].text` into the structured signal dict. Prompts must explicitly instruct the model to output Signal (BULLISH/BEARISH/NEUTRAL), Confidence (High/Moderate/Low), and 2-3 sentences of Reasoning in a parseable format.

The roadmap (`GITHUB_ISSUES.md`, `LINEAR_SETUP.md`) runs through four milestones: M1 Data Foundation (yfinance + indicators + CLI), M2 AI Signal Engine (Anthropic integration + logging), M3 Paper Trading (Alpaca), M4 Portfolio Dashboard (Streamlit UI). M1/M2 issue numbers map to Linear IDs `STO-1`...`STO-10`+; PRs should reference `Closes STO-X`.

## Design reference (`design/`)

Everything in `design/` is **reference material, not application code** — do not run or import it:

- `StockPilot.html` — clickable prototype of all four screens (Signal, Portfolio, Signal Log, Discover). Open this before building the equivalent Streamlit screen.
- `StockPilot Data Flow.html` — maps every UI element to its data source (yfinance / Anthropic / Alpaca / local-derived) and the milestone/issue that builds it. The primary reference when unsure where a piece of data comes from.
- `app.jsx`, `portfolio.jsx`, `signal.jsx`, `history.jsx`, `discover.jsx` — React component trees exported from Claude Design, showing intended screen composition. The real app is Python + Streamlit, not React.
- `atoms.jsx` — shared UI primitives (badges, metric cards, signal chips) and the states they support (BUY/HOLD/SELL/NEUTRAL, gain/loss coloring, confidence meters).
- `data.jsx` — **canonical schema reference** for ticker objects, signal records, and portfolio positions; mirror these shapes when designing Python dataclasses/dicts (e.g. the `get_summary()` and `get_signal()` return shapes, `signals_log.json` records, portfolio position records).

## Brand system (North Star Digital)

Streamlit screens should approximate this palette via `.streamlit/config.toml` theming (Streamlit can't load custom fonts, so match layout/hierarchy from the prototype rather than typography):

| Token | Hex | Role |
|---|---|---|
| Deep Navy | `#0D1B3E` | Primary background |
| Royal Blue | `#1B4F9A` | Content panels, cards |
| Sky Blue | `#5BB3E0` | Labels, links, wordmark |
| Amber Gold | `#F0A500` | CTAs / accent moments only — never a large background |
| Muted Blue-Gray | `#7EA8D4` | Body copy on dark |
| White | `#FFFFFF` | Text on dark, light backgrounds |

Typography: Fraunces (display/headlines), DM Sans Light (body/interface). No gradients, drop shadows, bevels, or stock icons; bullets use em dashes (—).
