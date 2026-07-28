"""StockPilot HTTP API — thin wrappers around the M1–M4 backend.

Start the server:
    uvicorn api.main:app --reload --port 8000

All secrets load from .env. Only the Alpaca paper account is used;
the live trading URL is never referenced here.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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

def _docs_enabled() -> bool:
    """Docs are on everywhere except when APP_ENV is explicitly "production".

    Render sets APP_ENV=production for the deployed instance; local dev and
    the test suite never set it, so /docs, /redoc, and /openapi.json stay
    reachable there. This mirrors the APP_PASSWORD pattern: the deployed
    environment is the only one that opts into the stricter behavior.
    """
    return os.getenv("APP_ENV", "").lower() != "production"


_DOCS_ENABLED = _docs_enabled()

app = FastAPI(
    title="StockPilot API",
    version="1.0.0",
    docs_url="/docs" if _DOCS_ENABLED else None,
    redoc_url="/redoc" if _DOCS_ENABLED else None,
    openapi_url="/openapi.json" if _DOCS_ENABLED else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
# allow_headers=["*"] covers X-App-Password, and CORSMiddleware answers the
# preflight OPTIONS request itself before any route or dependency runs, so
# require_password below never sees (and never blocks) a preflight request.


# ---------------------------------------------------------------------------
# Password gate — single shared passphrase, not per-user auth
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)

APP_PASSWORD = os.getenv("APP_PASSWORD")

if APP_PASSWORD:
    _log.info("Password gate: ON")
else:
    _log.info("Password gate: OFF (APP_PASSWORD not set)")


def require_password(x_app_password: Optional[str] = Header(None)) -> None:
    """Reject requests that don't carry the shared passphrase.

    Auth is off when APP_PASSWORD is unset: if the env var is missing or
    empty, this dependency allows every request through. That keeps local
    development and the test suite green without anyone having to set the
    variable. The gate only engages in environments where APP_PASSWORD is
    set — in practice, only the deployed Render instance.
    """
    if not APP_PASSWORD:
        return
    if x_app_password != APP_PASSWORD:
        raise HTTPException(401, detail="Invalid or missing passphrase")


# ---------------------------------------------------------------------------
# Rate limiting — caps the Anthropic spend behind /signal and /discover
# ---------------------------------------------------------------------------
#
# SP-47's passphrase gate reduces callers from "anyone on the internet" to
# "anyone holding the shared passphrase," but a shared passphrase is not a
# spend control: one caller looping an endpoint, or a leaked passphrase,
# still has an uncapped meter on Anthropic-backed routes. This is defense in
# depth behind the password gate, not a replacement for it.
#
# In-memory limiting (slowapi's default) is fine for a single Render
# instance: it resets on restart and does not coordinate across instances,
# which is an acceptable tradeoff at this project's scale.

_DEFAULT_SIGNAL_RATE_LIMIT = "10/minute"
_DEFAULT_DISCOVER_RATE_LIMIT = "3/minute"


def _signal_rate_limit() -> str:
    return os.getenv("SIGNAL_RATE_LIMIT", _DEFAULT_SIGNAL_RATE_LIMIT)


def _discover_rate_limit() -> str:
    return os.getenv("DISCOVER_RATE_LIMIT", _DEFAULT_DISCOVER_RATE_LIMIT)


def _client_ip(request: Request) -> str:
    """Resolve the caller's IP to key rate limits on.

    Render terminates TLS and proxies requests to the app, so the raw ASGI
    socket peer is always Render's proxy, never the caller. Render sets
    X-Forwarded-For with the original client IP first in the list, so prefer
    that when present and fall back to the socket peer for local dev, where
    there's no proxy in front.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_client_ip)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
def _handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """429 with the same {"detail": ...} shape every other error response uses."""
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded ({exc.detail}). Please slow down and try again shortly."},
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

