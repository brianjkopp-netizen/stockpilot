"""Alpaca paper-trading client for StockPilot.

All operations target the paper account only. The live trading URL is never used.
Every connection attempt and order is logged to stdout.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf
from dotenv import load_dotenv
from alpaca.common.exceptions import APIError
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from trading.trade_history import append_trade

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

_client: Optional[TradingClient] = None


class AlpacaAuthError(Exception):
    """Raised when Alpaca credentials are missing or rejected (HTTP 401/403)."""


class AlpacaNetworkError(Exception):
    """Raised when the Alpaca API is unreachable or returns a server error."""


class AlpacaOrderError(Exception):
    """Raised when an order placement fails."""

    def __init__(self, side: str, ticker: str, message: str) -> None:
        super().__init__(f"[{side} {ticker}] {message}")
        self.side = side
        self.ticker = ticker


def _get_client() -> TradingClient:
    """Return the singleton Alpaca TradingClient for the paper account.

    Creates the connection on first call; reuses it on all subsequent calls so
    a single script run opens exactly one connection regardless of how many
    functions are called.

    Returns:
        The shared TradingClient pointed at the paper endpoint.

    Raises:
        AlpacaAuthError: If the required environment variables are missing.
    """
    global _client
    if _client is None:
        api_key = os.getenv("APCA_API_KEY_ID")
        secret_key = os.getenv("APCA_API_SECRET_KEY")

        if not api_key or not secret_key:
            raise AlpacaAuthError(
                "APCA_API_KEY_ID and APCA_API_SECRET_KEY must be set in .env"
            )

        _log.info("Connecting to Alpaca paper account at %s", _PAPER_URL)
        _client = TradingClient(api_key, secret_key, paper=True)

    return _client


def get_account_info() -> dict:
    """Fetch account summary from the Alpaca paper account.

    Returns:
        Dict with keys: buying_power (float), cash (float), portfolio_value (float).

    Raises:
        AlpacaAuthError: If credentials are missing or Alpaca returns HTTP 401/403.
        AlpacaNetworkError: If the API is unreachable or returns a server error.
    """
    try:
        client = _get_client()
        account = client.get_account()
    except AlpacaAuthError:
        raise
    except APIError as exc:
        if exc.status_code in (401, 403):
            raise AlpacaAuthError(
                f"Alpaca credentials rejected (HTTP {exc.status_code}): {exc}"
            ) from exc
        raise AlpacaNetworkError(
            f"Failed to retrieve account info (HTTP {exc.status_code}): {exc}"
        ) from exc
    except Exception as exc:
        raise AlpacaNetworkError(
            f"Failed to reach Alpaca — check your network connection: {exc}"
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


def place_buy_order(
    ticker: str,
    qty: float,
    signal: Optional[str] = None,
    confidence: Optional[str] = None,
    signal_timestamp: Optional[str] = None,
) -> dict:
    """Submit a paper market buy order for the given ticker and share quantity.

    Logs every executed trade to trade_history.json regardless of how this
    function is called — logging cannot be bypassed by going through this
    lower-level function directly.

    Args:
        ticker:           The stock symbol to buy (e.g. "AAPL").
        qty:              Number of shares (fractional shares supported).
        signal:           Signal that triggered the trade, if any.
        confidence:       Signal confidence, if any.
        signal_timestamp: ISO timestamp of the originating signal log entry.

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
    return _place_order(ticker, qty, OrderSide.BUY, signal, confidence, signal_timestamp)


