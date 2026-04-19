"""
main.py - Bot Entry Point
Registers all commands and starts the bot.
"""

import asyncio
import logging
import os
from telegram import BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

import database as db
from config import TELEGRAM_TOKEN
from handlers import (
    cmd_start, cmd_help,
    # Account
    cmd_balance, cmd_pnl, cmd_positions, cmd_history, cmd_orders,
    # Signals
    cmd_signal, cmd_analyze, cmd_report,
    # Trading
    cmd_trade, cmd_force,
    # Scalping
    cmd_scalp, cmd_scalping,
    # Auto
    cmd_startauto, cmd_stopauto, cmd_autostatus,
    # Market
    cmd_ticker, cmd_market, cmd_topgainers, cmd_toplosers, cmd_feargreed,
    # Alerts
    cmd_alert, cmd_alerts, cmd_alertcancel,
    # Grid & DCA
    cmd_grid, cmd_gridlist, cmd_gridcancel,
    cmd_dca, cmd_dcalist, cmd_dcacancel,
    # Settings & System
    cmd_settings, cmd_emergency, cmd_heartbeat,
    # Fun
    cmd_flip, cmd_cryptoquote, cmd_meme,
)

# ─── LOGGING SETUP ────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("charts", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


# ─── COMMAND REGISTRY ─────────────────────────────────────────────────────────
COMMANDS = [
    # Basic
    ("start",        cmd_start,        "🚀 Start the bot"),
    ("help",         cmd_help,         "📖 Show all commands"),
    # Account
    ("balance",      cmd_balance,      "💰 Check USDT balance"),
    ("pnl",          cmd_pnl,          "📈 Profit/Loss summary"),
    ("positions",    cmd_positions,    "📊 Open positions"),
    ("history",      cmd_history,      "📜 Trade history"),
    ("orders",       cmd_orders,       "📋 Open orders"),
    ("report",       cmd_report,       "📊 Full trading report"),
    # Signals
    ("signal",       cmd_signal,       "🤖 Get signal: /signal BTCUSDT"),
    ("analyze",      cmd_analyze,      "🔍 Analyze symbol"),
    # Trading
    ("trade",        cmd_trade,        "📈 Trade: /trade BTCUSDT BUY 20"),
    ("force",        cmd_force,        "⚡ Force trade (no signal check)"),
    # Scalping
    ("scalp",        cmd_scalp,        "⚡ Scalp trade: /scalp BTCUSDT"),
    ("scalping",     cmd_scalping,     "⚡ Auto-scalp: /scalping on|off"),
    # Auto trading
    ("startauto",    cmd_startauto,    "🤖 Start auto trading"),
    ("stopauto",     cmd_stopauto,     "🛑 Stop auto trading"),
    ("autostatus",   cmd_autostatus,   "📊 Auto trading status"),
    # Market data
    ("ticker",       cmd_ticker,       "💹 Quick price: /ticker BTCUSDT"),
    ("market",       cmd_market,       "📊 Market data: /market BTCUSDT"),
    ("topgainers",   cmd_topgainers,   "🚀 Top 5 gainers"),
    ("toplosers",    cmd_toplosers,    "💀 Top 5 losers"),
    ("feargreed",    cmd_feargreed,    "😱 Fear & Greed Index"),
    # Alerts
    ("alert",        cmd_alert,        "🔔 Set alert: /alert BTCUSDT 65000"),
    ("alerts",       cmd_alerts,       "🔔 View your alerts"),
    ("alertcancel",  cmd_alertcancel,  "❌ Cancel alert: /alertcancel 1"),
    # Grid
    ("grid",         cmd_grid,         "🔲 Create grid: /grid BTC 60000 70000 10"),
    ("gridlist",     cmd_gridlist,     "🔲 List grids"),
    ("gridcancel",   cmd_gridcancel,   "❌ Cancel grid: /gridcancel BTCUSDT"),
    # DCA
    ("dca",          cmd_dca,          "🔁 DCA plan: /dca BTC 20 24 10"),
    ("dcalist",      cmd_dcalist,      "🔁 List DCA plans"),
    ("dcacancel",    cmd_dcacancel,    "❌ Cancel DCA: /dcacancel BTCUSDT"),
    # Settings & system
    ("settings",     cmd_settings,     "⚙️ View settings"),
    ("emergency",    cmd_emergency,    "🚨 Close all & stop bot"),
    ("heartbeat",    cmd_heartbeat,    "💓 Bot health check"),
    # Fun
    ("flip",         cmd_flip,         "🪙 Flip a coin"),
    ("cryptoquote",  cmd_cryptoquote,  "💬 Crypto quote"),
    ("meme",         cmd_meme,         "😂 Crypto meme"),
]


# ─── ALERT CHECKER BACKGROUND TASK ───────────────────────────────────────────

async def alert_checker(app):
    """Periodically check price alerts and notify users."""
    import exchange as ex
    exchange = ex.get_exchange()
    while True:
        try:
            alerts = db.get_active_alerts()
            for alert in alerts:
                aid, chat_id, symbol, target, direction, triggered, created = alert
                try:
                    ticker = await ex.get_ticker(exchange, symbol)
                    price  = ticker.get("last", 0)
                    if not price:
                        continue
                    hit = False
                    if price >= target:
                        hit = True
                        msg = f"🔔 *Alert Triggered!*\n{symbol} reached `${price:,.4f}` (target: `${target:,.4f}`) 🚀"
                    elif price <= target:
                        hit = True
                        msg = f"🔔 *Alert Triggered!*\n{symbol} dropped to `${price:,.4f}` (target: `${target:,.4f}`) 📉"
                    if hit:
                        db.trigger_alert(aid)
                        await app.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")
                except Exception as e:
                    logger.warning(f"Alert check error for {symbol}: {e}")
        except Exception as e:
            logger.warning(f"Alert checker error: {e}")
        await asyncio.sleep(30)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    logger.info("🚀 Starting Crypto Trading Bot V4.1 — Bybit Edition")

    # Init database
    db.init_db()

    # Build application
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Register all command handlers
    for cmd, handler, _ in COMMANDS:
        app.add_handler(CommandHandler(cmd, handler))

    # Unknown command handler
    async def unknown(update, ctx):
        await update.message.reply_text(
            "❓ Unknown command. Use /help to see all commands."
        )
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Set bot commands menu
    async def post_init(app):
        bot_commands = [
            BotCommand(cmd, desc[:40]) for cmd, _, desc in COMMANDS
        ]
        await app.bot.set_my_commands(bot_commands)
        # Start background alert checker
        asyncio.create_task(alert_checker(app))
        logger.info(f"✅ {len(COMMANDS)} commands registered")
        logger.info("🤖 Bot is running! Press Ctrl+C to stop.")

    app.post_init = post_init

    # Run polling
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
