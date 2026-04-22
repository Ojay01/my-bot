"""
Fair Value Gap (FVG) — a 3-candle imbalance where the market moved so
fast that it left a "gap" between candle 1 and candle 3.

Bullish FVG : candle[i-1].high  <  candle[i+1].low
              (gap above candle i-1, price will return to fill it)
              → price pulls back INTO this gap → BUY opportunity

Bearish FVG : candle[i-1].low   >  candle[i+1].high
              (gap below candle i-1)
              → price pulls back INTO this gap → SELL opportunity

"Filled" means price has already returned to close the gap.
We only trade UNFILLED (fresh) FVGs.
"""

import pandas as pd
from dataclasses import dataclass


@dataclass
class FairValueGap:
    kind:   str     # "BULLISH" | "BEARISH"
    top:    float   # upper boundary of the gap
    bottom: float   # lower boundary of the gap
    mid:    float   # midpoint — the 50% fill level
    index:  int     # index of the middle candle
    filled: bool


def find_fvgs(df: pd.DataFrame, max_results: int = 5) -> list[FairValueGap]:
    fvgs   = []
    start  = max(1, len(df) - 150)    # scan last 150 candles

    for i in range(start, len(df) - 1):
        prev_high = df["High"].iloc[i - 1]
        prev_low  = df["Low"].iloc[i - 1]
        next_high = df["High"].iloc[i + 1]
        next_low  = df["Low"].iloc[i + 1]

        # ── Bullish FVG ──────────────────────────────────────
        if prev_high < next_low:
            # Filled if any future low came back down to the gap
            filled = False
            if i + 2 < len(df):
                filled = df["Low"].iloc[i + 2 :].min() <= prev_high

            fvgs.append(FairValueGap(
                kind  = "BULLISH",
                top   = next_low,
                bottom= prev_high,
                mid   = (next_low + prev_high) / 2,
                index = i,
                filled= filled,
            ))

        # ── Bearish FVG ──────────────────────────────────────
        elif prev_low > next_high:
            filled = False
            if i + 2 < len(df):
                filled = df["High"].iloc[i + 2 :].max() >= prev_low

            fvgs.append(FairValueGap(
                kind  = "BEARISH",
                top   = prev_low,
                bottom= next_high,
                mid   = (prev_low + next_high) / 2,
                index = i,
                filled= filled,
            ))

    # Return the most recent unfilled ones
    unfilled = [f for f in fvgs if not f.filled]
    return unfilled[-max_results:]


def price_in_fvg(price: float, fvg: FairValueGap) -> bool:
    return fvg.bottom <= price <= fvg.top


def nearest_unfilled_fvg(price: float, fvgs: list[FairValueGap],
                          kind: str) -> FairValueGap | None:
    matching = [f for f in fvgs if f.kind == kind and not f.filled]
    if not matching:
        return None
    return min(matching, key=lambda f: abs(f.mid - price))
