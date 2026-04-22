"""
Fibonacci Retracement — after a strong move, price often pulls back to
specific levels before continuing.  These levels act as magnets.

Key levels traders watch:
  0.382 → shallow retracement (strong trend)
  0.500 → 50% pullback (balanced)
  0.618 → golden ratio — the most respected level
  0.786 → deep retracement (still valid, more aggressive entry)

How we use it:
  - Measure from the last swing LOW to swing HIGH (for a bullish setup)
  - If price pulls back to 0.618 or 0.786 AND we have an OB or FVG there
    → very high probability BUY zone
  - Mirror logic for bearish setups
"""

from dataclasses import dataclass

KEY_LEVELS = [0.382, 0.500, 0.618, 0.786]


@dataclass
class FibLevels:
    swing_high: float
    swing_low:  float
    levels:     dict   # { 0.382: price, 0.5: price, ... }


def calculate(swing_high: float, swing_low: float) -> FibLevels:
    diff   = swing_high - swing_low
    levels = {}
    for lvl in [0.0, 0.236, 0.382, 0.500, 0.618, 0.786, 1.0]:
        levels[lvl] = swing_high - lvl * diff
    return FibLevels(swing_high=swing_high, swing_low=swing_low, levels=levels)


def nearest_key_level(price: float, fib: FibLevels,
                       tolerance_pct: float = 0.15) -> float | None:
    """
    Returns the Fibonacci key level (e.g. 0.618) if price is within
    tolerance of it.  tolerance_pct is a % of the total swing range.
    """
    tolerance = (fib.swing_high - fib.swing_low) * (tolerance_pct / 100)
    best_level = None
    best_dist  = float("inf")

    for lvl in KEY_LEVELS:
        lvl_price = fib.levels[lvl]
        dist = abs(price - lvl_price)
        if dist <= tolerance and dist < best_dist:
            best_dist  = dist
            best_level = lvl

    return best_level
