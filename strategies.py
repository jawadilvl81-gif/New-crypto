"""
strategies.py - 12 Technical Analysis Strategies + Signal Engine
Each strategy returns: +1 (BUY), -1 (SELL), 0 (NEUTRAL)
"""

import pandas as pd
import numpy as np
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


# ─── OHLCV → DATAFRAME ────────────────────────────────────────────────────────

def ohlcv_to_df(ohlcv: list) -> pd.DataFrame:
    """Convert raw CCXT OHLCV list to DataFrame."""
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df


# ─── STRATEGY 1: RSI ──────────────────────────────────────────────────────────

def strategy_rsi(df: pd.DataFrame, period: int = 14,
                 oversold: float = 30, overbought: float = 70) -> Tuple[int, str]:
    try:
        delta = df["close"].diff()
        gain  = delta.clip(lower=0)
        loss  = -delta.clip(upper=0)
        avg_g = gain.ewm(com=period - 1, adjust=False).mean()
        avg_l = loss.ewm(com=period - 1, adjust=False).mean()
        rs    = avg_g / avg_l
        rsi   = 100 - (100 / (1 + rs))
        val   = rsi.iloc[-1]
        if val < oversold:
            return 1, f"RSI Oversold ({val:.1f})"
        if val > overbought:
            return -1, f"RSI Overbought ({val:.1f})"
        return 0, f"RSI Neutral ({val:.1f})"
    except Exception as e:
        logger.warning(f"RSI error: {e}")
        return 0, "RSI Error"


# ─── STRATEGY 2: EMA TREND ────────────────────────────────────────────────────

def strategy_ema_trend(df: pd.DataFrame, period: int = 20) -> Tuple[int, str]:
    try:
        ema   = df["close"].ewm(span=period, adjust=False).mean()
        price = df["close"].iloc[-1]
        ema_v = ema.iloc[-1]
        if price > ema_v:
            return 1, f"EMA Trend: Price > EMA{period}"
        if price < ema_v:
            return -1, f"EMA Trend: Price < EMA{period}"
        return 0, "EMA Trend Neutral"
    except Exception as e:
        logger.warning(f"EMA error: {e}")
        return 0, "EMA Error"


# ─── STRATEGY 3: MACD ─────────────────────────────────────────────────────────

