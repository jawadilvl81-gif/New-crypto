"""
config.py - Bot Configuration
⚠️  SECURITY WARNING: Never commit real API keys to version control!
    Use environment variables in production.
    Rotate your Bybit keys immediately if shared publicly.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── TELEGRAM ────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8746379336:AAErpaGPOsbK8woEhFvAXFLfabAKZhZUkeM")
ALLOWED_USERS = []  # Leave empty to allow all, or add Telegram user IDs: [123456789]

# ─── BYBIT ───────────────────────────────────────────────────────────────────
BYBIT_API_KEY    = os.getenv("BYBIT_API_KEY",    "ZQfwxbpWIqp1qwg1G1")
BYBIT_API_SECRET = os.getenv("BYBIT_API_SECRET", "XrRYRFNFc7e6lCPMptVJPiHCvBIXUlWxUBfV")
BYBIT_TESTNET    = os.getenv("BYBIT_TESTNET", "false").lower() == "true"  # Set True for testnet

# ─── TRADE DEFAULTS ──────────────────────────────────────────────────────────
DEFAULT_TRADE_USDT   = float(os.getenv("DEFAULT_TRADE_USDT", "20"))
DEFAULT_LEVERAGE     = int(os.getenv("DEFAULT_LEVERAGE", "1"))
DEFAULT_SL_PERCENT   = float(os.getenv("DEFAULT_SL_PERCENT", "2.0"))   # 2%
DEFAULT_TP_PERCENT   = float(os.getenv("DEFAULT_TP_PERCENT", "4.0"))   # 4%
MAX_OPEN_TRADES      = int(os.getenv("MAX_OPEN_TRADES", "10"))
MIN_CONFIDENCE_AUTO  = float(os.getenv("MIN_CONFIDENCE_AUTO", "3.0"))  # out of 7.0
TRADE_CATEGORY       = "linear"   # Bybit: "linear" = USDT perpetual, "spot" = spot

# ─── STRATEGY WEIGHTS ────────────────────────────────────────────────────────
STRATEGY_WEIGHTS = {
    "RSI":               1.0,
    "EMA_Trend":         1.0,
    "MACD":              1.0,
    "Bollinger":         1.0,
    "Volume_Breakout":   0.8,
    "Support_Resistance":0.8,
    "Scalping":          0.7,
    "Ichimoku":          1.2,
    "VWAP":              1.0,
    "ADX":               0.9,
    "Stochastic":        0.9,
    "Parabolic_SAR":     0.9,
    "Sentiment_ML":      1.5,
}

# ─── TIMEFRAMES ──────────────────────────────────────────────────────────────
PRIMARY_TF   = "1h"
SCALP_TF     = "5m"
HIGHER_TF    = ["4h", "1d"]
CANDLE_LIMIT = 200

# ─── AUTO TRADING ─────────────────────────────────────────────────────────────
AUTO_SCAN_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT",
]
AUTO_SCAN_INTERVAL_SECONDS = 60   # scan every 60 seconds

# ─── ALERTS ──────────────────────────────────────────────────────────────────
ALERTS_FILE  = "data/alerts.json"
TRADES_DB    = "data/trades.db"
LOG_FILE     = "logs/bot.log"

# ─── NEWSAPI (optional — get free key at newsapi.org) ────────────────────────
NEWSAPI_KEY  = os.getenv("NEWSAPI_KEY", "")

# ─── CHART ───────────────────────────────────────────────────────────────────
CHART_STYLE  = "binance-dark"  # mplfinance style
CHART_DIR    = "charts/"