def place_sell_order(
    ticker: str,
    qty: float,
    signal: Optional[str] = None,
    confidence: Optional[str] = None,
    signal_timestamp: Optional[str] = None,
) -> dict:
    """Submit a paper market sell order for the given ticker and share quantity.

    Logs every executed trade to trade_history.json regardless of how this
    function is called — logging cannot be bypassed by going through this
    lower-level function directly.

    Args:
        ticker:           The stock symbol to sell (e.g. "AAPL").
        qty:              Number of shares (fractional shares supported).
        signal:           Signal that triggered the trade, if any.
        confidence:       Signal confidence, if any.
        signal_timestamp: ISO timestamp of the originating signal log entry.

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
    return _place_order(ticker, qty, OrderSide.SELL, signal, confidence, signal_timestamp)


def _place_order(
    ticker: str,
    qty: float,
    side: OrderSide,
    signal: Optional[str] = None,
    confidence: Optional[str] = None,
    signal_timestamp: Optional[str] = None,
) -> dict:
    """Send the market order, read back the fill price, and write a trade log entry.

    Logging happens here — not in the callers — so no code path (execute_signal,
    direct place_buy_order calls, smoke tests) can skip the trade record.
    """
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

    # Read the actual Alpaca fill price. Market orders placed during trading
    # hours fill within seconds; after-hours orders return filled_avg_price=None
    # and get recorded with fill_price=None until a reconciliation pass.
    fill_price: Optional[float] = None
    try:
        fill_status = get_order_status(result["id"])
        fill_price = fill_status.get("filled_avg_price")
    except AlpacaOrderError as exc:
        _log.warning("Could not read fill price for order %s: %s", result["id"], exc)

    append_trade(
        ticker=ticker,
        side=side_label,
        qty=float(order.qty),
        fill_price=fill_price,
        order_id=result["id"],
        signal=signal,
        confidence=confidence,
        signal_timestamp=signal_timestamp,
    )
    return result


def get_order_status(order_id: str) -> dict:
    """Fetch the current fill status of a previously submitted order.

    Market orders typically fill within seconds during trading hours. If the
    order was placed after hours, call this again at the next market open to
    confirm the position landed and buying power dropped.

    Args:
        order_id: The UUID string returned by place_buy_order() or place_sell_order().

    Returns:
        Dict with keys: id, ticker, side, qty, status, filled_qty,
        filled_avg_price (float or None if not yet filled).

    Raises:
        AlpacaAuthError:  If credentials are invalid.
        AlpacaOrderError: If the order ID is not found.
    """
    try:
        client = _get_client()
        order = client.get_order_by_id(order_id)
    except AlpacaAuthError:
        raise
    except Exception as exc:
        raise AlpacaOrderError("GET_STATUS", order_id, str(exc)) from exc

    result = {
        "id": str(order.id),
        "ticker": order.symbol,
        "side": str(order.side).upper(),
        "qty": float(order.qty),
        "status": str(order.status),
        "filled_qty": float(order.filled_qty) if order.filled_qty else 0.0,
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
    }
    _log.info(
        "Order status — id=%s  status=%s  filled_qty=%.4f",
        result["id"], result["status"], result["filled_qty"],
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


def get_latest_price(ticker: str) -> float:
    """Fetch the most recent available close price for a ticker via yfinance.

    Market orders may fill at a slightly different price due to normal
    market-order slippage — the notional dollar amount deployed is therefore
    approximate by design.

    Args:
        ticker: Stock symbol (e.g. "AAPL").

    Returns:
        Most recent close price as a positive float.

    Raises:
        ValueError:     If ticker is invalid or yfinance returns no data.
        ConnectionError: If the price cannot be fetched due to a network error.
    """
    try:
        hist = yf.Ticker(ticker.upper()).history(period="1d")
    except Exception as exc:
        raise ConnectionError(
            f"Failed to fetch price for '{ticker}': {exc}"
        ) from exc

    if hist.empty:
        raise ValueError(
            f"No price data returned for '{ticker}'. The ticker may be invalid."
        )

    price = float(hist["Close"].iloc[-1])
    _log.info("Live price fetched — %s $%.2f", ticker.upper(), price)
    return price


def execute_signal(signal_dict: dict) -> Optional[dict]:
    """Translate a get_signal() result into a paper buy order, with buying-power validation.

    Fetches a live market price for the ticker before computing share quantity,
    so the notional amount deployed matches the configured target ($500 High,
    $200 Moderate). Market orders may fill at a slightly different price due
    to normal slippage — the notional is therefore approximate by design.

    Calls decide_order() to determine whether the signal warrants a trade and for
    how much notional value. Checks available buying power before submitting.

    Args:
        signal_dict: Dict returned by get_signal() — required keys: ticker, signal, confidence.

    Returns:
        Order result dict from place_buy_order(), or None if no trade was placed
        (NEUTRAL/BEARISH signal, Low confidence, or insufficient buying power).

    Raises:
        ValueError:       If signal_dict is missing required keys.
        AlpacaAuthError:  If Alpaca credentials are invalid.
        AlpacaOrderError: If Alpaca rejects the order.
        ConnectionError:  If the live price feed is unreachable.
    """
    required_keys = {"ticker", "signal", "confidence"}
    missing = required_keys - signal_dict.keys()
    if missing:
        raise ValueError(f"signal_dict missing required keys: {sorted(missing)}")

    ticker = signal_dict["ticker"]
    action, notional = decide_order(signal_dict["signal"], signal_dict["confidence"])

    if action is None:
        _log.info(
            "No trade: %s  signal=%s  confidence=%s",
            ticker, signal_dict["signal"], signal_dict["confidence"],
        )
        return None

    current_price = get_latest_price(ticker)

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
    return place_buy_order(
        ticker,
        qty,
        signal=signal_dict["signal"],
        confidence=signal_dict["confidence"],
        signal_timestamp=signal_dict.get("timestamp"),
    )


def get_positions() -> list[dict]:
    """Return all open positions in the Alpaca paper account.

    Returns:
        List of dicts, each with keys: ticker, qty, market_value, avg_entry_price,
        unrealized_pl, unrealized_plpc. Empty list if no positions are open.

    Raises:
        AlpacaAuthError: If credentials are missing or Alpaca returns HTTP 401/403.
        AlpacaNetworkError: If the API is unreachable or returns a server error.
    """
    try:
        client = _get_client()
        positions = client.get_all_positions()
    except AlpacaAuthError:
        raise
    except APIError as exc:
        if exc.status_code in (401, 403):
            raise AlpacaAuthError(
                f"Alpaca credentials rejected (HTTP {exc.status_code}): {exc}"
            ) from exc
        raise AlpacaNetworkError(
            f"Failed to retrieve positions (HTTP {exc.status_code}): {exc}"
        ) from exc
    except Exception as exc:
        raise AlpacaNetworkError(
            f"Failed to reach Alpaca — check your network connection: {exc}"
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
    import sys

    print("=== Alpaca paper account smoke test ===")
    info = get_account_info()
    print(f"  buying_power   : ${info['buying_power']:,.2f}")
    print(f"  cash           : ${info['cash']:,.2f}")
    print(f"  portfolio_value: ${info['portfolio_value']:,.2f}")
    print("Connection successful.")

    if "--live" not in sys.argv:
        print("\nSkipping order placement (pass --live to place a real paper order).")
        sys.exit(0)

    print("\n=== Signal → order smoke test (--live) ===")
    synthetic_signal = {
        "ticker": "AAPL",
        "signal": "BULLISH",
        "confidence": "High",
        "reasoning": "Smoke test — live signal",
        "key_factors": [],
    }
    live_price = get_latest_price(synthetic_signal["ticker"])
    print(f"  Signal : {synthetic_signal['signal']} / {synthetic_signal['confidence']}")
    print(f"  Ticker : {synthetic_signal['ticker']}  (live price ${live_price:.2f})")
    order = execute_signal(synthetic_signal)
    if order:
        print(f"  Order placed — id={order['id']}  status={order['status']}")
        print(f"  {order['side']} {order['qty']:.4f} shares of {order['ticker']}")

        fill = get_order_status(order["id"])
        print(f"  Fill status: {fill['status']}  filled_qty={fill['filled_qty']:.4f}"
              f"  avg_price={fill['filled_avg_price']}")
        if fill["status"] == "filled":
            print("  Position confirmed filled.")
        else:
            print("  NOTE: order not yet filled — re-run get_order_status() at next market open")
            print("        to confirm buying power dropped and position appears in get_positions().")
    else:
        print("  No order placed (signal filtered or insufficient buying power).")