def strategy_macd(df: pd.DataFrame,
                  fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[int, str]:
    try:
        ema_f  = df["close"].ewm(span=fast,   adjust=False).mean()
        ema_s  = df["close"].ewm(span=slow,   adjust=False).mean()
        macd   = ema_f - ema_s
        sig    = macd.ewm(span=signal, adjust=False).mean()
        # Crossover detection
        prev_diff = (macd - sig).iloc[-2]
        curr_diff = (macd - sig).iloc[-1]
        if prev_diff < 0 and curr_diff > 0:
            return 1, "MACD Bullish Crossover"
        if prev_diff > 0 and curr_diff < 0:
            return -1, "MACD Bearish Crossover"
        # Trend following
        if curr_diff > 0:
            return 1, f"MACD Above Signal (+{curr_diff:.4f})"
        return -1, f"MACD Below Signal ({curr_diff:.4f})"
    except Exception as e:
        logger.warning(f"MACD error: {e}")
        return 0, "MACD Error"


# ─── STRATEGY 4: BOLLINGER BANDS ──────────────────────────────────────────────

def strategy_bollinger(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> Tuple[int, str]:
    try:
        sma   = df["close"].rolling(period).mean()
        sigma = df["close"].rolling(period).std()
        upper = sma + std * sigma
        lower = sma - std * sigma
        price = df["close"].iloc[-1]
        if price <= lower.iloc[-1]:
            return 1, f"Bollinger Lower Band Touch ({price:.2f})"
        if price >= upper.iloc[-1]:
            return -1, f"Bollinger Upper Band Touch ({price:.2f})"
        return 0, "Bollinger Bands Neutral"
    except Exception as e:
        logger.warning(f"Bollinger error: {e}")
        return 0, "Bollinger Error"


# ─── STRATEGY 5: VOLUME BREAKOUT ──────────────────────────────────────────────

def strategy_volume_breakout(df: pd.DataFrame, multiplier: float = 1.5) -> Tuple[int, str]:
    try:
        avg_vol = df["volume"].rolling(20).mean()
        curr_vol = df["volume"].iloc[-1]
        curr_close = df["close"].iloc[-1]
        prev_close = df["close"].iloc[-2]
        is_high_vol = curr_vol > multiplier * avg_vol.iloc[-1]
        if is_high_vol and curr_close > prev_close:
            return 1, f"Volume Breakout Bullish ({curr_vol/avg_vol.iloc[-1]:.1f}x avg)"
        if is_high_vol and curr_close < prev_close:
            return -1, f"Volume Breakout Bearish ({curr_vol/avg_vol.iloc[-1]:.1f}x avg)"
        return 0, "Volume Normal"
    except Exception as e:
        logger.warning(f"Volume error: {e}")
        return 0, "Volume Error"


# ─── STRATEGY 6: SUPPORT/RESISTANCE ──────────────────────────────────────────

def strategy_support_resistance(df: pd.DataFrame, lookback: int = 50,
                                  threshold: float = 0.01) -> Tuple[int, str]:
    try:
        recent    = df.tail(lookback)
        swing_low = recent["low"].min()
        swing_high = recent["high"].max()
        price     = df["close"].iloc[-1]
        near_low  = abs(price - swing_low) / swing_low < threshold
        near_high = abs(price - swing_high) / swing_high < threshold
        if near_low:
            return 1, f"Near Support ({swing_low:.2f})"
        if near_high:
            return -1, f"Near Resistance ({swing_high:.2f})"
        return 0, "Between S/R Levels"
    except Exception as e:
        logger.warning(f"S/R error: {e}")
        return 0, "S/R Error"


# ─── STRATEGY 7: SCALPING (5m) ───────────────────────────────────────────────

def strategy_scalping(df: pd.DataFrame) -> Tuple[int, str]:
    try:
        ema9  = df["close"].ewm(span=9,  adjust=False).mean()
        ema21 = df["close"].ewm(span=21, adjust=False).mean()
        delta = df["close"].diff()
        gain  = delta.clip(lower=0)
        loss  = -delta.clip(upper=0)
        avg_g = gain.ewm(com=4, adjust=False).mean()
        avg_l = loss.ewm(com=4, adjust=False).mean()
        rsi5  = 100 - (100 / (1 + avg_g / avg_l))
        avg_vol  = df["volume"].rolling(20).mean()
        curr_vol = df["volume"].iloc[-1]
        high_vol = curr_vol > 1.2 * avg_vol.iloc[-1]
        rsi_v    = rsi5.iloc[-1]
        if ema9.iloc[-1] > ema21.iloc[-1] and 45 <= rsi_v <= 65 and high_vol:
            return 1, f"Scalp BUY (EMA9>EMA21, RSI5={rsi_v:.1f})"
        if ema9.iloc[-1] < ema21.iloc[-1] and 35 <= rsi_v <= 55 and high_vol:
            return -1, f"Scalp SELL (EMA9<EMA21, RSI5={rsi_v:.1f})"
        return 0, "Scalping Neutral"
    except Exception as e:
        logger.warning(f"Scalping error: {e}")
        return 0, "Scalping Error"


# ─── STRATEGY 8: ICHIMOKU CLOUD ──────────────────────────────────────────────

def strategy_ichimoku(df: pd.DataFrame) -> Tuple[int, str]:
    try:
        high = df["high"]
        low  = df["low"]
        close = df["close"]
        # Tenkan-sen (9)
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        # Kijun-sen (26)
        kijun  = (high.rolling(26).max() + low.rolling(26).min()) / 2
        # Senkou Span A
        span_a = ((tenkan + kijun) / 2).shift(26)
        # Senkou Span B
        span_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
        # Chikou Span
        chikou = close.shift(-26)

        price   = close.iloc[-1]
        cloud_top    = max(span_a.iloc[-1], span_b.iloc[-1])
        cloud_bottom = min(span_a.iloc[-1], span_b.iloc[-1])
        tk = tenkan.iloc[-1]
        kj = kijun.iloc[-1]

        bullish = (price > cloud_top) and (tk > kj)
        bearish = (price < cloud_bottom) and (tk < kj)
        if bullish:
            return 1, "Ichimoku Bullish Signal"
        if bearish:
            return -1, "Ichimoku Bearish Signal"
        return 0, "Ichimoku Inside Cloud"
    except Exception as e:
        logger.warning(f"Ichimoku error: {e}")
        return 0, "Ichimoku Error"


# ─── STRATEGY 9: VWAP REVERSION ──────────────────────────────────────────────

def strategy_vwap(df: pd.DataFrame, threshold: float = 0.02) -> Tuple[int, str]:
    try:
        typical = (df["high"] + df["low"] + df["close"]) / 3
        vwap    = (typical * df["volume"]).cumsum() / df["volume"].cumsum()
        price   = df["close"].iloc[-1]
        vwap_v  = vwap.iloc[-1]
        if price < vwap_v * (1 - threshold):
            return 1, f"VWAP Buy (Price={price:.2f} < VWAP={vwap_v:.2f})"
        if price > vwap_v * (1 + threshold):
            return -1, f"VWAP Sell (Price={price:.2f} > VWAP={vwap_v:.2f})"
        return 0, f"VWAP Neutral ({price:.2f} ≈ {vwap_v:.2f})"
    except Exception as e:
        logger.warning(f"VWAP error: {e}")
        return 0, "VWAP Error"


# ─── STRATEGY 10: ADX TREND STRENGTH ─────────────────────────────────────────

def strategy_adx(df: pd.DataFrame, period: int = 14, threshold: float = 25) -> Tuple[int, str]:
    try:
        high  = df["high"]
        low   = df["low"]
        close = df["close"]
        plus_dm  = high.diff().clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs()
        ], axis=1).max(axis=1)
        atr      = tr.ewm(span=period, adjust=False).mean()
        plus_di  = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr)
        dx  = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.ewm(span=period, adjust=False).mean()
        adx_v = adx.iloc[-1]
        pdi   = plus_di.iloc[-1]
        mdi   = minus_di.iloc[-1]
        if adx_v > threshold and pdi > mdi:
            return 1, f"ADX Strong Uptrend (ADX={adx_v:.1f})"
        if adx_v > threshold and mdi > pdi:
            return -1, f"ADX Strong Downtrend (ADX={adx_v:.1f})"
        return 0, f"ADX Weak Trend ({adx_v:.1f})"
    except Exception as e:
        logger.warning(f"ADX error: {e}")
        return 0, "ADX Error"


