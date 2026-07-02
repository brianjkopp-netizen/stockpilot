"""StockPilot application entry point.

Run as Streamlit dashboard:
    streamlit run app/main.py

Run as CLI (M1/M2 behaviour preserved):
    python app/main.py --ticker AAPL
    python -m app.main --ticker AAPL
"""

import argparse
import html as _html_lib
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from data.fetcher import get_stock_data
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary
from analysis.ai_analyst import get_signal, SignalGenerationError

_DEFAULT_DAYS = 30
_MA_WINDOWS = [10, 20]
_WIDTH = 80
_LABEL_WIDTH = 16

_WATCHLIST_PATH = Path(__file__).parent.parent / "watchlist.json"
_SIGNALS_LOG_PATH = Path(__file__).parent.parent / "signals_log.json"

# Brand tokens — approximating North Star Digital palette in Streamlit
_SKY = "#5BB3E0"
_GOLD = "#F0A500"
_MUTE = "#7EA8D4"


# ---------------------------------------------------------------------------
# Shared helpers (no Streamlit imports — safe for CLI path too)
# ---------------------------------------------------------------------------

def _load_watchlist() -> list:
    if not _WATCHLIST_PATH.exists():
        return []
    try:
        with _WATCHLIST_PATH.open() as f:
            data = json.load(f)
        return [t.upper() for t in data if isinstance(t, str) and t.strip()]
    except (json.JSONDecodeError, OSError):
        return []


def _save_watchlist(tickers: list) -> None:
    with _WATCHLIST_PATH.open("w") as f:
        json.dump([t.upper() for t in tickers], f, indent=2)


def _run_analysis(ticker: str, days: int) -> tuple:
    """Fetch data and return (summary, signal). Raises on any failure."""
    df = get_stock_data(ticker, days)
    df = add_moving_averages(df, _MA_WINDOWS)
    df = add_volume_signal(df)
    summary = get_summary(df)
    signal = get_signal(ticker, summary)
    return summary, signal


def _fetch_sparkline(ticker: str) -> list:
    """Return last 14 trading-day close prices for ticker. Returns [] on error."""
    try:
        df = get_stock_data(ticker, days=20)
        return df["Close"].dropna().tail(14).tolist()
    except Exception:
        return []


def _fetch_account_safe() -> Optional[dict]:
    """Return Alpaca account info dict or None if unavailable."""
    try:
        from trading.alpaca_client import get_account_info
        return get_account_info()
    except Exception:
        return None


def _md(text: str) -> str:
    """Escape dollar signs so Streamlit markdown doesn't render them as LaTeX."""
    return text.replace("$", r"\$")


def _h(text: str) -> str:
    """Escape text for safe embedding in an HTML string."""
    return _html_lib.escape(str(text))


def _signal_color(signal: str) -> str:
    return {"BULLISH": _GOLD, "BEARISH": _MUTE, "NEUTRAL": _SKY}.get(signal, _MUTE)


# ---------------------------------------------------------------------------
# Streamlit chrome — present on every screen
# ---------------------------------------------------------------------------

def _render_sidebar_account() -> None:
    """Render live Alpaca account totals. Degrades gracefully if unreachable."""
    import streamlit as st

    if "account_info" not in st.session_state:
        st.session_state["account_info"] = _fetch_account_safe()

    account = st.session_state.get("account_info")

    st.markdown(
        f'<span style="font-size:10px;letter-spacing:0.18em;text-transform:uppercase;'
        f'color:{_SKY};">Account · Paper</span>',
        unsafe_allow_html=True,
    )

    if account:
        st.metric("Portfolio Value", f"${account['portfolio_value']:,.2f}")
        st.metric("Cash", f"${account['cash']:,.2f}")
        st.metric("Buying Power", f"${account['buying_power']:,.2f}")
    else:
        st.caption("Alpaca unreachable — check .env credentials.")

    if st.button("↻ Refresh account", key="sb_refresh_account", use_container_width=True):
        st.session_state["account_info"] = _fetch_account_safe()
        st.session_state.pop("portfolio_state", None)
        st.rerun()


