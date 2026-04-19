"""
exchange.py - Bybit Exchange Interface via CCXT
Handles all order placement, balance, position queries.
"""

import ccxt.async_support as ccxt
import asyncio
import logging
from config import (
    BYBIT_API_KEY, BYBIT_API_SECRET, BYBIT_TESTNET,
    DEFAULT_LEVERAGE, TRADE_CATEGORY
)

logger = logging.getLogger(__name__)


def get_exchange() -> ccxt.bybit:
    """Create and return authenticated Bybit exchange instance."""
    exchange = ccxt.bybit({
        "apiKey":  BYBIT_API_KEY,
        "secret":  BYBIT_API_SECRET,
        "options": {
            "defaultType": "linear",   # USDT perpetual futures
            "adjustForTimeDifference": True,
        },
        "enableRateLimit": True,
    })
    if BYBIT_TESTNET:
        exchange.set_sandbox_mode(True)
        logger.info("🧪 Bybit TESTNET mode enabled")
    return exchange


# ─── BALANCE ──────────────────────────────────────────────────────────────────

async def get_balance(exchange: ccxt.bybit) -> dict:
    """Return USDT balance details."""
    try:
        bal = await exchange.fetch_balance({"type": "linear"})
        usdt = bal.get("USDT", {})
        return {
            "total":  usdt.get("total",  0.0),
            "free":   usdt.get("free",   0.0),
            "used":   usdt.get("used",   0.0),
        }
    except Exception as e:
        logger.error(f"get_balance error: {e}")
        return {"total": 0.0, "free": 0.0, "used": 0.0}


# ─── MARKET DATA ──────────────────────────────────────────────────────────────

async def get_ticker(exchange: ccxt.bybit, symbol: str) -> dict:
    """Fetch current ticker data for a symbol."""
    try:
        symbol = _fmt(symbol)
        ticker = await exchange.fetch_ticker(symbol)
        return ticker
    except Exception as e:
        logger.error(f"get_ticker({symbol}) error: {e}")
        return {}


async def get_ohlcv(exchange: ccxt.bybit, symbol: str,
                    timeframe: str = "1h", limit: int = 200) -> list:
    """Fetch OHLCV candles."""
    try:
        symbol = _fmt(symbol)
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        return ohlcv
    except Exception as e:
        logger.error(f"get_ohlcv({symbol},{timeframe}) error: {e}")
        return []


async def get_orderbook(exchange: ccxt.bybit, symbol: str) -> dict:
    """Fetch order book (top 20 levels)."""
    try:
        symbol = _fmt(symbol)
        ob = await exchange.fetch_order_book(symbol, limit=20)
        return ob
    except Exception as e:
        logger.error(f"get_orderbook({symbol}) error: {e}")
        return {}


async def get_top_gainers(exchange: ccxt.bybit, top_n: int = 5) -> list:
    """Return top N gainers by 24h % change."""
    try:
        tickers = await exchange.fetch_tickers()
        usdt_pairs = [
            t for sym, t in tickers.items()
            if sym.endswith("/USDT") and t.get("percentage") is not None
        ]
        usdt_pairs.sort(key=lambda x: x["percentage"], reverse=True)
        return usdt_pairs[:top_n]
    except Exception as e:
        logger.error(f"get_top_gainers error: {e}")
        return []


async def get_top_losers(exchange: ccxt.bybit, top_n: int = 5) -> list:
    """Return top N losers by 24h % change."""
    try:
        tickers = await exchange.fetch_tickers()
        usdt_pairs = [
            t for sym, t in tickers.items()
            if sym.endswith("/USDT") and t.get("percentage") is not None
        ]
        usdt_pairs.sort(key=lambda x: x["percentage"])
        return usdt_pairs[:top_n]
    except Exception as e:
        logger.error(f"get_top_losers error: {e}")
        return []


# ─── POSITIONS ────────────────────────────────────────────────────────────────

async def get_positions(exchange: ccxt.bybit) -> list:
    """Return all open positions."""
    try:
        positions = await exchange.fetch_positions()
        open_pos = [p for p in positions if float(p.get("contracts", 0) or 0) != 0]
        return open_pos
    except Exception as e:
        logger.error(f"get_positions error: {e}")
        return []


async def get_open_orders(exchange: ccxt.bybit, symbol: str = None) -> list:
    """Return open orders, optionally filtered by symbol."""
    try:
        if symbol:
            orders = await exchange.fetch_open_orders(_fmt(symbol))
        else:
            orders = await exchange.fetch_open_orders()
        return orders
    except Exception as e:
        logger.error(f"get_open_orders error: {e}")
        return []


