"""Alpaca paper-trading client for StockPilot.

All operations target the paper account only. The live trading URL is never used.
Every connection attempt and order is logged to stdout.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

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

# Notional dollar amounts to invest per trade, keyed by confidence level.
# BULLISH + High     → BUY $500
# BULLISH + Moderate → BUY $200
# BULLISH + Low      → no trade (signal too weak)
# BEARISH + any      → no trade (no short selling on paper account)
# NEUTRAL + any      → no trade
_BUY_NOTIONAL_HIGH = 500.0
_BUY_NOTIONAL_MODERATE = 200.0


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


def decide_order(signal: str, confidence: str) -> tuple:
    """Map (signal, confidence) to (action, notional_dollars).

    Decision rules — only BULLISH signals with sufficient confidence trigger a buy.
    No short selling: BEARISH signals are always skipped on this paper account.

      BULLISH + High     → BUY, $500.00
      BULLISH + Moderate → BUY, $200.00
      BULLISH + Low      → no trade (signal too weak to act on)
      BEARISH + any      → no trade (short selling not supported)
      NEUTRAL + any      → no trade

    Args:
        signal:     One of "BULLISH", "BEARISH", "NEUTRAL".
        confidence: One of "High", "Moderate", "Low".

    Returns:
        (action, notional): action is "BUY" or None; notional is the target
        dollar amount for the trade. Returns (None, 0.0) when no trade is warranted.
    """
    if signal == "BULLISH" and confidence == "High":
        return "BUY", _BUY_NOTIONAL_HIGH
    if signal == "BULLISH" and confidence == "Moderate":
        return "BUY", _BUY_NOTIONAL_MODERATE
    return None, 0.0


def execute_signal(signal_dict: dict, current_price: float) -> Optional[dict]:
    """Translate a get_signal() result into a paper buy order, with buying-power validation.

    Calls decide_order() to determine whether the signal warrants a trade and for
    how much notional value. Checks available buying power before submitting.

    Args:
        signal_dict:   Dict returned by get_signal() — required keys: ticker, signal, confidence.
        current_price: Current market price of the ticker, used to compute share qty.

    Returns:
        Order result dict from place_buy_order(), or None if no trade was placed
        (NEUTRAL/BEARISH signal, Low confidence, or insufficient buying power).

    Raises:
        ValueError:       If signal_dict is missing required keys or current_price is not positive.
        AlpacaAuthError:  If Alpaca credentials are invalid.
        AlpacaOrderError: If Alpaca rejects the order.
    """
    required_keys = {"ticker", "signal", "confidence"}
    missing = required_keys - signal_dict.keys()
    if missing:
        raise ValueError(f"signal_dict missing required keys: {sorted(missing)}")
    if current_price <= 0:
        raise ValueError(f"current_price must be positive, got {current_price}")

    ticker = signal_dict["ticker"]
    action, notional = decide_order(signal_dict["signal"], signal_dict["confidence"])

    if action is None:
        _log.info(
            "No trade: %s  signal=%s  confidence=%s",
            ticker, signal_dict["signal"], signal_dict["confidence"],
        )
        return None

    account = get_account_info()
    if account["buying_power"] < notional:
        _log.warning(
            "Insufficient buying power for %s — need $%.2f, have $%.2f — order skipped",
            ticker, notional, account["buying_power"],
        )
        return None

    qty = round(notional / current_price, 4)
    _log.info(
        "Executing %s %s — notional=$%.2f  price=$%.2f  qty=%.4f",
        action, ticker, notional, current_price, qty,
    )
    return place_buy_order(ticker, qty)


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
    print("Connection successful.\n")

    print("=== Signal → order smoke test ===")
    synthetic_signal = {
        "ticker": "AAPL",
        "signal": "BULLISH",
        "confidence": "High",
        "reasoning": "Smoke test — simulated signal",
        "key_factors": [],
    }
    simulated_price = 210.00
    print(f"  Signal : {synthetic_signal['signal']} / {synthetic_signal['confidence']}")
    print(f"  Ticker : {synthetic_signal['ticker']}  (simulated price ${simulated_price:.2f})")
    order = execute_signal(synthetic_signal, simulated_price)
    if order:
        print(f"  Order placed — id={order['id']}  status={order['status']}")
        print(f"  {order['side']} {order['qty']:.4f} shares of {order['ticker']}")
        positions = get_positions()
        aapl = next((p for p in positions if p["ticker"] == "AAPL"), None)
        if aapl:
            print(f"  AAPL position confirmed — qty={aapl['qty']:.4f}")
        else:
            print("  Order submitted; position may settle shortly.")
    else:
        print("  No order placed (signal filtered or insufficient buying power).")