def _render_topbar(page: str) -> None:
    """Static topbar chrome — wordmark left, current page right."""
    import streamlit as st

    col_left, col_right = st.columns([1, 5])
    with col_left:
        st.markdown(
            f'<span style="font-size:11px;letter-spacing:0.22em;text-transform:uppercase;'
            f'font-weight:600;color:{_SKY};">STOCKPILOT</span>',
            unsafe_allow_html=True,
        )
    with col_right:
        st.markdown(
            f'<span style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;'
            f'color:{_MUTE};">{_h(page)}</span>',
            unsafe_allow_html=True,
        )
    st.divider()


# ---------------------------------------------------------------------------
# Signal screen
# ---------------------------------------------------------------------------

def render_signal() -> None:
    import streamlit as st

    st.subheader("AI Signal Analysis")
    st.caption(
        "Enter a ticker. StockPilot pulls 30 days of market data, computes indicators, "
        "and asks Claude for a structured signal with confidence and plain-language reasoning."
    )

    col_ticker, col_days, col_btn = st.columns([3, 1, 1])
    with col_ticker:
        ticker_input = st.text_input("Ticker", placeholder="e.g. AAPL, NVDA, TSLA").strip().upper()
    with col_days:
        days_input = st.number_input("Days", min_value=14, max_value=365, value=_DEFAULT_DAYS)
    with col_btn:
        st.write("")
        run = st.button("Analyze", type="primary", disabled=not ticker_input, use_container_width=True)

    if run and ticker_input:
        _do_analysis(ticker_input, int(days_input))

    signal = st.session_state.get("last_signal")
    summary = st.session_state.get("last_summary")

    if signal is None:
        return

    st.divider()
    _render_signal_result(signal, summary)


def _do_analysis(ticker: str, days: int) -> None:
    """Run the 4-phase analysis pipeline with progress feedback; store results in session_state."""
    import streamlit as st

    progress = st.progress(0, text=f"Fetching market data for {ticker}…")
    try:
        df = get_stock_data(ticker, days)
        progress.progress(0.30, text="Computing indicators…")
        df = add_moving_averages(df, _MA_WINDOWS)
        df = add_volume_signal(df)
        summary = get_summary(df)
        progress.progress(0.60, text="Querying Anthropic API…")
        signal = get_signal(ticker, summary)
        progress.progress(1.0, text="Done.")
        st.session_state["last_signal"] = signal
        st.session_state["last_summary"] = summary
    except ValueError as exc:
        st.error(f"Data error: {exc}")
    except ConnectionError as exc:
        st.error(f"Network error: {exc}")
    except SignalGenerationError as exc:
        st.error(f"AI error: {exc}")
    finally:
        progress.empty()


