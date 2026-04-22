"""
SMC Strategy — Smart Money Concepts

Full multi-timeframe decision engine:

  H4  →  Determine market bias using BOS / CHOCH
  H1  →  Find Order Blocks, Fair Value Gaps, Fibonacci zones
  M15 →  Confirm entry with Liquidity Sweep + RSI

Entry is only taken when:
  1. H4 bias is clear (not NEUTRAL)
  2. Price is inside an Order Block OR Fair Value Gap on H1
  3. At least one extra confluence exists:
       • Fibonacci 0.618 / 0.786 level nearby
       • Liquidity sweep on M15
       • CHOCH on H4 (trend reversal signal)
  4. Risk-to-Reward is at least 1.5 : 1

Stop Loss  : just beyond the Order Block boundary (structure-based)
Take Profit: next significant swing high/low on H1
"""

import pandas as pd
import mt5_connector as mt5c
import indicators    as ind
import config

from strategies.base_strategy    import BaseStrategy, Signal, NONE_SIGNAL
from strategies.market_structure import (analyze_structure, find_swing_highs,
                                         find_swing_lows)
from strategies.order_blocks     import (find_bullish_ob, find_bearish_ob,
                                         price_in_ob)
from strategies.fair_value_gap   import find_fvgs, price_in_fvg
from strategies.fibonacci        import calculate as calc_fib, nearest_key_level
from strategies.liquidity        import detect_sweep


MIN_RR = 1.5   # minimum risk-to-reward ratio


class SmcStrategy(BaseStrategy):
    name = "SMC"

    def generate_signal(self, df_m15: pd.DataFrame, symbol: str,
                        current_price: float) -> Signal:

        # ── Fetch higher timeframe data ───────────────────────
        df_h4 = mt5c.get_candles(symbol, "H4", 120)
        df_h1 = mt5c.get_candles(symbol, "H1", 200)

        if df_h4 is None or len(df_h4) < 30:
            return NONE_SIGNAL
        if df_h1 is None or len(df_h1) < 60:
            return NONE_SIGNAL

        # ── Step 1: H4 bias ───────────────────────────────────
        structure = analyze_structure(df_h4)
        bias      = structure.bias

        if bias == "NEUTRAL":
            return NONE_SIGNAL

        # ── Step 2: H1 swing points ───────────────────────────
        sh_h1 = find_swing_highs(df_h1)
        sl_h1 = find_swing_lows(df_h1)

        # ── Step 3: Order Blocks on H1 ────────────────────────
        if bias == "BULLISH":
            ob = find_bullish_ob(df_h1, sl_h1)
        else:
            ob = find_bearish_ob(df_h1, sh_h1)

        # ── Step 4: Fair Value Gaps on H1 ─────────────────────
        fvgs    = find_fvgs(df_h1)
        fvg_dir = "BULLISH" if bias == "BULLISH" else "BEARISH"
        active_fvgs = [f for f in fvgs if f.kind == fvg_dir and not f.filled]

        in_ob  = ob is not None and price_in_ob(current_price, ob)
        in_fvg = any(price_in_fvg(current_price, f) for f in active_fvgs)

        # Price must be in at least one zone to consider entry
        if not in_ob and not in_fvg:
            return NONE_SIGNAL

        # ── Step 5: Fibonacci confluence on H1 ───────────────
        fib_level = None
        if len(sh_h1) >= 1 and len(sl_h1) >= 1:
            last_sh = sh_h1[-1]
            last_sl = sl_h1[-1]
            fib = calc_fib(last_sh.price, last_sl.price)
            fib_level = nearest_key_level(current_price, fib)

        # ── Step 6: Liquidity sweep on M15 ───────────────────
        sweep = detect_sweep(df_m15)
        sweep_confirms = (
            (sweep is not None and sweep.kind == "BULLISH_SWEEP" and bias == "BULLISH") or
            (sweep is not None and sweep.kind == "BEARISH_SWEEP" and bias == "BEARISH")
        )

        # ── Step 7: RSI confirmation on M15 ──────────────────
        rsi_vals = ind.rsi(df_m15["Close"], config.RSI_PERIOD)
        rsi_now  = rsi_vals.iloc[-1]
        if pd.isna(rsi_now):
            return NONE_SIGNAL

        rsi_ok = (bias == "BULLISH" and rsi_now < 60) or \
                 (bias == "BEARISH" and rsi_now > 40)

        # ── Step 8: Confluence score ──────────────────────────
        score = 0.0
        score += 1.0 if in_ob                            else 0.0
        score += 0.8 if in_fvg                           else 0.0
        score += 0.7 if ob and ob.is_extreme             else 0.0
        score += 0.6 if fib_level in (0.618, 0.786)      else \
                 0.3 if fib_level in (0.382, 0.500)       else 0.0
        score += 0.6 if sweep_confirms                   else 0.0
        score += 0.4 if structure.choch_detected         else 0.0
        score += 0.2 if rsi_ok                           else 0.0

        # Require strong confluence — Order Block or FVG alone is not enough
        if score < config.MIN_SMC_CONFLUENCE_SCORE:
            return NONE_SIGNAL

        strength = min(score / 3.8, 1.0)

        # ── Step 9: SL and TP calculation ─────────────────────
        atr_vals = ind.atr(df_m15["High"], df_m15["Low"],
                           df_m15["Close"], config.ATR_PERIOD)
        atr_now  = atr_vals.iloc[-1]

        if pd.isna(atr_now) or atr_now == 0:
            return NONE_SIGNAL

        if bias == "BULLISH":
            # SL: just below the OB low (structure-based), fall back to ATR
            if ob:
                sl_price = ob.low - atr_now * 0.3
            else:
                sl_price = current_price - atr_now * config.ATR_SL_MULTIPLIER

            # TP: next swing high on H1
            future_highs = [s for s in sh_h1 if s.price > current_price]
            if future_highs:
                tp_price = min(future_highs, key=lambda s: s.price).price
            else:
                tp_price = current_price + atr_now * config.ATR_TP_MULTIPLIER

        else:  # BEARISH
            if ob:
                sl_price = ob.high + atr_now * 0.3
            else:
                sl_price = current_price + atr_now * config.ATR_SL_MULTIPLIER

            future_lows = [s for s in sl_h1 if s.price < current_price]
            if future_lows:
                tp_price = max(future_lows, key=lambda s: s.price).price
            else:
                tp_price = current_price - atr_now * config.ATR_TP_MULTIPLIER

        # ── Step 10: Risk-to-Reward check ─────────────────────
        sl_dist = abs(current_price - sl_price)
        tp_dist = abs(current_price - tp_price)

        if sl_dist == 0 or (tp_dist / sl_dist) < MIN_RR:
            return NONE_SIGNAL

        return Signal(
            direction = "BUY" if bias == "BULLISH" else "SELL",
            sl_price  = sl_price,
            tp_price  = tp_price,
            strength  = strength,
            strategy  = self.name,
        )
