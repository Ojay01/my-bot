import pandas as pd
import indicators as ind
import config
from strategies.base_strategy import BaseStrategy, Signal, NONE_SIGNAL


class EmaCrossoverStrategy(BaseStrategy):
    name = "EMA_Crossover"

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

        # Indexes: -1 = latest closed candle, -2 = previous candle
        i, p = -1, -2

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

        if bullish_cross and rsi_now > 50 and current_price > trend_now:
            return Signal(
                direction="BUY",
                sl_price=current_price - sl_dist,
                tp_price=current_price + tp_dist,
                strength=min((rsi_now - 50) / 50, 1.0),
                strategy=self.name,
            )

        if bearish_cross and rsi_now < 50 and current_price < trend_now:
            return Signal(
                direction="SELL",
                sl_price=current_price + sl_dist,
                tp_price=current_price - tp_dist,
                strength=min((50 - rsi_now) / 50, 1.0),
                strategy=self.name,
            )

        return NONE_SIGNAL
