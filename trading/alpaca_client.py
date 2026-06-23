"""Alpaca paper-trading client for StockPilot.

All operations target the paper account only. The live trading URL is never used.
Every connection attempt and order is logged to stdout.
"""

import logging
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

load_dotenv()

logging.basicConfig(
    format="%(asctime)s [alpaca] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=logging.INFO,
)
_log = logging.getLogger(__name__)

_PAPER_URL = "https://paper-api.alpaca.markets"


class AlpacaAuthError(Exception):
    """Raised when Alpaca credentials are missing or rejected."""


class AlpacaOrderError(Exception):
    """Raised when an order placement fails."""

    def __init__(self, side: str, ticker: str, message: str) -> None:
        super().__init__(f"[{side} {ticker}] {message}")
        self.side = side
        self.ticker = ticker


def _get_client() -> TradingClient:
    """Build and return an authenticated Alpaca TradingClient (paper account).

    Returns:
        A connected TradingClient pointed at the paper endpoint.

    Raises:
        AlpacaAuthError: If the required environment variables are missing.
    """
    api_key = os.getenv("APCA_API_KEY_ID")
    secret_key = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not secret_key:
        raise AlpacaAuthError(
            "APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in .env"
        )

    _log.info("Connecting to Alpaca paper account at %s", _PAPER_URL)
    return TradingClient(api_key, secret_key, paper=True)


def get_account_info() -> dict:
    """Fetch account summary from the Alpaca paper account.

    Returns:
        Dict with keys: buying_power (float), cash (float), portfolio_value (float).

    Raises:
        AlpacaAuthError: If credentials are missing or rejected by Alpaca.
    """
    try:
        client = _get_client()
        account = client.get_account()
    except AlpacaAuthError:
        raise
    except Exception as exc:
        raise AlpacaAuthError(
            f"Failed to retrieve account info — check your Alpaca paper credentials: {exc}"
        ) from exc

    info = {
        "buying_power": float(account.buying_power),
        "cash": float(account.cash),
        "portfolio_value": float(account.portfolio_value),
    }
    _log.info(
        "Account fetched — buying_power=$%.2f  cash=$%.2f  portfolio_value=$%.2f",
        info["buying_power"],
        info["cash"],
        info["portfolio_value"],
    )
    return info


def place_buy_order(ticker: str, qty: float) -> dict:
    """Submit a paper market buy order for the given ticker and share quantity.

    Args:
        ticker: The stock symbol to buy (e.g. "AAPL").
        qty:    Number of shares (fractional shares supported).

    Returns:
        Dict with keys: id (str), ticker, side, qty, status, submitted_at (ISO str).

    Raises:
        AlpacaAuthError:  If credentials are invalid.
        AlpacaOrderError: If Alpaca rejects the order.
        ValueError:       If qty is not positive.
    """
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")

    _log.info("Placing BUY order: %s x %.4f shares", ticker, qty)
    return _place_order(ticker, qty, OrderSide.BUY)


def place_sell_order(ticker: str, qty: float) -> dict:
    """Submit a paper market sell order for the given ticker and share quantity.

    Args:
        ticker: The stock symbol to sell (e.g. "AAPL").
        qty:    Number of shares (fractional shares supported).

    Returns:
        Dict with keys: id (str), ticker, side, qty, status, submitted_at (ISO str).

    Raises:
        AlpacaAuthError:  If credentials are invalid.
        AlpacaOrderError: If Alpaca rejects the order.
        ValueError:       If qty is not positive.
    """
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")

    _log.info("Placing SELL order: %s x %.4f shares", ticker, qty)
    return _place_order(ticker, qty, OrderSide.SELL)


def _place_order(ticker: str, qty: float, side: OrderSide) -> dict:
    """Internal helper that sends the market order and returns a normalised result dict."""
    side_label = side.value.upper()
    try:
        client = _get_client()
        request = MarketOrderRequest(
            symbol=ticker.upper(),
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        order = client.submit_order(request)
    except AlpacaAuthError:
        raise
    except Exception as exc:
        _log.error("Order FAILED — %s %s: %s", side_label, ticker, exc)
        raise AlpacaOrderError(side_label, ticker, str(exc)) from exc

    result = {
        "id": str(order.id),
        "ticker": ticker.upper(),
        "side": side_label,
        "qty": float(order.qty),
        "status": str(order.status),
        "submitted_at": (
            order.submitted_at.isoformat()
            if order.submitted_at
            else datetime.now(timezone.utc).isoformat()
        ),
    }
    _log.info(
        "Order submitted — id=%s  %s %s x %.4f  status=%s",
        result["id"],
        result["side"],
        result["ticker"],
        result["qty"],
        result["status"],
    )
    return result


def get_positions() -> list[dict]:
    """Return all open positions in the Alpaca paper account.

    Returns:
        List of dicts, each with keys: ticker, qty, market_value, avg_entry_price,
        unrealized_pl, unrealized_plpc. Empty list if no positions are open.

    Raises:
        AlpacaAuthError: If credentials are invalid.
    """
    try:
        client = _get_client()
        positions = client.get_all_positions()
    except AlpacaAuthError:
        raise
    except Exception as exc:
        raise AlpacaAuthError(
            f"Failed to retrieve positions: {exc}"
        ) from exc

    result = [
        {
            "ticker": p.symbol,
            "qty": float(p.qty),
            "market_value": float(p.market_value),
            "avg_entry_price": float(p.avg_entry_price),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
        }
        for p in positions
    ]
    _log.info("Positions fetched — %d open position(s)", len(result))
    return result


if __name__ == "__main__":
    print("=== Alpaca paper account smoke test ===")
    info = get_account_info()
    print(f"  buying_power   : ${info['buying_power']:,.2f}")
    print(f"  cash           : ${info['cash']:,.2f}")
    print(f"  portfolio_value: ${info['portfolio_value']:,.2f}")
    print("Connection successful.")
