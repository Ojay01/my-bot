"""
Order Blocks (OB) — zones where institutional money placed large orders.

Bullish OB : the last BEARISH (red) candle before price makes a strong
             move UP and breaks structure.  Price tends to return here
             before continuing up — that's where we BUY.

Bearish OB : the last BULLISH (green) candle before price makes a strong
             move DOWN and breaks structure.  Price returns here → SELL.

Extreme OB : an OB that sits at a significant swing high or swing low.
             These are the highest-probability zones because that's where
             the most liquidity was resting.
"""

import pandas as pd
from dataclasses import dataclass
from strategies.market_structure import SwingPoint


@dataclass
class OrderBlock:
    kind:       str     # "BULLISH" | "BEARISH"
    high:       float
    low:        float
    open_:      float
    close_:     float
    index:      int
    is_extreme: bool    # True if at a key swing level
    is_fresh:   bool    # True if price has NOT yet returned to this zone


def _is_near_swing(price: float, swings: list[SwingPoint], pct: float = 0.05) -> bool:
    for s in swings:
        if abs(s.price - price) / price * 100 <= pct:
            return True
    return False


def find_bullish_ob(df: pd.DataFrame,
                    swing_lows: list[SwingPoint]) -> OrderBlock | None:
    """
    Scan recent candles for the last bearish candle that preceded a
    strong bullish expansion.  That candle is the bullish Order Block.
    """
    lookback = min(60, len(df) - 3)

    for i in range(len(df) - 2, len(df) - lookback, -1):
        candle = df.iloc[i]
        is_bearish = candle["Close"] < candle["Open"]
        if not is_bearish:
            continue

        # The next 3 candles must push significantly higher
        future = df.iloc[i + 1 : min(i + 5, len(df))]
        if len(future) == 0:
            continue

        expansion = future["Close"].max() > candle["High"] * 1.0005
        if not expansion:
            continue

        # Has price already returned to (mitigated) this OB?
        after = df.iloc[i + 1 :]
        mitigated = (after["Low"] <= candle["High"]).any()

        is_extreme = _is_near_swing(candle["Low"], swing_lows)

        return OrderBlock(
            kind      = "BULLISH",
            high      = candle["High"],
            low       = candle["Low"],
            open_     = candle["Open"],
            close_    = candle["Close"],
            index     = i,
            is_extreme= is_extreme,
            is_fresh  = not mitigated,
        )

    return None


def find_bearish_ob(df: pd.DataFrame,
                    swing_highs: list[SwingPoint]) -> OrderBlock | None:
    """
    Scan recent candles for the last bullish candle that preceded a
    strong bearish expansion.  That candle is the bearish Order Block.
    """
    lookback = min(60, len(df) - 3)

    for i in range(len(df) - 2, len(df) - lookback, -1):
        candle = df.iloc[i]
        is_bullish = candle["Close"] > candle["Open"]
        if not is_bullish:
            continue

        future = df.iloc[i + 1 : min(i + 5, len(df))]
        if len(future) == 0:
            continue

        expansion = future["Close"].min() < candle["Low"] * 0.9995
        if not expansion:
            continue

        after     = df.iloc[i + 1 :]
        mitigated = (after["High"] >= candle["Low"]).any()

        is_extreme = _is_near_swing(candle["High"], swing_highs)

        return OrderBlock(
            kind      = "BEARISH",
            high      = candle["High"],
            low       = candle["Low"],
            open_     = candle["Open"],
            close_    = candle["Close"],
            index     = i,
            is_extreme= is_extreme,
            is_fresh  = not mitigated,
        )

    return None


def price_in_ob(price: float, ob: OrderBlock) -> bool:
    return ob.low <= price <= ob.high