def _render_signal_result(signal: dict, summary: dict) -> None:
    """Two-column layout: left = price + reasoning, right = indicators + act."""
    import streamlit as st

    left_col, right_col = st.columns([3, 2], gap="large")

    with left_col:
        sig_color = _signal_color(signal["signal"])
        price = summary["current_price"]

        # Price headline + signal badge
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;justify-content:space-between;'
            f'margin-bottom:16px;">'
            f'<div>'
            f'<div style="font-size:11px;letter-spacing:0.14em;text-transform:uppercase;'
            f'color:{_SKY};margin-bottom:4px;">Last Close</div>'
            f'<div style="font-size:44px;font-weight:600;line-height:1;letter-spacing:-0.01em;">'
            f'${price:,.2f}</div>'
            f'</div>'
            f'<span style="display:inline-block;padding:6px 14px;'
            f'border:1px solid {sig_color};color:{sig_color};'
            f'font-size:11px;letter-spacing:0.18em;text-transform:uppercase;margin-top:6px;">'
            f'&#9679; {_h(signal["signal"])}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Reasoning panel
        st.markdown(
            f'<div style="font-size:10px;letter-spacing:0.18em;text-transform:uppercase;'
            f'color:{_MUTE};margin-bottom:8px;">Reasoning · claude-sonnet-4</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="border-left:2px solid {_SKY};padding:14px 16px;'
            f'font-size:13.5px;line-height:1.65;color:rgba(255,255,255,0.92);">'
            f'<span style="font-size:10px;letter-spacing:0.2em;text-transform:uppercase;'
            f'color:{_SKY};margin-right:10px;">AI Analyst</span>'
            f'{_h(signal["reasoning"])}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if signal.get("key_factors"):
            with st.expander("Key factors"):
                for factor in signal["key_factors"]:
                    safe_factor = _md(factor)
                    st.markdown(f"- {safe_factor}")

        st.divider()
        m1, m2, m3 = st.columns(3)
        m1.metric("Signal", signal["signal"])
        m2.metric("Confidence", signal["confidence"])
        m3.metric("Ticker", signal["ticker"])

    with right_col:
        # Indicators panel
        st.markdown(
            f'<div style="font-size:10px;letter-spacing:0.18em;text-transform:uppercase;'
            f'color:{_MUTE};margin-bottom:12px;">Indicators · 30d</div>',
            unsafe_allow_html=True,
        )

        ma10_pct = (summary["current_price"] - summary["ma_10"]) / summary["ma_10"] * 100
        ma20_pct = (summary["current_price"] - summary["ma_20"]) / summary["ma_20"] * 100

        ind_rows = [
            ("Current", f"${summary['current_price']:.2f}", ""),
            ("MA · 10", f"${summary['ma_10']:.2f}", f"{ma10_pct:+.2f}%"),
            ("MA · 20", f"${summary['ma_20']:.2f}", f"{ma20_pct:+.2f}%"),
            ("Volume",  summary["volume_signal"].title(), ""),
        ]
        table_rows = "".join(
            f'<tr style="border-bottom:1px solid rgba(255,255,255,0.07);">'
            f'<td style="padding:10px 0;font-size:11px;letter-spacing:0.12em;'
            f'text-transform:uppercase;color:{_MUTE};">{label}</td>'
            f'<td style="padding:10px 0;font-size:13px;text-align:right;">{val}</td>'
            f'<td style="padding:10px 4px;font-size:11px;text-align:right;'
            f'color:{"" if not sub else (_GOLD if not sub.startswith("-") else _MUTE)}">'
            f'{sub}</td>'
            f'</tr>'
            for label, val, sub in ind_rows
        )
        st.markdown(
            f'<table style="width:100%;border-collapse:collapse;">{table_rows}</table>',
            unsafe_allow_html=True,
        )

        st.divider()

        # Act on signal panel
        st.markdown(
            f'<div style="font-size:10px;letter-spacing:0.18em;text-transform:uppercase;'
            f'color:{_MUTE};margin-bottom:12px;">Act on Signal · Paper · Alpaca</div>',
            unsafe_allow_html=True,
        )

        if signal["signal"] == "BULLISH" and signal["confidence"] in ("High", "Moderate"):
            notional = 500.0 if signal["confidence"] == "High" else 200.0
            st.markdown(
                f'<div style="font-size:12.5px;line-height:1.6;color:rgba(255,255,255,0.8);">'
                f'Signal is <strong style="color:{_GOLD};">{_h(signal["signal"])}</strong>'
                f' / {_h(signal["confidence"])} — eligible for a ${notional:.0f} paper buy.</div>',
                unsafe_allow_html=True,
            )
            if st.button(f"Open paper buy · ${notional:.0f}", type="primary", use_container_width=True):
                _execute_paper_trade(signal)
        else:
            st.markdown(
                f'<div style="font-size:12.5px;color:{_MUTE};line-height:1.6;">'
                f'Signal is <strong>{_h(signal["signal"])}</strong> / {_h(signal["confidence"])} — '
                f'no trade warranted.<br>'
                f'BEARISH and Low-confidence signals are skipped on this paper account.</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            f'<div style="margin-top:12px;font-size:11px;color:{_MUTE};line-height:1.5;">'
            f'All trades routed through Alpaca paper account. '
            f'No real capital at risk. Signal is logged regardless of action.</div>',
            unsafe_allow_html=True,
        )


def _execute_paper_trade(signal: dict) -> None:
    import streamlit as st
    from trading.alpaca_client import execute_signal, AlpacaAuthError, AlpacaOrderError

    with st.spinner("Submitting to Alpaca paper account…"):
        try:
            order = execute_signal(signal)
            if order:
                st.success(
                    f"{order['side']} {order['qty']:.4f} sh of {order['ticker']} — "
                    f"id {order['id'][:8]}… status {order['status']}"
                )
                st.session_state.pop("account_info", None)
                st.session_state.pop("portfolio_state", None)
            else:
                st.warning("No order placed — insufficient buying power or signal filtered.")
        except AlpacaAuthError as exc:
            st.error(f"Alpaca auth error: {exc}")
        except AlpacaOrderError as exc:
            st.error(f"Order failed: {exc}")
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Portfolio screen
# ---------------------------------------------------------------------------

def _gain_color(value: float) -> str:
    """Gold for gain/flat, muted blue-gray for loss — matches the design system's P&L coloring."""
    return _GOLD if value >= 0 else _MUTE


def _fmt_signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "-"
    return f"{sign}${abs(value):,.2f}"


def _verdict_color(verdict: str) -> str:
    return {"ADD": _GOLD, "SELL": _MUTE, "HOLD": _SKY}.get(verdict, _MUTE)


def _verdict_pill(verdict: str) -> str:
    color = _verdict_color(verdict)
    return (
        f'<span style="display:inline-block;padding:2px 8px;'
        f'border:1px solid {color};color:{color};'
        f'font-size:9px;letter-spacing:0.16em;text-transform:uppercase;">'
        f'{_h(verdict)}</span>'
    )


def _sparkline_svg(values: list, color: str, width: int = 110, height: int = 32) -> str:
    """Minimal inline SVG sparkline — mirrors the Sparkline atom in design/atoms.jsx."""
    if not values or len(values) < 2:
        return f'<span style="font-size:11px;color:{_MUTE};">no trend data</span>'
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    step_x = width / (len(values) - 1)
    points = " ".join(
        f"{i * step_x:.1f},{height - ((v - lo) / span) * height:.1f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="1.25"/>'
        f"</svg>"
    )


def _kpi_card(label: str, value: str, color: str = "#FFFFFF") -> str:
    return (
        f'<div style="font-size:10px;letter-spacing:0.14em;text-transform:uppercase;'
        f'color:{_MUTE};margin-bottom:4px;">{label}</div>'
        f'<div style="font-size:22px;font-weight:600;color:{color};">{value}</div>'
    )


def _render_position_card(p: dict, rec: Optional[dict] = None) -> None:
    """One position rendered as a row of metric cards: ticker/qty, entry, value, P&L, daily P&L, sparkline.

    When rec is supplied, the verdict pill is shown under the ticker and the
    AI brief is rendered as a full-width strip below the metric row.
    """
    import streamlit as st

    pl_color = _gain_color(p["unrealized_pl"])
    daily_color = _gain_color(p["daily_pl"])
    sparkline = _fetch_sparkline(p["ticker"])
    spark_color = _gain_color(sparkline[-1] - sparkline[0]) if len(sparkline) >= 2 else _MUTE

    with st.container(border=True):
        c_ticker, c_qty, c_entry, c_value, c_pl, c_daily, c_spark = st.columns(
            [1.1, 0.9, 1.1, 1.3, 1.5, 1.5, 1.3]
        )

        ticker_html = (
            f'<div style="font-size:10px;letter-spacing:0.14em;text-transform:uppercase;'
            f'color:{_SKY};margin-bottom:4px;">Ticker</div>'
            f'<div style="font-size:18px;font-weight:600;">{_h(p["ticker"])}</div>'
        )
        if rec:
            ticker_html += f'<div style="margin-top:6px;">{_verdict_pill(rec["verdict"])}</div>'
        c_ticker.markdown(ticker_html, unsafe_allow_html=True)

        c_qty.markdown(_kpi_card("Qty", f"{p['qty']:.4f}"), unsafe_allow_html=True)
        c_entry.markdown(_kpi_card("Avg Entry", f"${p['avg_entry_price']:.2f}"), unsafe_allow_html=True)
        c_value.markdown(_kpi_card("Market Value", f"${p['market_value']:,.2f}"), unsafe_allow_html=True)

        c_pl.markdown(
            _kpi_card("Unrealized P&L", _fmt_signed_money(p["unrealized_pl"]), pl_color)
            + f'<div style="font-size:11px;color:{pl_color};">{p["unrealized_plpc"] * 100:+.2f}%</div>',
            unsafe_allow_html=True,
        )
        c_daily.markdown(
            _kpi_card("Daily P&L", _fmt_signed_money(p["daily_pl"]), daily_color)
            + f'<div style="font-size:11px;color:{daily_color};">{p["daily_plpc"] * 100:+.2f}%</div>',
            unsafe_allow_html=True,
        )

        with c_spark:
            st.markdown(
                f'<div style="font-size:10px;letter-spacing:0.14em;text-transform:uppercase;'
                f'color:{_MUTE};margin-bottom:4px;">Trend · 14d</div>'
                f"{_sparkline_svg(sparkline, spark_color)}",
                unsafe_allow_html=True,
            )

        if rec and rec.get("brief"):
            brief_color = _MUTE if rec.get("error") else "rgba(255,255,255,0.80)"
            st.markdown(
                f'<div style="border-top:1px solid rgba(255,255,255,0.07);'
                f'margin-top:10px;padding-top:10px;font-size:12.5px;line-height:1.65;'
                f'color:{brief_color};">'
                f'<span style="font-size:9px;letter-spacing:0.18em;text-transform:uppercase;'
                f'color:{_MUTE};margin-right:8px;">AI Brief</span>'
                f'{_h(rec["brief"])}'
                f'</div>',
                unsafe_allow_html=True,
            )


def _refresh_recs(positions: list) -> None:
    """Run the recommendation pass for all positions, storing results in session_state["recs"].

    Errors for individual positions are captured as degraded rec dicts rather
    than propagating — the screen must not crash if one ticker's API call fails.
    """
    import streamlit as st
    from portfolio.recommender import RecommendationError, get_recommendation

    recs: dict = {}
    prog = st.progress(0, text="Generating recommendations…")
    for i, pos in enumerate(positions):
        prog.progress((i + 1) / len(positions), text=f"Analyzing {pos['ticker']}…")
        try:
            recs[pos["ticker"]] = get_recommendation(pos)
        except (RecommendationError, ValueError, ConnectionError) as exc:
            recs[pos["ticker"]] = {
                "ticker": pos["ticker"],
                "verdict": "HOLD",
                "brief": f"Recommendation unavailable: {exc}",
                "signal": "—",
                "confidence": "—",
                "error": True,
            }
    prog.empty()
    st.session_state["recs"] = recs


def render_portfolio() -> None:
    import streamlit as st
    import pandas as pd

    st.subheader("Portfolio")
    st.caption("Live positions marked to market via yfinance against your Alpaca paper account.")

    col_refresh, col_recs = st.columns([1, 1])
    with col_refresh:
        if st.button("↻ Refresh", type="primary"):
            st.session_state.pop("portfolio_state", None)
            st.session_state.pop("account_info", None)
            st.session_state.pop("recs", None)
    with col_recs:
        positions_for_recs = st.session_state.get("portfolio_state", {}).get("positions", [])
        if st.button("↻ Refresh recs", disabled=not positions_for_recs):
            _refresh_recs(positions_for_recs)
            st.rerun()

    if "portfolio_state" not in st.session_state:
        from portfolio.tracker import get_portfolio_state
        from trading.alpaca_client import AlpacaAuthError
        with st.spinner("Fetching from Alpaca…"):
            try:
                st.session_state["portfolio_state"] = get_portfolio_state()
                st.session_state["account_info"] = _fetch_account_safe()
            except AlpacaAuthError as exc:
                st.error(f"Alpaca auth error — check .env credentials: {exc}")
                return
            except RuntimeError as exc:
                st.error(str(exc))
                return

    state = st.session_state.get("portfolio_state")
    if state is None:
        return

    account = state["account"]
    totals = state.get("totals", {})
    source_label = " (cached)" if state.get("source") == "cache" else ""
    fetched_at = state.get("fetched_at", "")[:19].replace("T", " ")
    st.caption(f"Alpaca paper{source_label} · {fetched_at} UTC")

    positions = state.get("positions", [])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Portfolio Value", f"${account['portfolio_value']:,.2f}")
    k2.markdown(
        _kpi_card(
            "Unrealized P&L",
            _fmt_signed_money(totals.get("unrealized_pl", 0.0)),
            _gain_color(totals.get("unrealized_pl", 0.0)),
        ),
        unsafe_allow_html=True,
    )
    k3.markdown(
        _kpi_card(
            "Today's P&L",
            _fmt_signed_money(totals.get("daily_pl", 0.0)),
            _gain_color(totals.get("daily_pl", 0.0)),
        ),
        unsafe_allow_html=True,
    )
    k4.metric("Cash · Paper", f"${account['cash']:,.2f}")
    k5.metric("Open Positions", str(len(positions)))

    st.divider()
    st.markdown(
        f"**Open Positions** · {len(positions)} held · "
        f"${totals.get('market_value', 0.0):,.2f} marked"
    )

    recs = st.session_state.get("recs", {})
    if positions:
        for p in positions:
            _render_position_card(p, rec=recs.get(p["ticker"]))
    else:
        st.info("No open positions.")

    from trading.trade_history import load_trade_history
    history = load_trade_history()
    st.divider()
    st.markdown(f"**Trade History** · {len(history)} trade{'s' if len(history) != 1 else ''}")

    if history:
        th_df = pd.DataFrame(history)[
            ["timestamp", "ticker", "side", "qty", "fill_price", "signal", "confidence"]
        ].copy()
        th_df.columns = ["Timestamp", "Ticker", "Side", "Qty", "Fill Price", "Signal", "Confidence"]
        th_df["Timestamp"] = th_df["Timestamp"].str[:19].str.replace("T", " ")
        th_df["Fill Price"] = pd.to_numeric(th_df["Fill Price"])
        th_df = th_df.iloc[::-1].reset_index(drop=True)
        st.dataframe(
            th_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fill Price": st.column_config.NumberColumn(format="$%.2f"),
            },
        )
    else:
        st.info("No trades recorded yet.")


