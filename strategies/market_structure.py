"""
Market Structure — detects swing highs/lows, Break of Structure (BOS),
and Change of Character (CHOCH) to determine overall bias.

BOS   = price breaks a previous swing high (bullish) or swing low (bearish)
        → confirms the current trend is continuing
CHOCH = the FIRST BOS against the trend
        → early warning that the trend is reversing
"""

import pandas as pd
from dataclasses import dataclass

SWING_LOOKBACK = 5   # candles on each side needed to confirm a swing point


@dataclass
class SwingPoint:
    index: int
    price: float
    kind:  str    # "high" or "low"


@dataclass
class MarketStructure:
    bias:             str            # "BULLISH" | "BEARISH" | "NEUTRAL"
    last_bos:         str | None     # "BULLISH" | "BEARISH" | None
    choch_detected:   bool
    last_swing_high:  SwingPoint | None
    last_swing_low:   SwingPoint | None


def find_swing_highs(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> list[SwingPoint]:
    points = []
    for i in range(lookback, len(df) - lookback):
        window = df["High"].iloc[i - lookback : i + lookback + 1]
        if df["High"].iloc[i] >= window.max():
            points.append(SwingPoint(i, df["High"].iloc[i], "high"))
    return points


def find_swing_lows(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> list[SwingPoint]:
    points = []
    for i in range(lookback, len(df) - lookback):
        window = df["Low"].iloc[i - lookback : i + lookback + 1]
        if df["Low"].iloc[i] <= window.min():
            points.append(SwingPoint(i, df["Low"].iloc[i], "low"))
    return points


def analyze_structure(df: pd.DataFrame) -> MarketStructure:
    swing_highs = find_swing_highs(df)
    swing_lows  = find_swing_lows(df)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return MarketStructure("NEUTRAL", None, False, None, None)

    sh_prev, sh_last = swing_highs[-2], swing_highs[-1]
    sl_prev, sl_last = swing_lows[-2],  swing_lows[-1]

    current_close = df["Close"].iloc[-1]
    current_high  = df["High"].iloc[-1]
    current_low   = df["Low"].iloc[-1]

    # ── Trend detection (higher highs + higher lows = uptrend) ───
    uptrend   = sh_last.price > sh_prev.price and sl_last.price > sl_prev.price
    downtrend = sh_last.price < sh_prev.price and sl_last.price < sl_prev.price

    last_bos       = None
    choch          = False
    bias           = "NEUTRAL"

    # ── BOS ──────────────────────────────────────────────────────
    if current_close > sh_prev.price:
        last_bos = "BULLISH"
        bias     = "BULLISH"
    elif current_close < sl_prev.price:
        last_bos = "BEARISH"
        bias     = "BEARISH"

    # ── CHOCH ─────────────────────────────────────────────────────
    # Downtrend → price breaks ABOVE last swing high = first bullish BOS → CHOCH
    if downtrend and current_close > sh_last.price:
        choch = True
        bias  = "BULLISH"

    # Uptrend → price breaks BELOW last swing low = first bearish BOS → CHOCH
    if uptrend and current_close < sl_last.price:
        choch = True
        bias  = "BEARISH"

    return MarketStructure(
        bias           = bias,
        last_bos       = last_bos,
        choch_detected = choch,
        last_swing_high= swing_highs[-1],
        last_swing_low = swing_lows[-1],
    )
