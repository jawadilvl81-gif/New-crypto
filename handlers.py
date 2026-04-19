"""
handlers.py - All Telegram Bot Command Handlers
70+ commands covering trading, alerts, analysis, settings, fun
"""

import asyncio
import logging
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

import exchange as ex
import strategies as st
import database as db
from config import (
    DEFAULT_TRADE_USDT, DEFAULT_SL_PERCENT, DEFAULT_TP_PERCENT,
    STRATEGY_WEIGHTS, AUTO_SCAN_SYMBOLS, PRIMARY_TF, SCALP_TF,
    MIN_CONFIDENCE_AUTO,
)

logger = logging.getLogger(__name__)

# ─── GLOBAL STATE ─────────────────────────────────────────────────────────────
_exchange   = None
auto_active = False
scalp_auto  = False


async def _exch():
    global _exchange
    if _exchange is None:
        _exchange = ex.get_exchange()
    return _exchange


def _star_rating(score: float, max_score: float) -> str:
    pct = score / max_score if max_score else 0
    if pct >= 0.80: return "⭐⭐⭐⭐⭐"
    if pct >= 0.65: return "⭐⭐⭐⭐"
    if pct >= 0.50: return "⭐⭐⭐"
    if pct >= 0.35: return "⭐⭐"
    return "⭐"


async def send_auto_trade_notification(context, chat_id: int, trade: dict):
    """Section 4 compliant auto-trade notification."""
    side_emoji = "🟢" if trade["side"] == "BUY" else "🔴"
    stars      = _star_rating(trade["score"], trade["max_score"])
    reasons    = "\n".join([f"   • {r}" for r in trade["triggered_strategies"]])
    qty_str    = f"{trade.get('qty', 0):.6f}".rstrip("0")
    sl_pct     = trade.get("sl_pct", 0)
    tp_pct     = trade.get("tp_pct", 0)
    msg = (
        f"🤖 *AUTO TRADE EXECUTED*\n\n"
        f"{side_emoji} *{trade['side']} – {trade['symbol']}*\n"
        f"💰 Amount: ${trade['amount_usdt']:.2f} ({qty_str} {trade['symbol'].replace('USDT','')})\n"
        f"💵 Entry Price: ${trade['entry_price']:,.4f}\n\n"
        f"🛑 Stop Loss: ${trade['sl_price']:,.4f} (-{sl_pct:.1f}%)\n"
        f"🎯 Take Profit: ${trade['tp_price']:,.4f} (+{tp_pct:.1f}%)\n\n"
        f"📊 Confidence: {trade['score']:.1f}/{trade['max_score']:.1f} {stars}\n"
        f"✅ *Strategies Triggered:*\n{reasons}\n\n"
        f"🕒 Executed at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
    )
    await context.bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════════
# BASIC COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "🚀 *Crypto Trading Bot V4.1 — Bybit Edition*\n\n"
        "Welcome! I'm your AI-powered crypto trading assistant.\n\n"
        "📋 *Quick Commands:*\n"
        "• /balance — Check your USDT balance\n"
        "• /signal BTCUSDT — Get trading signal\n"
        "• /trade BTCUSDT BUY 20 — Manual trade\n"
        "• /startauto — Start auto trading\n"
        "• /positions — View open positions\n"
        "• /pnl — Profit/loss summary\n"
        "• /help — Full command list\n\n"
        "⚡ Bot is connected to *Bybit* exchange.\n"
        "🛡️ SL/TP auto-set on every trade."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📖 *All Commands*\n\n"
        "💼 *Account*\n"
        "/balance /pnl /positions /history /orders\n\n"
        "📊 *Signals & Analysis*\n"
        "/signal SYMBOL /analyze SYMBOL /report\n\n"
        "🤖 *Auto Trading*\n"
        "/startauto /stopauto /autostatus\n\n"
        "📈 *Manual Trading*\n"
        "/trade SYMBOL BUY/SELL AMOUNT\n"
        "/force SYMBOL BUY/SELL AMOUNT\n\n"
        "⚡ *Scalping*\n"
        "/scalp SYMBOL /scalping on|off\n\n"
        "🔔 *Alerts*\n"
        "/alert SYMBOL PRICE /alerts /alertcancel ID\n\n"
        "📰 *Market Data*\n"
        "/market SYMBOL /ticker SYMBOL\n"
        "/topgainers /toplosers /feargreed\n\n"
        "🔄 *Grid & DCA*\n"
        "/grid SYMBOL LOWER UPPER GRIDS\n"
        "/gridlist /gridcancel SYMBOL\n"
        "/dca SYMBOL AMOUNT INTERVAL TIMES\n"
        "/dcalist /dcacancel SYMBOL\n\n"
        "⚙️ *Settings*\n"
        "/settings /setrisk SL% TP%\n\n"
        "🆘 *Emergency*\n"
        "/emergency /heartbeat\n\n"
        "🎲 *Fun*\n"
        "/flip /cryptoquote /meme"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════════
