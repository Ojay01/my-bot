import pandas as pd
import indicators as ind
import config
from strategies.base_strategy import BaseStrategy, Signal, NONE_SIGNAL


class RsiBollingerStrategy(BaseStrategy):
    name = "RSI_Bollinger"

    def generate_signal(self, df: pd.DataFrame, symbol: str,
                        current_price: float) -> Signal:
        if len(df) < config.BB_PERIOD + 5:
            return NONE_SIGNAL

        close = df["Close"]
        rsi   = ind.rsi(close, config.RSI_PERIOD)
        upper, mid, lower = ind.bollinger_bands(close, config.BB_PERIOD, config.BB_STD)
        atr_v = ind.atr(df["High"], df["Low"], close, config.ATR_PERIOD)

        i, p = -1, -2

        rsi_now     = rsi.iloc[i]
        lower_now   = lower.iloc[i]
        upper_now   = upper.iloc[i]
        mid_now     = mid.iloc[i]
        atr_now     = atr_v.iloc[i]
        close_now   = close.iloc[i]
        close_prev  = close.iloc[p]
        lower_prev  = lower.iloc[p]
        upper_prev  = upper.iloc[p]

        if pd.isna(atr_now) or atr_now == 0:
            return NONE_SIGNAL

        sl_dist = atr_now * config.ATR_SL_MULTIPLIER

        # BUY: RSI oversold + price pierced lower BB then closed back above
        if (rsi_now < config.RSI_OVERSOLD and
                close_prev <= lower_prev and
                close_now > lower_now):
            tp = mid_now
            if (tp - current_price) < sl_dist:          # skip if R:R < 1:1
                return NONE_SIGNAL
            return Signal(
                direction="BUY",
                sl_price=current_price - sl_dist,
                tp_price=tp,
                strength=min((config.RSI_OVERSOLD - rsi_now) / config.RSI_OVERSOLD, 1.0),
                strategy=self.name,
            )

        # SELL: RSI overbought + price pierced upper BB then closed back below
        if (rsi_now > config.RSI_OVERBOUGHT and
                close_prev >= upper_prev and
                close_now < upper_now):
            tp = mid_now
            if (current_price - tp) < sl_dist:
                return NONE_SIGNAL
            return Signal(
                direction="SELL",
                sl_price=current_price + sl_dist,
                tp_price=tp,
                strength=min((rsi_now - config.RSI_OVERBOUGHT) /
                             (100 - config.RSI_OVERBOUGHT), 1.0),
                strategy=self.name,
            )

        return NONE_SIGNAL