# ─── STRATEGY 11: STOCHASTIC ──────────────────────────────────────────────────

def strategy_stochastic(df: pd.DataFrame, k_period: int = 14,
                          d_period: int = 3) -> Tuple[int, str]:
    try:
        low_min  = df["low"].rolling(k_period).min()
        high_max = df["high"].rolling(k_period).max()
        k = 100 * (df["close"] - low_min) / (high_max - low_min)
        d = k.rolling(d_period).mean()
        kv, dv = k.iloc[-1], d.iloc[-1]
        if kv < 20 and dv < 20:
            return 1, f"Stochastic Oversold (K={kv:.1f}, D={dv:.1f})"
        if kv > 80 and dv > 80:
            return -1, f"Stochastic Overbought (K={kv:.1f}, D={dv:.1f})"
        return 0, f"Stochastic Neutral (K={kv:.1f}, D={dv:.1f})"
    except Exception as e:
        logger.warning(f"Stochastic error: {e}")
        return 0, "Stochastic Error"


# ─── STRATEGY 12: PARABOLIC SAR ──────────────────────────────────────────────

def strategy_parabolic_sar(df: pd.DataFrame,
                             af_start: float = 0.02, af_max: float = 0.2) -> Tuple[int, str]:
    try:
        high  = df["high"].values
        low   = df["low"].values
        close = df["close"].values
        sar   = np.zeros(len(close))
        ep    = np.zeros(len(close))
        af    = af_start
        bull  = True
        sar[0] = low[0]
        ep[0]  = high[0]
        for i in range(1, len(close)):
            sar[i] = sar[i-1] + af * (ep[i-1] - sar[i-1])
            if bull:
                if low[i] < sar[i]:
                    bull  = False
                    sar[i] = ep[i-1]
                    ep[i]  = low[i]
                    af     = af_start
                else:
                    if high[i] > ep[i-1]:
                        ep[i] = high[i]
                        af    = min(af + af_start, af_max)
                    else:
                        ep[i] = ep[i-1]
            else:
                if high[i] > sar[i]:
                    bull  = True
                    sar[i] = ep[i-1]
                    ep[i]  = high[i]
                    af     = af_start
                else:
                    if low[i] < ep[i-1]:
                        ep[i] = low[i]
                        af    = min(af + af_start, af_max)
                    else:
                        ep[i] = ep[i-1]
        price  = close[-1]
        sar_v  = sar[-1]
        was_below = sar[-2] > close[-2]
        now_above = close[-1] > sar[-1]
        if was_below and now_above:
            return 1, f"Parabolic SAR Bullish Crossover (SAR={sar_v:.2f})"
        if not was_below and not now_above:
            return -1, f"Parabolic SAR Bearish Crossover (SAR={sar_v:.2f})"
        if now_above:
            return 1, f"Parabolic SAR Uptrend (SAR={sar_v:.2f})"
        return -1, f"Parabolic SAR Downtrend (SAR={sar_v:.2f})"
    except Exception as e:
        logger.warning(f"Parabolic SAR error: {e}")
        return 0, "SAR Error"