@app.get("/signal/{ticker}", dependencies=[Depends(require_password)])
@limiter.limit(_signal_rate_limit)
def route_get_signal(
    request: Request,
    ticker: str,
    days: int = Query(_DEFAULT_DAYS, ge=1, le=365),
):
    """Fetch market data, compute indicators, and return an AI signal.

    Response includes all signal fields plus the indicator summary so the React
    client can render both the verdict and the supporting numbers in one call.
    Rate-limited (SIGNAL_RATE_LIMIT env, default 10/minute) since each call
    spends an Anthropic token budget.
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
        _log.error("GET /signal/%s — network error: %s", ticker, exc)
        raise HTTPException(503, detail="Upstream data provider unavailable")
    except SignalGenerationError as exc:
        _log.error("GET /signal/%s — AI signal generation failed: %s", ticker, exc)
        raise HTTPException(502, detail="AI signal generation failed")


# ---------------------------------------------------------------------------
# GET /signals
# ---------------------------------------------------------------------------

@app.get("/signals", dependencies=[Depends(require_password)])
def route_get_signals():
    """Return every logged signal record (signals_log.json), most recent first."""
    records = list(reversed(load_all_signals()))
    return {"records": records, "total": len(records)}


# ---------------------------------------------------------------------------
# GET /portfolio
# ---------------------------------------------------------------------------

@app.get("/portfolio", dependencies=[Depends(require_password)])
def route_get_portfolio():
    """Return live portfolio state: positions marked to market, totals, account."""
    try:
        return get_portfolio_state()
    except AlpacaAuthError as exc:
        _log.error("GET /portfolio — Alpaca auth error: %s", exc)
        raise HTTPException(503, detail="Portfolio data unavailable")
    except (AlpacaNetworkError, RuntimeError) as exc:
        _log.error("GET /portfolio — error: %s", exc)
        raise HTTPException(503, detail="Portfolio data unavailable")


# ---------------------------------------------------------------------------
# GET /portfolio/{ticker}/recommendation
# ---------------------------------------------------------------------------

@app.get("/portfolio/{ticker}/recommendation", dependencies=[Depends(require_password)])
def route_get_recommendation(ticker: str):
    """Return a HOLD / ADD / SELL recommendation for an open position."""
    try:
        state = get_portfolio_state()
    except AlpacaAuthError as exc:
        _log.error("GET /portfolio/%s/recommendation — Alpaca auth error: %s", ticker, exc)
        raise HTTPException(503, detail="Portfolio data unavailable")
    except (AlpacaNetworkError, RuntimeError) as exc:
        _log.error("GET /portfolio/%s/recommendation — error: %s", ticker, exc)
        raise HTTPException(503, detail="Portfolio data unavailable")

    position = next(
        (p for p in state.get("positions", []) if p["ticker"].upper() == ticker.upper()),
        None,
    )
    if position is None:
        raise HTTPException(404, detail=f"No open position for {ticker.upper()}")

    try:
        return get_recommendation(position)
    except RecommendationError as exc:
        _log.error("GET /portfolio/%s/recommendation — recommendation error: %s", ticker, exc)
        raise HTTPException(502, detail="Recommendation generation failed")
    except (ValueError, ConnectionError) as exc:
        _log.error("GET /portfolio/%s/recommendation — error: %s", ticker, exc)
        raise HTTPException(503, detail="Recommendation data unavailable")


# ---------------------------------------------------------------------------
# GET /discover
# ---------------------------------------------------------------------------

@app.get("/discover", dependencies=[Depends(require_password)])
@limiter.limit(_discover_rate_limit)
def route_discover(request: Request, days: int = _DEFAULT_DAYS):
    """Scan the watchlist and return AI signals for every ticker.

    Each result matches the shape of analysis.discover.scan_ticker — ticker,
    company_name, signal, confidence, price, drift_5d, sparkline, reasoning,
    error. The internal _signal_obj field is stripped before returning.

    Rate-limited more tightly than /signal (DISCOVER_RATE_LIMIT env, default
    3/minute) since one call fans out into an Anthropic call per watchlist
    ticker.
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

@app.get("/watchlist", dependencies=[Depends(require_password)])
def route_get_watchlist():
    """Return the current watchlist."""
    return {"tickers": _load_watchlist()}


@app.post("/watchlist", dependencies=[Depends(require_password)])
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


@app.delete("/watchlist/{ticker}", dependencies=[Depends(require_password)])
def route_remove_watchlist(ticker: str):
    """Remove a ticker from the watchlist. No-op if not present."""
    ticker = ticker.upper()
    tickers = [t for t in _load_watchlist() if t != ticker]
    _save_watchlist(tickers)
    return {"tickers": tickers}


# ---------------------------------------------------------------------------
# POST /orders
# ---------------------------------------------------------------------------

@app.post("/orders", dependencies=[Depends(require_password)])
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