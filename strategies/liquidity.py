"""
Liquidity — banks and institutions need large amounts of orders to fill
their positions.  Those orders pile up at obvious places:
  - Above swing highs (buy-stop orders from retail traders)
  - Below swing lows  (sell-stop orders from retail traders)
  - At round numbers  (psychological levels)

Equal Highs (EQH) : multiple candles touching the same high = big pool
                    of buy-stop orders sitting above that level.
Equal Lows (EQL)  : multiple candles touching the same low  = big pool
                    of sell-stop orders sitting below.

Liquidity Sweep   : price spikes through EQH/EQL to collect those orders
                    then IMMEDIATELY reverses.
                    → This is often the true entry trigger in SMC.
                    → We enter AFTER the sweep, not before.
"""

import pandas as pd
from dataclasses import dataclass


@dataclass
class LiquiditySweep:
    kind:  str     # "BULLISH_SWEEP" | "BEARISH_SWEEP"
    level: float   # the level that was swept


def detect_sweep(df: pd.DataFrame,
                 lookback: int = 20) -> LiquiditySweep | None:
    """
    Check if the most recent closed candle swept a liquidity pool and
    closed back on the other side — signalling institutional reversal.
    """
    if len(df) < lookback + 2:
        return None

    # Reference window: candles BEFORE the last two
    window    = df.iloc[-(lookback + 2) : -2]
    last      = df.iloc[-2]   # last fully closed candle
    prev      = df.iloc[-3]

    recent_high = window["High"].max()
    recent_low  = window["Low"].min()

    # ── Bullish sweep (swept LOWS, expect price to go UP) ────
    # Wick went below recent low but candle closed ABOVE it
    if (last["Low"]   < recent_low and
            last["Close"] > recent_low and
            last["Close"] > prev["Close"]):
        return LiquiditySweep("BULLISH_SWEEP", recent_low)

    # ── Bearish sweep (swept HIGHS, expect price to go DOWN) ─
    if (last["High"]  > recent_high and
            last["Close"] < recent_high and
            last["Close"] < prev["Close"]):
        return LiquiditySweep("BEARISH_SWEEP", recent_high)

    return None


def find_equal_highs(df: pd.DataFrame,
                     tolerance_pct: float = 0.03,
                     lookback: int = 50) -> list[float]:
    """Returns price levels where 2+ swing highs touched the same area."""
    highs  = df["High"].iloc[-lookback:].values
    levels = []
    visited = set()

    for i, h in enumerate(highs):
        if i in visited:
            continue
        tol    = h * tolerance_pct / 100
        cluster= [j for j, hh in enumerate(highs) if abs(hh - h) <= tol]
        if len(cluster) >= 2:
            levels.append(float(h))
            visited.update(cluster)

    return levels


def find_equal_lows(df: pd.DataFrame,
                    tolerance_pct: float = 0.03,
                    lookback: int = 50) -> list[float]:
    lows   = df["Low"].iloc[-lookback:].values
    levels = []
    visited = set()

    for i, l in enumerate(lows):
        if i in visited:
            continue
        tol    = l * tolerance_pct / 100
        cluster= [j for j, ll in enumerate(lows) if abs(ll - l) <= tol]
        if len(cluster) >= 2:
            levels.append(float(l))
            visited.update(cluster)

    return levels