# ─── ORDER EXECUTION ──────────────────────────────────────────────────────────

async def set_leverage(exchange: ccxt.bybit, symbol: str, leverage: int) -> bool:
    """Set leverage for a symbol."""
    try:
        await exchange.set_leverage(leverage, _fmt(symbol))
        return True
    except Exception as e:
        logger.warning(f"set_leverage({symbol},{leverage}): {e}")
        return False


async def place_market_order(
    exchange: ccxt.bybit,
    symbol: str,
    side: str,          # "buy" or "sell"
    usdt_amount: float,
    sl_price: float = None,
    tp_price: float = None,
) -> dict:
    """
    Place a market order on Bybit with optional SL/TP.
    Returns order dict on success, empty dict on failure.
    """
    try:
        symbol = _fmt(symbol)
        await set_leverage(exchange, symbol, DEFAULT_LEVERAGE)

        # Calculate quantity from USDT amount
        ticker = await get_ticker(exchange, symbol)
        price  = ticker.get("last", 0)
        if not price:
            raise ValueError("Could not fetch current price")

        qty = round(usdt_amount / price, 6)

        params = {}
        if sl_price:
            params["stopLoss"] = str(sl_price)
        if tp_price:
            params["takeProfit"] = str(tp_price)

        order = await exchange.create_market_order(symbol, side, qty, params=params)
        logger.info(f"✅ Order placed: {side.upper()} {qty} {symbol} @ ~{price}")
        return order
    except Exception as e:
        logger.error(f"place_market_order({symbol},{side}) error: {e}")
        return {}


async def place_limit_order(
    exchange: ccxt.bybit,
    symbol: str,
    side: str,
    usdt_amount: float,
    limit_price: float,
    sl_price: float = None,
    tp_price: float = None,
) -> dict:
    """Place a limit order."""
    try:
        symbol = _fmt(symbol)
        qty    = round(usdt_amount / limit_price, 6)
        params = {}
        if sl_price:
            params["stopLoss"] = str(sl_price)
        if tp_price:
            params["takeProfit"] = str(tp_price)
        order = await exchange.create_limit_order(symbol, side, qty, limit_price, params=params)
        return order
    except Exception as e:
        logger.error(f"place_limit_order error: {e}")
        return {}


async def cancel_all_orders(exchange: ccxt.bybit, symbol: str = None) -> bool:
    """Cancel all open orders, optionally for a specific symbol."""
    try:
        if symbol:
            await exchange.cancel_all_orders(_fmt(symbol))
        else:
            for sym in AUTO_SCAN_SYMBOLS_FMT:
                try:
                    await exchange.cancel_all_orders(sym)
                except Exception:
                    pass
        return True
    except Exception as e:
        logger.error(f"cancel_all_orders error: {e}")
        return False


async def close_all_positions(exchange: ccxt.bybit) -> list:
    """Close all open positions (emergency)."""
    results = []
    try:
        positions = await get_positions(exchange)
        for pos in positions:
            symbol = pos["symbol"]
            side   = "sell" if pos["side"] == "long" else "buy"
            qty    = abs(float(pos.get("contracts", 0) or 0))
            try:
                order = await exchange.create_market_order(
                    symbol, side, qty,
                    params={"reduceOnly": True}
                )
                results.append({"symbol": symbol, "status": "closed", "order": order})
                logger.info(f"🔴 Emergency closed: {symbol}")
            except Exception as e:
                results.append({"symbol": symbol, "status": "error", "error": str(e)})
    except Exception as e:
        logger.error(f"close_all_positions error: {e}")
    return results


# ─── TRADE HISTORY ────────────────────────────────────────────────────────────

async def get_trade_history(exchange: ccxt.bybit, limit: int = 20) -> list:
    """Fetch recent closed trades."""
    try:
        trades = await exchange.fetch_my_trades(limit=limit)
        return trades
    except Exception as e:
        logger.error(f"get_trade_history error: {e}")
        return []


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _fmt(symbol: str) -> str:
    """Normalize symbol format: BTCUSDT → BTC/USDT."""
    symbol = symbol.upper().replace("-", "")
    if "/" not in symbol and symbol.endswith("USDT"):
        symbol = symbol[:-4] + "/USDT"
    return symbol


# Import here to avoid circular; used in cancel_all
try:
    from config import AUTO_SCAN_SYMBOLS
    AUTO_SCAN_SYMBOLS_FMT = [_fmt(s) for s in AUTO_SCAN_SYMBOLS]
except ImportError:
    AUTO_SCAN_SYMBOLS_FMT = []
