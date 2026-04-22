import numpy as np
import pandas as pd


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(span=period, adjust=False).mean()
    avg_loss = loss.ewm(span=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def bollinger_bands(series: pd.Series, period: int = 20,
                    std_mult: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid   = series.rolling(period).mean()
    sigma = series.rolling(period).std()
    return mid + std_mult * sigma, mid, mid - std_mult * sigma


def atr(high: pd.Series, low: pd.Series, close: pd.Series,
        period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def candle_body(df: pd.DataFrame) -> pd.Series:
    return (df["Close"] - df["Open"]).abs()


def avg_candle_body(df: pd.DataFrame, period: int = 20) -> pd.Series:
    return candle_body(df).rolling(period).mean()