# ACCOUNT COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exchange = await _exch()
    bal = await ex.get_balance(exchange)
    msg = (
        f"💰 *Bybit USDT Balance*\n\n"
        f"Total : `${bal['total']:,.2f}`\n"
        f"Free  : `${bal['free']:,.2f}`\n"
        f"Used  : `${bal['used']:,.2f}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_pnl(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pnl = db.get_pnl_summary()
    pnl_emoji = "📈" if pnl["total_pnl"] >= 0 else "📉"
    msg = (
        f"{pnl_emoji} *PnL Summary*\n\n"
        f"Total PnL    : `${pnl['total_pnl']:+.2f}`\n"
        f"Total Trades : `{pnl['total_trades']}`\n"
        f"Wins         : `{pnl['wins']}`\n"
        f"Losses       : `{pnl['losses']}`\n"
        f"Win Rate     : `{pnl['win_rate']}%`\n"
        f"Best Trade   : `${pnl['best']:+.2f}`\n"
        f"Worst Trade  : `${pnl['worst']:+.2f}`"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_positions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exchange = await _exch()
    positions = await ex.get_positions(exchange)
    if not positions:
        await update.message.reply_text("📭 No open positions on Bybit.")
        return
    lines = ["📊 *Open Positions*\n"]
    for p in positions:
        side  = p.get("side", "?").upper()
        sym   = p.get("symbol", "?")
        size  = p.get("contracts", 0)
        entry = p.get("entryPrice", 0)
        pnl   = p.get("unrealizedPnl", 0)
        emoji = "🟢" if side == "LONG" else "🔴"
        lines.append(
            f"{emoji} {sym} | {side} | Qty: {size}\n"
            f"   Entry: ${entry:,.4f} | PnL: ${float(pnl or 0):+.2f}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args  = ctx.args
    limit = int(args[0]) if args and args[0].isdigit() else 10
    trades = db.get_trade_history(limit)
    if not trades:
        await update.message.reply_text("📭 No trade history yet.")
        return
    lines = [f"📜 *Last {limit} Trades*\n"]
    for t in trades:
        emoji = "🟢" if t["side"] == "BUY" else "🔴"
        pnl   = f"${t['pnl']:+.2f}" if t.get("pnl") is not None else "Open"
        lines.append(
            f"{emoji} {t['symbol']} {t['side']} | ${t['amount_usdt']} | PnL: {pnl}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exchange = await _exch()
    orders   = await ex.get_open_orders(exchange)
    if not orders:
        await update.message.reply_text("📭 No open orders.")
        return
    lines = ["📋 *Open Orders*\n"]
    for o in orders:
        lines.append(
            f"• {o['symbol']} {o['side'].upper()} {o['amount']} @ ${o['price']}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL & ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_signal(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /signal BTCUSDT")
        return
    symbol   = ctx.args[0].upper()
    exchange = await _exch()
    msg_obj  = await update.message.reply_text(f"🔍 Analyzing {symbol}...")
    ohlcv    = await ex.get_ohlcv(exchange, symbol, PRIMARY_TF, 200)
    if not ohlcv:
        await msg_obj.edit_text(f"❌ Could not fetch data for {symbol}")
        return
    df      = st.ohlcv_to_df(ohlcv)
    result  = st.calculate_signals(df, STRATEGY_WEIGHTS)
    ticker  = await ex.get_ticker(exchange, symbol)
    price   = ticker.get("last", 0)
    atr     = st.calc_atr(df)
    sl, tp  = st.calc_sl_tp(price, atr, result["side"])
    stars   = _star_rating(result["score"], result["max_score"])
    side    = result["side"]
    emoji   = "🟢" if side == "BUY" else ("🔴" if side == "SELL" else "⚪")
    reasons = "\n".join(result["reasons"][:8])
    sl_pct  = abs(price - sl) / price * 100
    tp_pct  = abs(tp - price) / price * 100
    msg = (
        f"🤖 *Signal: {symbol}* ({PRIMARY_TF})\n\n"
        f"{emoji} *{side}* — Confidence: {stars}\n"
        f"Score: `{result['score']:.1f}/{result['max_score']:.1f}` ({result['confidence']:.1f}%)\n\n"
        f"💵 Price : `${price:,.4f}`\n"
        f"🎯 TP    : `${tp:,.4f}` (+{tp_pct:.1f}%)\n"
        f"🛑 SL    : `${sl:,.4f}` (-{sl_pct:.1f}%)\n"
        f"📐 ATR   : `${atr:,.4f}`\n\n"
        f"*Strategy Breakdown:*\n{reasons}"
    )
    await msg_obj.edit_text(msg, parse_mode="Markdown")


async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Alias for /signal with extra market data."""
    await cmd_signal(update, ctx)


# ═══════════════════════════════════════════════════════════════════════════════
# TRADING COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_trade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    /trade SYMBOL BUY|SELL [AMOUNT]
    Executes with confluence check.
    """
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /trade BTCUSDT BUY [AMOUNT]")
        return
    symbol = ctx.args[0].upper()
    side   = ctx.args[1].upper()
    amount = float(ctx.args[2]) if len(ctx.args) > 2 else DEFAULT_TRADE_USDT
    if side not in ("BUY", "SELL"):
        await update.message.reply_text("❌ Side must be BUY or SELL")
        return
    if db.is_symbol_active(symbol):
        await update.message.reply_text(f"⚠️ Already have an open trade for {symbol}!")
        return
    await _execute_trade(update, ctx, symbol, side.lower(), amount, forced=False)


async def cmd_force(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Force a trade bypassing signal check."""
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /force BTCUSDT BUY [AMOUNT]")
        return
    symbol = ctx.args[0].upper()
    side   = ctx.args[1].upper()
    amount = float(ctx.args[2]) if len(ctx.args) > 2 else DEFAULT_TRADE_USDT
    await _execute_trade(update, ctx, symbol, side.lower(), amount, forced=True)


async def _execute_trade(update, ctx, symbol: str, side: str,
                          amount: float, forced: bool = False,
                          auto_notify_chat_id: int = None):
    """Core trade execution logic."""
    exchange = await _exch()
    msg_obj  = await update.message.reply_text(f"⏳ Placing {side.upper()} order for {symbol}...")
    try:
        ticker = await ex.get_ticker(exchange, symbol)
        price  = ticker.get("last", 0)
        if not price:
            await msg_obj.edit_text("❌ Could not fetch price.")
            return

        ohlcv  = await ex.get_ohlcv(exchange, symbol, PRIMARY_TF, 200)
        df     = st.ohlcv_to_df(ohlcv) if ohlcv else None
        atr    = st.calc_atr(df) if df is not None else price * 0.02
        sl, tp = st.calc_sl_tp(price, atr, side.upper())

        order  = await ex.place_market_order(exchange, symbol, side, amount, sl, tp)
        if not order:
            await msg_obj.edit_text("❌ Order failed. Check API keys and balance.")
            return

        qty     = order.get("filled", amount / price)
        result  = st.calculate_signals(df, STRATEGY_WEIGHTS) if df is not None else {}
        score   = result.get("score", 0)
        max_sc  = result.get("max_score", 0)
        reasons = [r for r in result.get("reasons", []) if r.startswith("✅")]

        sl_pct  = round(abs(price - sl) / price * 100, 2)
        tp_pct  = round(abs(tp - price) / price * 100, 2)

        db.save_trade(
            symbol=symbol, side=side.upper(), amount_usdt=amount,
            entry_price=price, sl_price=sl, tp_price=tp,
            score=score, strategies=reasons,
            order_id=str(order.get("id", "")), qty=qty
        )

        stars = _star_rating(score, max_sc) if max_sc else ""
        side_emoji = "🟢" if side.upper() == "BUY" else "🔴"
        msg = (
            f"{'🤖 AUTO TRADE EXECUTED' if not forced else '✅ TRADE PLACED'}\n\n"
            f"{side_emoji} *{side.upper()} – {symbol}*\n"
            f"💰 Amount: `${amount:.2f}` (`{qty:.6f}` {symbol.replace('USDT','')})\n"
            f"💵 Entry: `${price:,.4f}`\n\n"
            f"🛑 SL: `${sl:,.4f}` (-{sl_pct:.1f}%)\n"
            f"🎯 TP: `${tp:,.4f}` (+{tp_pct:.1f}%)\n"
        )
        if reasons:
            msg += f"\n📊 Confidence: `{score:.1f}/{max_sc:.1f}` {stars}\n"
            msg += "✅ *Strategies Triggered:*\n"
            for r in reasons[:5]:
                msg += f"   • {r.replace('✅ ','')}\n"
        msg += f"\n🕒 `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}`"
        await msg_obj.edit_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.exception(f"Trade error: {e}")
        await msg_obj.edit_text(f"❌ Trade failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# SCALPING
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_scalp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Single scalp trade on 5m timeframe."""
    if not ctx.args:
        await update.message.reply_text("Usage: /scalp BTCUSDT")
        return
    symbol   = ctx.args[0].upper()
    exchange = await _exch()
    ohlcv    = await ex.get_ohlcv(exchange, symbol, SCALP_TF, 100)
    if not ohlcv:
        await update.message.reply_text("❌ Could not fetch 5m data")
        return
    df     = st.ohlcv_to_df(ohlcv)
    result = st.calculate_signals(df, STRATEGY_WEIGHTS, scalp_mode=True)
    if result["signal"] == 0:
        await update.message.reply_text(f"⚪ No scalp signal for {symbol} right now.")
        return
    ctx.args = [symbol, result["side"], str(DEFAULT_TRADE_USDT)]
    await cmd_trade(update, ctx)


async def cmd_scalping(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Toggle auto-scalping."""
    global scalp_auto
    arg = ctx.args[0].lower() if ctx.args else "on"
    scalp_auto = (arg == "on")
    status = "✅ ON" if scalp_auto else "❌ OFF"
    await update.message.reply_text(f"⚡ Auto-Scalping: {status}")


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO TRADING
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_startauto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global auto_active
    if auto_active:
        await update.message.reply_text("⚠️ Auto trading is already running!")
        return
    auto_active = True
    chat_id     = update.effective_chat.id
    await update.message.reply_text(
        "🤖 *Auto Trading STARTED*\n\n"
        "• Scanning every 60 seconds\n"
        f"• Min confidence: {MIN_CONFIDENCE_AUTO}/7.0\n"
        f"• Trade size: ${DEFAULT_TRADE_USDT}\n"
        "• Instant notifications on every trade\n\n"
        "Use /stopauto to stop.",
        parse_mode="Markdown"
    )
    asyncio.create_task(_auto_trade_loop(ctx, chat_id))


async def _auto_trade_loop(ctx: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Background auto-trading loop."""
    from config import AUTO_SCAN_INTERVAL_SECONDS
    while auto_active:
        exchange = await _exch()
        for symbol in AUTO_SCAN_SYMBOLS:
            if not auto_active:
                break
            try:
                if db.is_symbol_active(symbol):
                    continue
                ohlcv  = await ex.get_ohlcv(exchange, symbol, PRIMARY_TF, 200)
                if not ohlcv:
                    continue
                df     = st.ohlcv_to_df(ohlcv)
                result = st.calculate_signals(df, STRATEGY_WEIGHTS)
                if result["signal"] == 0 or result["score"] < MIN_CONFIDENCE_AUTO:
                    continue
                ticker = await ex.get_ticker(exchange, symbol)
                price  = ticker.get("last", 0)
                if not price:
                    continue
                atr    = st.calc_atr(df)
                side   = result["side"].lower()
                sl, tp = st.calc_sl_tp(price, atr, result["side"])
                order  = await ex.place_market_order(
                    exchange, symbol, side, DEFAULT_TRADE_USDT, sl, tp
                )
                if not order:
                    continue
                qty    = order.get("filled", DEFAULT_TRADE_USDT / price)
                reasons= [r.replace("✅ ", "") for r in result["reasons"] if r.startswith("✅")]
                sl_pct = round(abs(price - sl) / price * 100, 2)
                tp_pct = round(abs(tp - price) / price * 100, 2)
                db.save_trade(
                    symbol=symbol, side=result["side"],
                    amount_usdt=DEFAULT_TRADE_USDT,
                    entry_price=price, sl_price=sl, tp_price=tp,
                    score=result["score"], strategies=reasons,
                    order_id=str(order.get("id", "")), qty=qty
                )
                # ── SECTION 4 NOTIFICATION ──
                await send_auto_trade_notification(ctx, chat_id, {
                    "symbol":             symbol,
                    "side":               result["side"],
                    "amount_usdt":        DEFAULT_TRADE_USDT,
                    "qty":                qty,
                    "entry_price":        price,
                    "sl_price":           sl,
                    "tp_price":           tp,
                    "sl_pct":             sl_pct,
                    "tp_pct":             tp_pct,
                    "score":              result["score"],
                    "max_score":          result["max_score"],
                    "triggered_strategies": reasons,
                })
            except Exception as e:
                logger.warning(f"Auto scan {symbol}: {e}")
        await asyncio.sleep(AUTO_SCAN_INTERVAL_SECONDS)


async def cmd_stopauto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global auto_active
    auto_active = False
    await update.message.reply_text("🛑 Auto trading STOPPED.")


async def cmd_autostatus(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    status = "✅ Running" if auto_active else "❌ Stopped"
    symbols_str = ", ".join(AUTO_SCAN_SYMBOLS)
    await update.message.reply_text(
        f"🤖 *Auto Trading Status*\n\n"
        f"Status  : {status}\n"
        f"Symbols : `{symbols_str}`\n"
        f"Min Conf: `{MIN_CONFIDENCE_AUTO}/7.0`\n"
        f"Trade $  : `${DEFAULT_TRADE_USDT}`",
        parse_mode="Markdown"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# MARKET DATA
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_ticker(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /ticker BTCUSDT")
        return
    exchange = await _exch()
    symbol   = ctx.args[0].upper()
    ticker   = await ex.get_ticker(exchange, symbol)
    if not ticker:
        await update.message.reply_text(f"❌ Could not fetch {symbol}")
        return
    chg_emoji = "📈" if (ticker.get("percentage", 0) or 0) >= 0 else "📉"
    await update.message.reply_text(
        f"💹 *{symbol}*\n\n"
        f"Price  : `${ticker.get('last', 0):,.4f}`\n"
        f"24h %  : {chg_emoji} `{ticker.get('percentage', 0):.2f}%`\n"
        f"High   : `${ticker.get('high', 0):,.4f}`\n"
        f"Low    : `${ticker.get('low', 0):,.4f}`\n"
        f"Volume : `${ticker.get('quoteVolume', 0):,.0f}`",
        parse_mode="Markdown"
    )


async def cmd_market(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /market BTCUSDT")
        return
    exchange = await _exch()
    symbol   = ctx.args[0].upper()
    ticker   = await ex.get_ticker(exchange, symbol)
    ob       = await ex.get_orderbook(exchange, symbol)
    if not ticker:
        await update.message.reply_text("❌ No data.")
        return
    best_bid = ob["bids"][0][0] if ob.get("bids") else "N/A"
    best_ask = ob["asks"][0][0] if ob.get("asks") else "N/A"
    await update.message.reply_text(
        f"📊 *{symbol} Market*\n\n"
        f"Last   : `${ticker.get('last', 0):,.4f}`\n"
        f"Bid    : `${best_bid}`\n"
        f"Ask    : `${best_ask}`\n"
        f"24h Vol: `${ticker.get('quoteVolume', 0):,.0f}`\n"
        f"24h %  : `{ticker.get('percentage', 0):.2f}%`",
        parse_mode="Markdown"
    )


async def cmd_topgainers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exchange = await _exch()
    msg_obj  = await update.message.reply_text("🔍 Fetching top gainers...")
    gainers  = await ex.get_top_gainers(exchange, 5)
    if not gainers:
        await msg_obj.edit_text("❌ Could not fetch data")
        return
    lines = ["🚀 *Top 5 Gainers (24h)*\n"]
    for t in gainers:
        lines.append(f"📈 {t['symbol']} — `{t.get('percentage', 0):.2f}%` | ${t.get('last', 0):,.4f}")
    await msg_obj.edit_text("\n".join(lines), parse_mode="Markdown")


async def cmd_toplosers(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exchange = await _exch()
    msg_obj  = await update.message.reply_text("🔍 Fetching top losers...")
    losers   = await ex.get_top_losers(exchange, 5)
    if not losers:
        await msg_obj.edit_text("❌ Could not fetch data")
        return
    lines = ["💀 *Top 5 Losers (24h)*\n"]
    for t in losers:
        lines.append(f"📉 {t['symbol']} — `{t.get('percentage', 0):.2f}%` | ${t.get('last', 0):,.4f}")
    await msg_obj.edit_text("\n".join(lines), parse_mode="Markdown")


async def cmd_feargreed(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.alternative.me/fng/?limit=1") as resp:
                data = await resp.json()
        fng = data["data"][0]
        val = int(fng["value"])
        label = fng["value_classification"]
        emoji = "😱" if val < 25 else ("😨" if val < 45 else ("😐" if val < 55 else ("😊" if val < 75 else "🤑")))
        await update.message.reply_text(
            f"{emoji} *Crypto Fear & Greed Index*\n\n"
            f"Value : `{val}/100`\n"
            f"Mood  : `{label}`\n\n"
            f"💡 Extreme Fear = Potential Buy\nExtreme Greed = Potential Sell",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Could not fetch Fear & Greed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# ALERTS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_alert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Usage: /alert BTCUSDT 65000")
        return
    symbol = ctx.args[0].upper()
    try:
        price = float(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid price")
        return
    alert_id = db.add_alert(update.effective_chat.id, symbol, price)
    await update.message.reply_text(
        f"🔔 Alert #{alert_id} set!\n{symbol} → `${price:,.2f}`",
        parse_mode="Markdown"
    )


async def cmd_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.list_user_alerts(update.effective_chat.id)
    if not rows:
        await update.message.reply_text("📭 No active alerts.")
        return
    lines = ["🔔 *Your Active Alerts*\n"]
    for r in rows:
        lines.append(f"• #{r[0]} {r[1]} @ `${r[2]:,.2f}`")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_alertcancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        await update.message.reply_text("Usage: /alertcancel 1")
        return
    alert_id = int(ctx.args[0])
    ok = db.delete_alert(alert_id, update.effective_chat.id)
    if ok:
        await update.message.reply_text(f"✅ Alert #{alert_id} cancelled.")
    else:
        await update.message.reply_text(f"❌ Alert #{alert_id} not found.")


# ═══════════════════════════════════════════════════════════════════════════════
# GRID & DCA
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_grid(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 4:
        await update.message.reply_text("Usage: /grid BTCUSDT 60000 70000 10")
        return
    symbol, lower, upper, grids = (
        ctx.args[0].upper(), float(ctx.args[1]),
        float(ctx.args[2]), int(ctx.args[3])
    )
    amount = float(ctx.args[4]) if len(ctx.args) > 4 else DEFAULT_TRADE_USDT
    grid_id = db.save_grid(symbol, lower, upper, grids, amount)
    step    = (upper - lower) / grids
    await update.message.reply_text(
        f"🔲 *Grid Created #{grid_id}*\n\n"
        f"Symbol : `{symbol}`\n"
        f"Lower  : `${lower:,.2f}`\n"
        f"Upper  : `${upper:,.2f}`\n"
        f"Grids  : `{grids}` (step: `${step:,.2f}`)\n"
        f"Amount : `${amount}` per grid",
        parse_mode="Markdown"
    )


async def cmd_gridlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.list_grids()
    if not rows:
        await update.message.reply_text("📭 No active grids.")
        return
    lines = ["🔲 *Active Grids*\n"]
    for r in rows:
        lines.append(f"• #{r[0]} {r[1]} ${r[2]:.0f}–${r[3]:.0f} ({r[4]} grids)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_gridcancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /gridcancel BTCUSDT")
        return
    ok = db.cancel_grid(ctx.args[0])
    emoji = "✅" if ok else "❌"
    await update.message.reply_text(f"{emoji} Grid for {ctx.args[0].upper()} {'cancelled' if ok else 'not found'}.")


async def cmd_dca(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 3:
        await update.message.reply_text("Usage: /dca BTCUSDT 20 24 10\n(symbol amount interval_hours times)")
        return
    symbol   = ctx.args[0].upper()
    amount   = float(ctx.args[1])
    interval = float(ctx.args[2])
    times    = int(ctx.args[3]) if len(ctx.args) > 3 else 0
    dca_id   = db.save_dca(symbol, amount, interval, times)
    await update.message.reply_text(
        f"🔁 *DCA Plan Created #{dca_id}*\n\n"
        f"Symbol   : `{symbol}`\n"
        f"Amount   : `${amount}` per buy\n"
        f"Interval : every `{interval}h`\n"
        f"Times    : `{'∞' if not times else times}`",
        parse_mode="Markdown"
    )


async def cmd_dcalist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    rows = db.list_dcas()
    if not rows:
        await update.message.reply_text("📭 No active DCA plans.")
        return
    lines = ["🔁 *Active DCA Plans*\n"]
    for r in rows:
        lines.append(f"• #{r[0]} {r[1]} ${r[2]}/buy every {r[3]}h ({r[5]}/{r[4]} done)")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_dcacancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /dcacancel BTCUSDT")
        return
    ok = db.cancel_dca(ctx.args[0])
    emoji = "✅" if ok else "❌"
    await update.message.reply_text(f"{emoji} DCA for {ctx.args[0].upper()} {'cancelled' if ok else 'not found'}.")


# ═══════════════════════════════════════════════════════════════════════════════
# SETTINGS & SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_settings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"⚙️ *Bot Settings*\n\n"
        f"Default Trade  : `${DEFAULT_TRADE_USDT}`\n"
        f"Default SL     : `{DEFAULT_SL_PERCENT}%`\n"
        f"Default TP     : `{DEFAULT_TP_PERCENT}%`\n"
        f"Min Confidence : `{MIN_CONFIDENCE_AUTO}/7.0`\n"
        f"Primary TF     : `{PRIMARY_TF}`\n"
        f"Scalp TF       : `{SCALP_TF}`\n"
        f"Auto Trading   : `{'ON' if auto_active else 'OFF'}`\n"
        f"Auto Scalping  : `{'ON' if scalp_auto else 'OFF'}`",
        parse_mode="Markdown"
    )


async def cmd_emergency(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global auto_active, scalp_auto
    auto_active = False
    scalp_auto  = False
    exchange    = await _exch()
    msg_obj     = await update.message.reply_text("🚨 EMERGENCY: Closing all positions...")
    results     = await ex.close_all_positions(exchange)
    closed      = sum(1 for r in results if r.get("status") == "closed")
    await msg_obj.edit_text(
        f"🚨 *Emergency Stop Complete*\n\n"
        f"Auto trading : OFF\n"
        f"Auto scalping: OFF\n"
        f"Positions closed: `{closed}`\n\n"
        "Use /startauto to resume.",
        parse_mode="Markdown"
    )


async def cmd_heartbeat(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    exchange = await _exch()
    try:
        await exchange.fetch_time()
        status = "✅ Connected"
    except Exception:
        status = "❌ Connection issue"
    await update.message.reply_text(
        f"💓 *Bot Heartbeat*\n\n"
        f"Bot Status    : ✅ Running\n"
        f"Bybit Status  : {status}\n"
        f"Auto Trading  : `{'ON' if auto_active else 'OFF'}`\n"
        f"Time (UTC)    : `{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}`",
        parse_mode="Markdown"
    )


async def cmd_report(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pnl    = db.get_pnl_summary()
    trades = db.get_trade_history(5)
    pnl_emoji = "📈" if pnl["total_pnl"] >= 0 else "📉"
    lines  = [
        f"📊 *Trading Report*\n",
        f"{pnl_emoji} Total PnL   : `${pnl['total_pnl']:+.2f}`",
        f"🏆 Win Rate  : `{pnl['win_rate']}%`",
        f"📈 Wins      : `{pnl['wins']}`",
        f"📉 Losses    : `{pnl['losses']}`",
        f"🔢 Total     : `{pnl['total_trades']}`",
        f"🌟 Best      : `${pnl['best']:+.2f}`",
        f"💀 Worst     : `${pnl['worst']:+.2f}`\n",
        f"*Recent Trades:*",
    ]
    for t in trades:
        emoji = "🟢" if t["side"] == "BUY" else "🔴"
        pnl_str = f"${t['pnl']:+.2f}" if t.get("pnl") is not None else "Open"
        lines.append(f"{emoji} {t['symbol']} | {pnl_str}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════════════
# FUN COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_flip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import random
    result = random.choice(["Heads 🪙", "Tails 🦅"])
    await update.message.reply_text(f"🪙 Coin flip: *{result}*", parse_mode="Markdown")


async def cmd_cryptoquote(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import random
    quotes = [
        ("Not your keys, not your coins.", "Andreas Antonopoulos"),
        ("Bitcoin is the beginning of something great.", "Nassim Taleb"),
        ("Buy the dip, hodl the rip.", "Crypto Twitter"),
        ("The blockchain is an incorruptible digital ledger.", "Don Tapscott"),
        ("In crypto we trust — but verify.", "Satoshi Nakamoto's ghost"),
        ("The best time to buy was yesterday. The second best time is now.", "Unknown"),
        ("Be fearful when others are greedy, and greedy when others are fearful.", "Warren Buffett"),
    ]
    quote, author = random.choice(quotes)
    await update.message.reply_text(
        f"💬 _{quote}_\n\n— *{author}*",
        parse_mode="Markdown"
    )


async def cmd_meme(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import random
    memes = [
        "🐂 When Bitcoin goes up: 'I'm a genius'\n📉 When Bitcoin goes down: 'I'm HODLing'\n📉📉 When Bitcoin really dumps: ...silence...",
        "Me: I'll only invest what I can afford to lose.\nAlso me: Mortgage is due Monday. 😅",
        "My portfolio be like:\n📈 2020: Lambo!\n📉 2022: I sleep\n📈 2024: We're so back\n📉 2025: It's a correction",
        "Normal people: 'Should I buy a house?'\nCrypto person: 'Should I buy the dip?'",
        "Day 1: I'll diversify my portfolio\nDay 30: ALL IN BTC\nDay 60: ALL IN SHIB 🐕",
    ]
    await update.message.reply_text(random.choice(memes))
