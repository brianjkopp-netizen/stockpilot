"""StockPilot application entry point.

Run as Streamlit dashboard:
    streamlit run app/main.py

Run as CLI (M1/M2 behaviour preserved):
    python app/main.py --ticker AAPL
    python -m app.main --ticker AAPL
"""

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

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


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load_watchlist() -> list[str]:
    """Return tickers from watchlist.json, or a sensible default if the file is missing."""
    if not _WATCHLIST_PATH.exists():
        return []
    try:
        with _WATCHLIST_PATH.open() as f:
            data = json.load(f)
        return [t.upper() for t in data if isinstance(t, str) and t.strip()]
    except (json.JSONDecodeError, OSError):
        return []


def _save_watchlist(tickers: list[str]) -> None:
    with _WATCHLIST_PATH.open("w") as f:
        json.dump([t.upper() for t in tickers], f, indent=2)


def _run_analysis(ticker: str, days: int) -> tuple[dict, dict]:
    """Fetch data and return (summary, signal). Raises on any failure."""
    df = get_stock_data(ticker, days)
    df = add_moving_averages(df, _MA_WINDOWS)
    df = add_volume_signal(df)
    summary = get_summary(df)
    signal = get_signal(ticker, summary)
    return summary, signal


# ---------------------------------------------------------------------------
# Streamlit screens
# ---------------------------------------------------------------------------

def _signal_badge_color(signal: str) -> str:
    return {"BULLISH": "green", "BEARISH": "red", "NEUTRAL": "gray"}.get(signal, "gray")


def render_signal() -> None:
    import streamlit as st

    st.title("Signal Analysis")
    st.caption("Enter a ticker to fetch market data and generate an AI trading signal.")

    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input("Ticker symbol", placeholder="e.g. AAPL").strip().upper()
    with col2:
        days_input = st.number_input("Days of history", min_value=14, max_value=365, value=_DEFAULT_DAYS, step=1)

    run = st.button("Analyze", type="primary", disabled=not ticker_input)

    if run and ticker_input:
        with st.spinner(f"Fetching data and generating signal for {ticker_input}…"):
            try:
                summary, signal = _run_analysis(ticker_input, int(days_input))
                st.session_state["last_signal"] = signal
                st.session_state["last_summary"] = summary
            except ValueError as exc:
                st.error(f"Data error: {exc}")
                return
            except ConnectionError as exc:
                st.error(f"Network error: {exc}")
                return
            except SignalGenerationError as exc:
                st.error(f"AI signal error: {exc}")
                return

    signal = st.session_state.get("last_signal")
    summary = st.session_state.get("last_summary")

    if signal is None:
        return

    st.divider()

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Ticker", signal["ticker"])
    m2.metric("Price", f"${summary['current_price']:.2f}")
    m3.metric("MA (10d)", f"${summary['ma_10']:.2f}")
    m4.metric("MA (20d)", f"${summary['ma_20']:.2f}")
    m5.metric("Volume", summary["volume_signal"].title())

    st.divider()

    sig_col, conf_col = st.columns(2)
    with sig_col:
        color = _signal_badge_color(signal["signal"])
        st.markdown(f"**Signal:** :{color}[{signal['signal']}]")
    with conf_col:
        st.markdown(f"**Confidence:** {signal['confidence']}")

    st.markdown(f"**Reasoning:** {signal['reasoning']}")

    if signal.get("key_factors"):
        with st.expander("Key factors"):
            for factor in signal["key_factors"]:
                st.markdown(f"- {factor}")

    if signal["signal"] == "BULLISH" and signal["confidence"] in ("High", "Moderate"):
        st.divider()
        notional = 500.0 if signal["confidence"] == "High" else 200.0
        if st.button(f"Execute paper trade — BUY ${notional:.0f} of {signal['ticker']}", type="primary"):
            from trading.alpaca_client import execute_signal, AlpacaAuthError, AlpacaOrderError
            with st.spinner("Submitting order to Alpaca paper account…"):
                try:
                    order = execute_signal(signal)
                    if order:
                        st.success(
                            f"Order submitted: {order['side']} {order['qty']:.4f} shares of "
                            f"{order['ticker']} (id: {order['id']}, status: {order['status']})"
                        )
                    else:
                        st.warning("No trade placed — insufficient buying power or signal filtered.")
                except AlpacaAuthError as exc:
                    st.error(f"Alpaca auth error: {exc}")
                except AlpacaOrderError as exc:
                    st.error(f"Order failed: {exc}")
                except Exception as exc:
                    st.error(f"Unexpected error: {exc}")


