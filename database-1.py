"""
database.py - SQLite Trade Tracking, Alerts, PnL
"""

import sqlite3
import json
import os
import logging
from datetime import datetime, timezone
from typing import List, Optional

logger = logging.getLogger(__name__)

DB_PATH    = "data/trades.db"
ALERTS_PATH = "data/alerts.json"


def _conn() -> sqlite3.Connection:
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_PATH)


# ─── INIT ─────────────────────────────────────────────────────────────────────

def init_db():
    """Create tables if not exist."""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT    NOT NULL,
            side        TEXT    NOT NULL,
            amount_usdt REAL    NOT NULL,
            qty         REAL,
            entry_price REAL,
            sl_price    REAL,
            tp_price    REAL,
            sl_pct      REAL,
            tp_pct      REAL,
            score       REAL,
            strategies  TEXT,
            order_id    TEXT,
            status      TEXT    DEFAULT 'open',
            close_price REAL,
            pnl         REAL,
            created_at  TEXT,
            closed_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS price_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id     INTEGER NOT NULL,
            symbol      TEXT    NOT NULL,
            target_price REAL   NOT NULL,
            direction   TEXT    NOT NULL,
            triggered   INTEGER DEFAULT 0,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS grid_orders (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT,
            lower       REAL,
            upper       REAL,
            grids       INTEGER,
            amount_usdt REAL,
            active      INTEGER DEFAULT 1,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS dca_plans (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT,
            amount_usdt REAL,
            interval_h  REAL,
            times_total INTEGER,
            times_done  INTEGER DEFAULT 0,
            active      INTEGER DEFAULT 1,
            created_at  TEXT,
            next_run    TEXT
        );
        """)
    logger.info("✅ Database initialized")


# ─── TRADES ───────────────────────────────────────────────────────────────────

def save_trade(symbol: str, side: str, amount_usdt: float,
               entry_price: float, sl_price: float, tp_price: float,
               score: float, strategies: list, order_id: str = "",
               qty: float = 0.0) -> int:
    """Save a new trade record. Returns trade ID."""
    sl_pct = round(abs(entry_price - sl_price) / entry_price * 100, 2)
    tp_pct = round(abs(tp_price - entry_price) / entry_price * 100, 2)
    now    = _now()
    with _conn() as con:
        cur = con.execute(
            """INSERT INTO trades
               (symbol, side, amount_usdt, qty, entry_price, sl_price, tp_price,
                sl_pct, tp_pct, score, strategies, order_id, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (symbol, side, amount_usdt, qty, entry_price, sl_price, tp_price,
             sl_pct, tp_pct, score, json.dumps(strategies), order_id, "open", now)
        )
        return cur.lastrowid


def close_trade(trade_id: int, close_price: float):
    """Mark a trade as closed and calculate PnL."""
    with _conn() as con:
        row = con.execute(
            "SELECT side, entry_price, amount_usdt FROM trades WHERE id=?",
            (trade_id,)
        ).fetchone()
        if not row:
            return
        side, entry, amount = row
        if side == "BUY":
            pnl = (close_price - entry) / entry * amount
        else:
            pnl = (entry - close_price) / entry * amount
        pnl = round(pnl, 4)
        con.execute(
            "UPDATE trades SET status='closed', close_price=?, pnl=?, closed_at=? WHERE id=?",
            (close_price, pnl, _now(), trade_id)
        )
    logger.info(f"Trade #{trade_id} closed. PnL: ${pnl:+.2f}")


def get_open_trades() -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trades WHERE status='open' ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_trade_history(limit: int = 20) -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_pnl_summary() -> dict:
    with _conn() as con:
        rows = con.execute(
            "SELECT pnl, side FROM trades WHERE status='closed' AND pnl IS NOT NULL"
        ).fetchall()
    if not rows:
        return {"total_pnl": 0.0, "wins": 0, "losses": 0, "win_rate": 0.0,
                "total_trades": 0, "best": 0.0, "worst": 0.0}
    pnls   = [r[0] for r in rows]
    wins   = sum(1 for p in pnls if p > 0)
    losses = sum(1 for p in pnls if p <= 0)
    return {
        "total_pnl":    round(sum(pnls), 2),
        "wins":         wins,
        "losses":       losses,
        "win_rate":     round(wins / len(pnls) * 100, 1) if pnls else 0.0,
        "total_trades": len(pnls),
        "best":         round(max(pnls), 2),
        "worst":        round(min(pnls), 2),
    }


def is_symbol_active(symbol: str) -> bool:
    """Check if there's already an open trade for this symbol."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM trades WHERE symbol=? AND status='open' LIMIT 1",
            (symbol.upper(),)
        ).fetchone()
    return row is not None


# ─── PRICE ALERTS ─────────────────────────────────────────────────────────────

def add_alert(chat_id: int, symbol: str, target_price: float) -> int:
    """Add a price alert. Returns alert ID."""
    with _conn() as con:
        ticker_now = target_price  # direction determined at check time
        cur = con.execute(
            "INSERT INTO price_alerts (chat_id, symbol, target_price, direction, created_at) VALUES (?,?,?,?,?)",
            (chat_id, symbol.upper(), target_price, "auto", _now())
        )
        return cur.lastrowid


def get_active_alerts() -> list:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM price_alerts WHERE triggered=0"
        ).fetchall()
    return rows


def trigger_alert(alert_id: int):
    with _conn() as con:
        con.execute("UPDATE price_alerts SET triggered=1 WHERE id=?", (alert_id,))


def list_user_alerts(chat_id: int) -> list:
    with _conn() as con:
        return con.execute(
            "SELECT id, symbol, target_price, created_at FROM price_alerts WHERE chat_id=? AND triggered=0",
            (chat_id,)
        ).fetchall()


def delete_alert(alert_id: int, chat_id: int) -> bool:
    with _conn() as con:
        cur = con.execute(
            "DELETE FROM price_alerts WHERE id=? AND chat_id=?",
            (alert_id, chat_id)
        )
        return cur.rowcount > 0


# ─── GRID & DCA ──────────────────────────────────────────────────────────────

def save_grid(symbol: str, lower: float, upper: float,
              grids: int, amount_usdt: float) -> int:
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO grid_orders (symbol, lower, upper, grids, amount_usdt, created_at) VALUES (?,?,?,?,?,?)",
            (symbol.upper(), lower, upper, grids, amount_usdt, _now())
        )
        return cur.lastrowid


def list_grids() -> list:
    with _conn() as con:
        return con.execute(
            "SELECT id, symbol, lower, upper, grids, amount_usdt FROM grid_orders WHERE active=1"
        ).fetchall()


def cancel_grid(symbol: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "UPDATE grid_orders SET active=0 WHERE symbol=? AND active=1",
            (symbol.upper(),)
        )
        return cur.rowcount > 0


def save_dca(symbol: str, amount_usdt: float,
             interval_h: float, times_total: int) -> int:
    next_run = _now()
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO dca_plans (symbol, amount_usdt, interval_h, times_total, created_at, next_run) VALUES (?,?,?,?,?,?)",
            (symbol.upper(), amount_usdt, interval_h, times_total, _now(), next_run)
        )
        return cur.lastrowid


def list_dcas() -> list:
    with _conn() as con:
        return con.execute(
            "SELECT id, symbol, amount_usdt, interval_h, times_total, times_done, next_run FROM dca_plans WHERE active=1"
        ).fetchall()


def cancel_dca(symbol: str) -> bool:
    with _conn() as con:
        cur = con.execute(
            "UPDATE dca_plans SET active=0 WHERE symbol=? AND active=1",
            (symbol.upper(),)
        )
        return cur.rowcount > 0


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _row_to_dict(row: tuple) -> dict:
    keys = ["id","symbol","side","amount_usdt","qty","entry_price",
            "sl_price","tp_price","sl_pct","tp_pct","score","strategies",
            "order_id","status","close_price","pnl","created_at","closed_at"]
    return dict(zip(keys, row))