# ---------------------------------------------------------------------------
# Signal Log screen
# ---------------------------------------------------------------------------

def render_signal_log() -> None:
    import streamlit as st
    import pandas as pd

    st.subheader("Signal Log")
    st.caption(
        "Every signal call writes a row to `signals_log.json`. "
        "Use this log to review reasoning against actual price action "
        "and tune confidence thresholds."
    )

    if not _SIGNALS_LOG_PATH.exists():
        st.info("No signals logged yet. Run an analysis on the Signal screen.")
        return

    try:
        with _SIGNALS_LOG_PATH.open() as f:
            records = json.load(f)
    except json.JSONDecodeError:
        st.error("signals_log.json is corrupt and cannot be parsed.")
        return

    if not records:
        st.info("No signals logged yet.")
        return

    total = len(records)
    bullish = sum(1 for r in records if r.get("signal") == "BULLISH")
    bearish = sum(1 for r in records if r.get("signal") == "BEARISH")
    neutral = total - bullish - bearish

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Signals", str(total))
    k2.metric("Bullish", str(bullish))
    k3.metric("Bearish", str(bearish))
    k4.metric("Neutral", str(neutral))

    st.divider()

    all_tickers = sorted({r.get("ticker", "") for r in records if r.get("ticker")})
    f1, f2 = st.columns([2, 2])
    with f1:
        signal_filter = st.selectbox("Signal", ["ALL", "BULLISH", "BEARISH", "NEUTRAL"])
    with f2:
        ticker_filter = st.selectbox("Ticker", ["ALL"] + all_tickers)

    filtered = [
        r for r in records
        if (signal_filter == "ALL" or r.get("signal") == signal_filter)
        and (ticker_filter == "ALL" or r.get("ticker", "").upper() == ticker_filter.upper())
    ]
    filtered = list(reversed(filtered))

    st.caption(f"Showing {len(filtered)} of {total}")

    if not filtered:
        st.info("No signals match the current filter.")
        return

    df = pd.DataFrame(filtered)[["timestamp", "ticker", "signal", "confidence", "price", "reasoning"]]
    df.columns = ["Timestamp", "Ticker", "Signal", "Confidence", "Price", "Reasoning"]
    df["Timestamp"] = df["Timestamp"].str[:19].str.replace("T", " ")
    df["Price"] = pd.to_numeric(df["Price"])

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price":     st.column_config.NumberColumn(format="$%.2f"),
            "Reasoning": st.column_config.TextColumn(width="large"),
        },
    )


