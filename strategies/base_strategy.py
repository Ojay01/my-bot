from dataclasses import dataclass
import pandas as pd


@dataclass
class Signal:
    direction: str      # "BUY" | "SELL" | "NONE"
    sl_price:  float
    tp_price:  float
    strength:  float    # 0.0 – 1.0  (higher = more confident)
    strategy:  str      # name of strategy that generated this signal


NONE_SIGNAL = Signal("NONE", 0.0, 0.0, 0.0, "none")


class BaseStrategy:
    name: str = "base"

    def generate_signal(self, df: pd.DataFrame, symbol: str,
                        current_price: float) -> Signal:
        raise NotImplementedError