# ─── MASTER SIGNAL ENGINE ─────────────────────────────────────────────────────

def calculate_signals(df: pd.DataFrame,
                       weights: dict,
                       scalp_mode: bool = False) -> dict:
    """
    Run all strategies and return weighted vote result.

    Returns dict:
    {
      "signal":      1 | -1 | 0,
      "side":        "BUY" | "SELL" | "NEUTRAL",
      "score":       float,
      "max_score":   float,
      "reasons":     [str, ...],
      "confidence":  float (0-100),
    }
    """
    if df is None or len(df) < 60:
        return _neutral("Not enough candle data")

    strategies = [
        ("RSI",               strategy_rsi(df)),
        ("EMA_Trend",         strategy_ema_trend(df)),
        ("MACD",              strategy_macd(df)),
        ("Bollinger",         strategy_bollinger(df)),
        ("Volume_Breakout",   strategy_volume_breakout(df)),
        ("Support_Resistance",strategy_support_resistance(df)),
        ("Scalping",          strategy_scalping(df) if scalp_mode else (0, "Scalping N/A")),
        ("Ichimoku",          strategy_ichimoku(df)),
        ("VWAP",              strategy_vwap(df)),
        ("ADX",               strategy_adx(df)),
        ("Stochastic",        strategy_stochastic(df)),
        ("Parabolic_SAR",     strategy_parabolic_sar(df)),
    ]

    buy_score  = 0.0
    sell_score = 0.0
    max_score  = 0.0
    reasons    = []

    for name, (sig, reason) in strategies:
        w = weights.get(name, 1.0)
        max_score += w
        if sig == 1:
            buy_score += w
            reasons.append(f"✅ {reason}")
        elif sig == -1:
            sell_score += w
            reasons.append(f"🔻 {reason}")
        else:
            reasons.append(f"⚪ {reason}")

    if buy_score > sell_score and buy_score >= 2.0:
        return {
            "signal":    1,
            "side":      "BUY",
            "score":     round(buy_score, 2),
            "max_score": round(max_score, 2),
            "reasons":   reasons,
            "confidence": round((buy_score / max_score) * 100, 1),
        }
    if sell_score > buy_score and sell_score >= 2.0:
        return {
            "signal":    -1,
            "side":      "SELL",
            "score":     round(sell_score, 2),
            "max_score": round(max_score, 2),
            "reasons":   reasons,
            "confidence": round((sell_score / max_score) * 100, 1),
        }
    return {
        "signal":    0,
        "side":      "NEUTRAL",
        "score":     0.0,
        "max_score": round(max_score, 2),
        "reasons":   reasons,
        "confidence": 0.0,
    }


def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate Average True Range."""
    try:
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"]  - df["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        return float(tr.ewm(span=period, adjust=False).mean().iloc[-1])
    except Exception:
        return 0.0


def calc_sl_tp(price: float, atr: float, side: str,
               sl_mult: float = 2.0, tp_mult: float = 3.0) -> Tuple[float, float]:
    """Calculate SL and TP using ATR multiples."""
    if side == "BUY":
        sl = round(price - sl_mult * atr, 4)
        tp = round(price + tp_mult * atr, 4)
    else:
        sl = round(price + sl_mult * atr, 4)
        tp = round(price - tp_mult * atr, 4)
    return sl, tp


def _neutral(reason: str) -> dict:
    return {
        "signal": 0, "side": "NEUTRAL",
        "score": 0.0, "max_score": 0.0,
        "reasons": [reason], "confidence": 0.0,
    }
