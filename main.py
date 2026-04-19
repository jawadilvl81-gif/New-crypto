"""
main.py - Bot Entry Point
Compatible with python-telegram-bot v21+
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
    cmd_balance, cmd_pnl, cmd_positions, cmd_history, cmd_orders,
    cmd_signal, cmd_analyze, cmd_report,
    cmd_trade, cmd_force,
    cmd_scalp, cmd_scalping,
    cmd_startauto, cmd_stopauto, cmd_autostatus,
    cmd_ticker, cmd_market, cmd_topgainers, cmd_toplosers, cmd_feargreed,
    cmd_alert, cmd_alerts, cmd_alertcancel,
    cmd_grid, cmd_gridlist, cmd_gridcancel,
    cmd_dca, cmd_dcalist, cmd_dcacancel,
    cmd_settings, cmd_emergency, cmd_heartbeat,
    cmd_flip, cmd_cryptoquote, cmd_meme,
)

# ─── LOGGING ──────────────────────────────────────────────────────────────────
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

# ─── COMMANDS ─────────────────────────────────────────────────────────────────
COMMANDS = [
    ("start",       cmd_start,       "Start the bot"),
    ("help",        cmd_help,        "Show all commands"),
    ("balance",     cmd_balance,     "Check USDT balance"),
    ("pnl",         cmd_pnl,         "Profit/Loss summary"),
    ("positions",   cmd_positions,   "Open positions"),
    ("history",     cmd_history,     "Trade history"),
    ("orders",      cmd_orders,      "Open orders"),
    ("report",      cmd_report,      "Full trading report"),
    ("signal",      cmd_signal,      "Get signal: /signal BTCUSDT"),
    ("analyze",     cmd_analyze,     "Analyze symbol"),
    ("trade",       cmd_trade,       "Trade: /trade BTCUSDT BUY 20"),
    ("force",       cmd_force,       "Force trade (no signal check)"),
    ("scalp",       cmd_scalp,       "Scalp trade: /scalp BTCUSDT"),
    ("scalping",    cmd_scalping,    "Auto-scalp: /scalping on|off"),
    ("startauto",   cmd_startauto,   "Start auto trading"),
    ("stopauto",    cmd_stopauto,    "Stop auto trading"),
    ("autostatus",  cmd_autostatus,  "Auto trading status"),
    ("ticker",      cmd_ticker,      "Quick price: /ticker BTCUSDT"),
    ("market",      cmd_market,      "Market data: /market BTCUSDT"),
    ("topgainers",  cmd_topgainers,  "Top 5 gainers"),
    ("toplosers",   cmd_toplosers,   "Top 5 losers"),
    ("feargreed",   cmd_feargreed,   "Fear and Greed Index"),
    ("alert",       cmd_alert,       "Set alert: /alert BTCUSDT 65000"),
    ("alerts",      cmd_alerts,      "View your alerts"),
    ("alertcancel", cmd_alertcancel, "Cancel alert: /alertcancel 1"),
    ("grid",        cmd_grid,        "Create grid: /grid BTC 60000 70000 10"),
    ("gridlist",    cmd_gridlist,    "List grids"),
    ("gridcancel",  cmd_gridcancel,  "Cancel grid: /gridcancel BTCUSDT"),
    ("dca",         cmd_dca,         "DCA plan: /dca BTC 20 24 10"),
    ("dcalist",     cmd_dcalist,     "List DCA plans"),
    ("dcacancel",   cmd_dcacancel,   "Cancel DCA: /dcacancel BTCUSDT"),
    ("settings",    cmd_settings,    "View settings"),
    ("emergency",   cmd_emergency,   "Close all and stop bot"),
    ("heartbeat",   cmd_heartbeat,   "Bot health check"),
    ("flip",        cmd_flip,        "Flip a coin"),
    ("cryptoquote", cmd_cryptoquote, "Crypto quote"),
    ("meme",        cmd_meme,        "Crypto meme"),
]


# ─── ALERT CHECKER ────────────────────────────────────────────────────────────
async def alert_checker(app):
    """Background task: check price alerts every 30 seconds."""
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
                    if price >= target or price <= target:
                        db.trigger_alert(aid)
                        emoji = "🚀" if price >= target else "📉"
                        msg = (
                            f"🔔 *Alert Triggered!*\n"
                            f"{symbol} is now `${price:,.4f}`\n"
                            f"Your target: `${target:,.4f}` {emoji}"
                        )
                        await app.bot.send_message(
                            chat_id=chat_id, text=msg, parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.warning(f"Alert check {symbol}: {e}")
        except Exception as e:
            logger.warning(f"Alert checker: {e}")
        await asyncio.sleep(30)


# ─── POST INIT ────────────────────────────────────────────────────────────────
async def post_init(app):
    """Runs after bot starts — set commands menu & start background tasks."""
    bot_commands = [BotCommand(cmd, desc[:40]) for cmd, _, desc in COMMANDS]
    await app.bot.set_my_commands(bot_commands)

    # Start alert checker as background task
    app.create_task(alert_checker(app))

    logger.info(f"✅ {len(COMMANDS)} commands registered")
    logger.info("🤖 Bot is live!")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("🚀 Starting Crypto Trading Bot V4.1 — Bybit Edition")
    db.init_db()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Register commands
    for cmd, handler, _ in COMMANDS:
        app.add_handler(CommandHandler(cmd, handler))

    # Unknown command fallback
    async def unknown(update, ctx):
        await update.message.reply_text("❓ Unknown command. Use /help")
    app.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("⏳ Starting polling...")
    app.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