# ---------------------------------------------------------------------------
# Discover screen
# ---------------------------------------------------------------------------

def render_discover() -> None:
    import streamlit as st
    import pandas as pd

    st.subheader("Discover")
    st.caption(
        "Scan your watchlist for signals. "
        "The AI evaluates each ticker and surfaces constructive setups."
    )

    watchlist = _load_watchlist()

    with st.expander("Manage watchlist"):
        add_col, remove_col = st.columns(2)
        with add_col:
            new_ticker = st.text_input("Add ticker").strip().upper()
            if st.button("Add") and new_ticker:
                if new_ticker not in watchlist:
                    watchlist.append(new_ticker)
                    _save_watchlist(watchlist)
                    st.rerun()
                else:
                    st.warning(f"{new_ticker} is already on the watchlist.")
        with remove_col:
            if watchlist:
                to_remove = st.selectbox("Remove ticker", watchlist)
                if st.button("Remove"):
                    watchlist = [t for t in watchlist if t != to_remove]
                    _save_watchlist(watchlist)
                    st.rerun()

    if not watchlist:
        st.info("Add at least one ticker to the watchlist, then click Scan.")
        return

    chips = " ".join(
        f'<span style="font-size:11.5px;padding:4px 10px;'
        f'border:1px solid rgba(255,255,255,0.12);color:{_MUTE};'
        f'letter-spacing:0.04em;">{_h(t)}</span>'
        for t in watchlist
    )
    st.markdown(
        f'<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;">{chips}</div>',
        unsafe_allow_html=True,
    )

    days = st.number_input("Days of history", min_value=14, max_value=365, value=_DEFAULT_DAYS, step=1)

    if st.button("Scan All", type="primary"):
        results = []
        progress = st.progress(0, text="Starting scan…")
        for i, ticker in enumerate(watchlist):
            progress.progress((i + 1) / len(watchlist), text=f"Analyzing {ticker}…")
            try:
                summary, signal = _run_analysis(ticker, int(days))
                sparkline = _fetch_sparkline(ticker)
                results.append({
                    "Ticker":      ticker,
                    "Price":       summary["current_price"],
                    "Signal":      signal["signal"],
                    "Confidence":  signal["confidence"],
                    "Volume":      summary["volume_signal"].title(),
                    "Trend · 14d": sparkline,
                    "Reasoning":   signal["reasoning"],
                })
            except Exception as exc:
                results.append({
                    "Ticker":      ticker,
                    "Price":       None,
                    "Signal":      "ERROR",
                    "Confidence":  "—",
                    "Volume":      "—",
                    "Trend · 14d": [],
                    "Reasoning":   str(exc),
                })
        progress.empty()
        st.session_state["discover_results"] = results

    results = st.session_state.get("discover_results")
    if not results:
        return

    df = pd.DataFrame(results)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Price":       st.column_config.NumberColumn(format="$%.2f"),
            "Trend · 14d": st.column_config.LineChartColumn("Trend · 14d"),
            "Reasoning":   st.column_config.TextColumn(width="large"),
        },
    )


