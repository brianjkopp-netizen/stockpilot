"""StockPilot HTTP API — thin wrappers around the M1–M4 backend.

Start the server:
    uvicorn api.main:app --reload --port 8000

All secrets load from .env. Only the Alpaca paper account is used;
the live trading URL is never referenced here.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

from data.fetcher import get_stock_data
from analysis.indicators import add_moving_averages, add_volume_signal, get_summary
from analysis.ai_analyst import get_signal, load_all_signals, SignalGenerationError
from analysis.discover import scan_ticker
from portfolio.tracker import get_portfolio_state
from portfolio.recommender import get_recommendation, RecommendationError
from trading.alpaca_client import (
    AlpacaAuthError,
    AlpacaNetworkError,
    AlpacaOrderError,
    decide_order,
    get_account_info,
    get_latest_price,
    place_buy_order,
    place_sell_order,
)

_MA_WINDOWS = [10, 20]
_DEFAULT_DAYS = 30
_WATCHLIST_PATH = Path(__file__).parent.parent / "watchlist.json"

# CORS: React dev servers (CRA + Vite) plus an optional deploy origin from env.
_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5173"]
_deploy_origin = os.getenv("CORS_ORIGIN")
if _deploy_origin:
    _CORS_ORIGINS.append(_deploy_origin)

app = FastAPI(title="StockPilot API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Watchlist helpers
# ---------------------------------------------------------------------------

def _load_watchlist() -> list:
    if not _WATCHLIST_PATH.exists():
        return []
    try:
        with _WATCHLIST_PATH.open() as f:
            return [t.upper() for t in json.load(f) if isinstance(t, str) and t.strip()]
    except (json.JSONDecodeError, OSError):
        return []


def _save_watchlist(tickers: list) -> None:
    with _WATCHLIST_PATH.open("w") as f:
        json.dump(tickers, f, indent=2)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class OrderRequest(BaseModel):
    ticker: str
    side: str  # "buy" or "sell"
    qty: Optional[float] = None
    signal: Optional[str] = None
    confidence: Optional[str] = None


class WatchlistAddRequest(BaseModel):
    ticker: str


# ---------------------------------------------------------------------------
# GET /signal/{ticker}
# ---------------------------------------------------------------------------

@app.get("/signal/{ticker}")
def route_get_signal(ticker: str, days: int = _DEFAULT_DAYS):
    """Fetch market data, compute indicators, and return an AI signal.

    Response includes all signal fields plus the indicator summary so the React
    client can render both the verdict and the supporting numbers in one call.
    """
    try:
        df = get_stock_data(ticker.upper(), days)
        df = add_moving_averages(df, _MA_WINDOWS)
        df = add_volume_signal(df)
        summary = get_summary(df)
        signal = get_signal(ticker.upper(), summary)
        return {
            **signal,
            "price": summary["current_price"],
            "ma_10": summary["ma_10"],
            "ma_20": summary["ma_20"],
            "volume_signal": summary["volume_signal"],
        }
    except ValueError as exc:
        raise HTTPException(422, detail=str(exc))
    except ConnectionError as exc:
        raise HTTPException(503, detail=f"Network error: {exc}")
    except SignalGenerationError as exc:
        raise HTTPException(502, detail=f"AI signal error: {exc}")


# ---------------------------------------------------------------------------
# GET /signals
# ---------------------------------------------------------------------------

@app.get("/signals")
def route_get_signals():
    """Return every logged signal record (signals_log.json), most recent first."""
    records = list(reversed(load_all_signals()))
    return {"records": records, "total": len(records)}


# ---------------------------------------------------------------------------
# GET /portfolio
# ---------------------------------------------------------------------------

@app.get("/portfolio")
def route_get_portfolio():
    """Return live portfolio state: positions marked to market, totals, account."""
    try:
        return get_portfolio_state()
    except AlpacaAuthError as exc:
        raise HTTPException(503, detail=f"Alpaca auth error: {exc}")
    except (AlpacaNetworkError, RuntimeError) as exc:
        raise HTTPException(503, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /portfolio/{ticker}/recommendation
# ---------------------------------------------------------------------------

@app.get("/portfolio/{ticker}/recommendation")
def route_get_recommendation(ticker: str):
    """Return a HOLD / ADD / SELL recommendation for an open position."""
    try:
        state = get_portfolio_state()
    except AlpacaAuthError as exc:
        raise HTTPException(503, detail=f"Alpaca auth error: {exc}")
    except (AlpacaNetworkError, RuntimeError) as exc:
        raise HTTPException(503, detail=str(exc))

    position = next(
        (p for p in state.get("positions", []) if p["ticker"].upper() == ticker.upper()),
        None,
    )
    if position is None:
        raise HTTPException(404, detail=f"No open position for {ticker.upper()}")

    try:
        return get_recommendation(position)
    except RecommendationError as exc:
        raise HTTPException(502, detail=f"Recommendation error: {exc}")
    except (ValueError, ConnectionError) as exc:
        raise HTTPException(503, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /discover
# ---------------------------------------------------------------------------

@app.get("/discover")
def route_discover(days: int = _DEFAULT_DAYS):
    """Scan the watchlist and return AI signals for every ticker.

    Each result matches the shape of analysis.discover.scan_ticker — ticker,
    company_name, signal, confidence, price, drift_5d, sparkline, reasoning,
    error. The internal _signal_obj field is stripped before returning.
    """
    watchlist = _load_watchlist()
    raw_results = [scan_ticker(t, days) for t in watchlist]

    results = [{k: v for k, v in r.items() if k != "_signal_obj"} for r in raw_results]

    counts: dict = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    for r in results:
        if r["signal"] in counts:
            counts[r["signal"]] += 1

    return {
        "results": results,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "total": len(watchlist),
        "counts": counts,
    }


# ---------------------------------------------------------------------------
# GET /watchlist · POST /watchlist · DELETE /watchlist/{ticker}
# ---------------------------------------------------------------------------

@app.get("/watchlist")
def route_get_watchlist():
    """Return the current watchlist."""
    return {"tickers": _load_watchlist()}


@app.post("/watchlist")
def route_add_watchlist(body: WatchlistAddRequest):
    """Add a ticker to the watchlist. Idempotent — no-op if already present."""
    ticker = body.ticker.upper().strip()
    if not ticker:
        raise HTTPException(422, detail="ticker must not be empty")
    tickers = _load_watchlist()
    if ticker not in tickers:
        tickers.append(ticker)
        _save_watchlist(tickers)
    return {"tickers": tickers}


@app.delete("/watchlist/{ticker}")
def route_remove_watchlist(ticker: str):
    """Remove a ticker from the watchlist. No-op if not present."""
    ticker = ticker.upper()
    tickers = [t for t in _load_watchlist() if t != ticker]
    _save_watchlist(tickers)
    return {"tickers": tickers}


# ---------------------------------------------------------------------------
# POST /orders
# ---------------------------------------------------------------------------

@app.post("/orders")
def route_place_order(body: OrderRequest):
    """Place a paper buy or sell order on the Alpaca paper account.

    Buy: requires signal + confidence; uses decide_order() to determine notional
    amount ($500 High / $200 Moderate). Returns placed=False when the
    signal/confidence is below threshold or buying power is insufficient.

    Sell: requires qty (number of shares to sell).

    Response: {"placed": bool, "order": dict|null, "reason": str|null}
    """
    ticker = body.ticker.upper()
    side = body.side.lower()

    if side not in ("buy", "sell"):
        raise HTTPException(422, detail="side must be 'buy' or 'sell'")

    try:
        if side == "buy":
            if not body.signal or not body.confidence:
                raise HTTPException(422, detail="signal and confidence are required for buy orders")

            action, notional = decide_order(body.signal, body.confidence)
            if action is None:
                return {"placed": False, "reason": "Signal/confidence below buy threshold", "order": None}

            price = get_latest_price(ticker)
            account = get_account_info()
            if account["buying_power"] < notional:
                return {"placed": False, "reason": "Insufficient buying power", "order": None}

            qty = round(notional / price, 4)
            order = place_buy_order(ticker, qty, signal=body.signal, confidence=body.confidence)
            return {"placed": True, "order": order, "reason": None}

        else:
            if body.qty is None or body.qty <= 0:
                raise HTTPException(422, detail="qty must be a positive number for sell orders")
            order = place_sell_order(ticker, body.qty)
            return {"placed": True, "order": order, "reason": None}

    except HTTPException:
        raise
    except AlpacaAuthError as exc:
        raise HTTPException(503, detail=f"Alpaca auth error: {exc}")
    except AlpacaOrderError as exc:
        raise HTTPException(502, detail=f"Order failed: {exc}")
    except (ConnectionError, ValueError) as exc:
        raise HTTPException(422, detail=str(exc))