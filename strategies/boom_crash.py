"""
Spike Reversal Strategy — for Boom, Crash, and Jump indices.

Boom indices   : only spike UP   → after spike, SELL the reversal
Crash indices  : only spike DOWN → after spike, BUY the reversal
Jump indices   : spike EITHER direction → trade reversal of whichever way it spiked
"""

import pandas as pd
import indicators as ind
import config
from strategies.base_strategy import BaseStrategy, Signal, NONE_SIGNAL

# A REAL Deriv spike is huge — 10-30x the average candle.  Anything smaller
# is just normal volatility and will lose money on reversal trades.
SPIKE_MULTIPLIER = 8.0


class BoomCrashStrategy(BaseStrategy):
    name = "Spike_Reversal"

    def generate_signal(self, df: pd.DataFrame, symbol: str,
                        current_price: float) -> Signal:
        if len(df) < 30:
            return NONE_SIGNAL

        body     = ind.candle_body(df)
        avg_body = ind.avg_candle_body(df, 20)
        atr_v    = ind.atr(df["High"], df["Low"], df["Close"], config.ATR_PERIOD)

        i = -2   # last fully closed candle

        spike_body = body.iloc[i]
        avg        = avg_body.iloc[i]
        atr_now    = atr_v.iloc[-1]

        if pd.isna(avg) or avg == 0 or pd.isna(atr_now) or atr_now == 0:
            return NONE_SIGNAL

        is_spike = spike_body >= avg * SPIKE_MULTIPLIER
        if not is_spike:
            return NONE_SIGNAL

        open_c = df["Open"].iloc[i]
        close_c= df["Close"].iloc[i]
        high_c = df["High"].iloc[i]
        low_c  = df["Low"].iloc[i]

        sl_dist = atr_now * config.ATR_SL_MULTIPLIER
        tp_dist = atr_now * config.ATR_TP_MULTIPLIER
        strength= min(spike_body / (avg * SPIKE_MULTIPLIER * 2), 1.0)

        is_bullish_spike = close_c > open_c
        is_bearish_spike = close_c < open_c

        # ── Boom: only spikes UP → sell the reversal ─────────
        if "Boom" in symbol and is_bullish_spike:
            return Signal(
                direction="SELL",
                sl_price =high_c + sl_dist,
                tp_price =current_price - tp_dist,
                strength =strength,
                strategy =self.name,
            )

        # ── Crash: only spikes DOWN → buy the reversal ───────
        if "Crash" in symbol and is_bearish_spike:
            return Signal(
                direction="BUY",
                sl_price =low_c - sl_dist,
                tp_price =current_price + tp_dist,
                strength =strength,
                strategy =self.name,
            )

        # ── Jump: spikes both ways → trade whichever direction ─
        if "Jump" in symbol:
            if is_bullish_spike:
                return Signal(
                    direction="SELL",
                    sl_price =high_c + sl_dist,
                    tp_price =current_price - tp_dist,
                    strength =strength,
                    strategy =self.name,
                )
            if is_bearish_spike:
                return Signal(
                    direction="BUY",
                    sl_price =low_c - sl_dist,
                    tp_price =current_price + tp_dist,
                    strength =strength,
                    strategy =self.name,
                )

        return NONE_SIGNAL