# ---------------------------------------------------------------------------
# Streamlit top-level router
# ---------------------------------------------------------------------------

def _streamlit_main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="StockPilot",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    with st.sidebar:
        st.markdown(
            f'<span style="font-size:13px;letter-spacing:0.22em;text-transform:uppercase;'
            f'font-weight:600;color:{_SKY};">STOCKPILOT</span>',
            unsafe_allow_html=True,
        )
        st.caption("Paper Trading · AI Signals")
        st.divider()

        page = st.radio(
            "Navigate",
            ["Signal", "Portfolio", "Signal Log", "Discover"],
            label_visibility="collapsed",
        )

        st.divider()
        _render_sidebar_account()

    _render_topbar(page)

    if page == "Signal":
        render_signal()
    elif page == "Portfolio":
        render_portfolio()
    elif page == "Signal Log":
        render_signal_log()
    elif page == "Discover":
        render_discover()


# ---------------------------------------------------------------------------
# CLI — preserved from M1/M2 (STO-04)
# ---------------------------------------------------------------------------

def _row(label: str, value: str) -> str:
    return f"{label:<{_LABEL_WIDTH}}{value}"


def _reasoning_row(text: str) -> str:
    return textwrap.fill(
        text,
        width=_WIDTH,
        initial_indent=f"{'Reasoning:':<{_LABEL_WIDTH}}",
        subsequent_indent=" " * _LABEL_WIDTH,
    )


