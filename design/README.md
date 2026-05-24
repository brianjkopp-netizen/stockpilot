# StockPilot — Design Reference

This folder contains design artifacts produced in Claude Design using the North Star brand system. These files are **reference material for engineers, not application code.** Nothing here runs in production.

---

## Files

### `StockPilot.html`
Clickable UI prototype. All four screens — Signal, Portfolio, Signal Log, and Discover — are navigable in any browser. Open it before building any Streamlit screen to understand the intended layout, component hierarchy, and data presentation.

### `StockPilot Data Flow.html`
Data flow map. Every numbered UI element on every screen is traced to its data source (yfinance, Anthropic API, Alpaca, or Local/derived), the milestone that builds it, and the issue responsible for it. **This is the primary reference when you're unsure what a component should render or where its data comes from.**

### `app.jsx` · `portfolio.jsx` · `signal.jsx` · `history.jsx` · `discover.jsx`
React component files exported by Claude Design. These represent the intended screen structure as a component tree. Read them to understand how screens are composed and what props each section expects. **Do not attempt to run these.** The application is built in Python + Streamlit, not React.

### `atoms.jsx`
Shared design primitives — badge components, metric cards, signal chips, buttons. Use as a reference for how individual UI elements are constructed and what states they support (BUY / HOLD / SELL / NEUTRAL, gain / loss coloring, confidence meters).

### `data.jsx`
Mock data layer used by the prototype. Contains the shape of every data structure the prototype renders — ticker objects, signal records, portfolio positions, log entries. **Use this as the canonical field reference** when defining Python dataclasses or dict schemas in the backend modules.

---

## Brand System

All design artifacts use the **North Star Digital** brand system. Key tokens:

| Token | Hex | Role |
|---|---|---|
| Deep Navy | `#0D1B3E` | Primary background |
| Royal Blue | `#1B4F9A` | Content panels, cards |
| Sky Blue | `#5BB3E0` | Labels, links, wordmark |
| Amber Gold | `#F0A500` | CTAs, accent moments only |
| Muted Blue-Gray | `#7EA8D4` | Body copy on dark |
| White | `#FFFFFF` | Text on dark, light backgrounds |

Typography: **Fraunces** (display/headlines) · **DM Sans Light** (body/interface)

Streamlit does not support custom fonts natively. Match the layout and data hierarchy from the prototype; approximate the color system using Streamlit's theming config in `.streamlit/config.toml`.

---

## What These Files Do Not Cover

- Streamlit-specific component implementation (that lives in `app/`)
- API authentication or environment config (see `.env` and `CLAUDE.md`)
- Issue acceptance criteria (see GitHub Issues or `GITHUB_ISSUES.md`)

---

## Issue Reference Note

The data flow map references **STO-16 through STO-20** as M3/M4 placeholders. Full issue specs for those will be written after the M2 gate review (STO-10). Treat referenced issue numbers as accurate pointers to future work, not finalized acceptance criteria.
