import pandas as pd
import indicators as ind
import mt5_connector as mt5c
import config
from strategies.base_strategy import BaseStrategy, Signal, NONE_SIGNAL


class EmaCrossoverStrategy(BaseStrategy):
    name = "EMA_Crossover"

    def _higher_tf_trend(self, symbol: str) -> float | None:
        """200-EMA on the higher timeframe (TREND_TF) — the 'zoom out and
        check the big picture' a human does before taking a crossover."""
        df = mt5c.get_candles(symbol, config.TREND_TF, config.EMA_TREND + 10)
        if df is None or len(df) < config.EMA_TREND:
            return None
        return ind.ema(df["Close"], config.EMA_TREND).iloc[-2]

    def generate_signal(self, df: pd.DataFrame, symbol: str,
                        current_price: float) -> Signal:
        if len(df) < config.EMA_TREND + 5:
            return NONE_SIGNAL

        close = df["Close"]
        fast  = ind.ema(close, config.EMA_FAST)
        slow  = ind.ema(close, config.EMA_SLOW)
        trend = ind.ema(close, config.EMA_TREND)
        rsi   = ind.rsi(close, config.RSI_PERIOD)
        atr_v = ind.atr(df["High"], df["Low"], close, config.ATR_PERIOD)

        # Indexes: -1 is the still-forming bar in MT5 data, so the latest
        # CLOSED candle is -2 and the one before it is -3.  Signalling off
        # the forming bar repaints (a cross can appear and vanish mid-candle).
        i, p = -2, -3

        fast_now, fast_prev = fast.iloc[i], fast.iloc[p]
        slow_now, slow_prev = slow.iloc[i], slow.iloc[p]
        trend_now = trend.iloc[i]
        rsi_now   = rsi.iloc[i]
        atr_now   = atr_v.iloc[i]

        if pd.isna(atr_now) or atr_now == 0:
            return NONE_SIGNAL

        # Cross detection
        bullish_cross = (fast_prev <= slow_prev) and (fast_now > slow_now)
        bearish_cross = (fast_prev >= slow_prev) and (fast_now < slow_now)

        sl_dist = atr_now * config.ATR_SL_MULTIPLIER
        tp_dist = atr_now * config.ATR_TP_MULTIPLIER

        if not (bullish_cross or bearish_cross):
            return NONE_SIGNAL

        # Higher-timeframe trend must agree (skip check if data unavailable)
        ht_trend = self._higher_tf_trend(symbol)

        # Strength: RSI margin beyond 50, scaled so RSI ~62 = 0.5 (enough
        # when both classic strategies agree) and RSI ~67+ = 0.7 (solo).
        if bullish_cross and rsi_now > 50 and current_price > trend_now:
            if ht_trend is not None and current_price < ht_trend:
                return NONE_SIGNAL
            return Signal(
                direction="BUY",
                sl_price=current_price - sl_dist,
                tp_price=current_price + tp_dist,
                strength=min((rsi_now - 50) / 25, 1.0),
                strategy=self.name,
            )

        if bearish_cross and rsi_now < 50 and current_price < trend_now:
            if ht_trend is not None and current_price > ht_trend:
                return NONE_SIGNAL
            return Signal(
                direction="SELL",
                sl_price=current_price + sl_dist,
                tp_price=current_price - tp_dist,
                strength=min((50 - rsi_now) / 25, 1.0),
                strategy=self.name,
            )

        return NONE_SIGNAL