def _cli_main() -> None:
    """Parse CLI arguments, fetch stock data, compute indicators, call AI for a signal, and print results."""
    parser = argparse.ArgumentParser(
        description="StockPilot — fetch stock data, compute indicators, and generate an AI trading signal."
    )
    parser.add_argument("--ticker", default=None, help="Stock ticker symbol, e.g. AAPL")
    parser.add_argument(
        "--days",
        type=int,
        default=_DEFAULT_DAYS,
        help=f"Number of calendar days of history to fetch (default: {_DEFAULT_DAYS})",
    )
    args = parser.parse_args()

    if not args.ticker:
        args.ticker = input("Enter ticker symbol: ").strip()

    t_start = time.perf_counter()

    try:
        df = get_stock_data(args.ticker, args.days)
        df = add_moving_averages(df, _MA_WINDOWS)
        df = add_volume_signal(df)
        summary = get_summary(df)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as exc:
        print(f"Network error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching AI signal for {args.ticker.upper()}…", flush=True)
    try:
        signal = get_signal(args.ticker, summary)
    except SignalGenerationError as exc:
        print(f"AI signal error: {exc}", file=sys.stderr)
        sys.exit(1)

    t_end = time.perf_counter()

    ticker = args.ticker.upper()
    date_from = df.index[0].strftime("%Y-%m-%d")
    date_to = df.index[-1].strftime("%Y-%m-%d")
    sep = "=" * _WIDTH

    print(f"\n{sep}")
    print("StockPilot -- AI Signal Analysis")
    print(sep)
    print(_row("Ticker:", ticker))
    print(_row("Date Range:", f"{date_from} to {date_to}"))
    print(_row("Current Price:", f"${summary['current_price']:.2f}"))
    print(_row("MA (10-day):", f"${summary['ma_10']:.2f}"))
    print(_row("MA (20-day):", f"${summary['ma_20']:.2f}"))
    print(_row("Volume Signal:", summary["volume_signal"]))
    print()
    print("--- AI Signal ---")
    print(_row("Signal:", signal["signal"]))
    print(_row("Confidence:", signal["confidence"]))
    print(_reasoning_row(signal["reasoning"]))
    print()
    print(f"Runtime: {t_end - t_start:.1f}s")
    print(sep)
    print()


# ---------------------------------------------------------------------------
# Entry point — detects Streamlit vs CLI context automatically
# ---------------------------------------------------------------------------

def _is_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except ImportError:
        return False


def main() -> None:
    if _is_streamlit():
        _streamlit_main()
    else:
        _cli_main()


if _is_streamlit():
    _streamlit_main()
elif __name__ == "__main__":
    _cli_main()