def render_portfolio() -> None:
    import streamlit as st
    import pandas as pd

    st.title("Portfolio")
    st.caption("Live positions and account state from your Alpaca paper account.")

    refresh = st.button("Refresh", type="primary")

    if refresh or "portfolio_state" not in st.session_state:
        from portfolio.tracker import get_portfolio_state
        from trading.alpaca_client import AlpacaAuthError
        with st.spinner("Fetching account data from Alpaca…"):
            try:
                state = get_portfolio_state()
                st.session_state["portfolio_state"] = state
            except AlpacaAuthError as exc:
                st.error(f"Alpaca auth error — check your .env credentials: {exc}")
                return
            except RuntimeError as exc:
                st.error(str(exc))
                return

    state = st.session_state.get("portfolio_state")
    if state is None:
        return

    account = state["account"]
    source_label = " (cached)" if state.get("source") == "cache" else ""
    fetched_at = state.get("fetched_at", "")[:19].replace("T", " ")
    st.caption(f"Data source: Alpaca paper{source_label} · fetched {fetched_at} UTC")

    st.divider()
    c1, c2, c3 = st.columns(3)
    c1.metric("Portfolio Value", f"${account['portfolio_value']:,.2f}")
    c2.metric("Cash", f"${account['cash']:,.2f}")
    c3.metric("Buying Power", f"${account['buying_power']:,.2f}")

    positions = state.get("positions", [])
    st.divider()
    st.subheader(f"Open Positions ({len(positions)})")
    if positions:
        df = pd.DataFrame(positions)[
            ["ticker", "qty", "avg_entry_price", "market_value", "unrealized_pl", "unrealized_plpc"]
        ]
        df.columns = ["Ticker", "Qty", "Avg Entry", "Market Value", "Unrealized P/L", "P/L %"]
        df["Avg Entry"] = df["Avg Entry"].map("${:.2f}".format)
        df["Market Value"] = df["Market Value"].map("${:,.2f}".format)
        df["Unrealized P/L"] = df["Unrealized P/L"].map("${:+.2f}".format)
        df["P/L %"] = df["P/L %"].map("{:+.2%}".format)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No open positions.")

    from trading.trade_history import load_trade_history
    history = load_trade_history()
    st.divider()
    st.subheader(f"Trade History ({len(history)} trades)")
    if history:
        th = pd.DataFrame(history)[
            ["timestamp", "ticker", "side", "qty", "fill_price", "signal", "confidence"]
        ]
        th.columns = ["Timestamp", "Ticker", "Side", "Qty", "Fill Price", "Signal", "Confidence"]
        th["Timestamp"] = th["Timestamp"].str[:19].str.replace("T", " ")
        th["Fill Price"] = th["Fill Price"].map("${:.2f}".format)
        th = th.iloc[::-1].reset_index(drop=True)
        st.dataframe(th, use_container_width=True, hide_index=True)
    else:
        st.info("No trades recorded yet.")


def render_signal_log() -> None:
    import streamlit as st
    import pandas as pd
    from pathlib import Path
    import json

    st.title("Signal Log")
    st.caption("All signals generated by StockPilot, most recent first.")

    log_path = Path(__file__).parent.parent / "signals_log.json"
    if not log_path.exists():
        st.info("No signals logged yet. Run an analysis on the Signal screen.")
        return

    try:
        with log_path.open() as f:
            records = json.load(f)
    except json.JSONDecodeError:
        st.error("signals_log.json is corrupt and cannot be parsed.")
        return

    if not records:
        st.info("signals_log.json is empty.")
        return

    all_tickers = sorted({r.get("ticker", "") for r in records if r.get("ticker")})
    filter_ticker = st.selectbox("Filter by ticker", ["All"] + all_tickers)

    if filter_ticker != "All":
        records = [r for r in records if r.get("ticker", "").upper() == filter_ticker.upper()]

    records = list(reversed(records))

    df = pd.DataFrame(records)[["timestamp", "ticker", "signal", "confidence", "price", "reasoning"]]
    df.columns = ["Timestamp", "Ticker", "Signal", "Confidence", "Price", "Reasoning"]
    df["Timestamp"] = df["Timestamp"].str[:19].str.replace("T", " ")
    df["Price"] = df["Price"].map("${:.2f}".format)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Reasoning": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(f"{len(records)} record(s) shown.")


def render_discover() -> None:
    import streamlit as st
    import pandas as pd

    st.title("Discover")
    st.caption("Scan your watchlist for signals. Add or remove tickers below, then click Scan.")

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
                    st.warning(f"{new_ticker} is already in the watchlist.")
        with remove_col:
            if watchlist:
                to_remove = st.selectbox("Remove ticker", watchlist)
                if st.button("Remove"):
                    watchlist = [t for t in watchlist if t != to_remove]
                    _save_watchlist(watchlist)
                    st.rerun()

    st.markdown(f"**Watchlist:** {', '.join(watchlist) if watchlist else '(empty)'}")
    st.divider()

    if not watchlist:
        st.info("Add at least one ticker to the watchlist, then click Scan.")
        return

    days = st.number_input("Days of history", min_value=14, max_value=365, value=_DEFAULT_DAYS, step=1)

    if st.button("Scan All", type="primary"):
        results = []
        progress = st.progress(0, text="Starting scan…")
        for i, ticker in enumerate(watchlist):
            progress.progress((i + 1) / len(watchlist), text=f"Analyzing {ticker}…")
            try:
                summary, signal = _run_analysis(ticker, int(days))
                results.append({
                    "Ticker": ticker,
                    "Price": f"${summary['current_price']:.2f}",
                    "Signal": signal["signal"],
                    "Confidence": signal["confidence"],
                    "Volume": summary["volume_signal"].title(),
                    "Reasoning": signal["reasoning"],
                })
            except Exception as exc:
                results.append({
                    "Ticker": ticker,
                    "Price": "—",
                    "Signal": "ERROR",
                    "Confidence": "—",
                    "Volume": "—",
                    "Reasoning": str(exc),
                })
        progress.empty()
        st.session_state["discover_results"] = results

    results = st.session_state.get("discover_results")
    if results:
        df = pd.DataFrame(results)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Reasoning": st.column_config.TextColumn(width="large"),
            },
        )


# ---------------------------------------------------------------------------
# Streamlit top-level layout
# ---------------------------------------------------------------------------

def _streamlit_main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="StockPilot",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    page = st.sidebar.radio(
        "Navigation",
        ["Signal", "Portfolio", "Signal Log", "Discover"],
    )
    st.sidebar.divider()
    st.sidebar.caption("StockPilot · Paper Trading")

    if page == "Signal":
        render_signal()
    elif page == "Portfolio":
        render_portfolio()
    elif page == "Signal Log":
        render_signal_log()
    elif page == "Discover":
        render_discover()


# ---------------------------------------------------------------------------
# CLI (preserved from M1/M2 STO-04)
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
