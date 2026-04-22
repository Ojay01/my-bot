import time
import MetaTrader5 as mt5
import pandas as pd
import config

TIMEFRAME_MAP = {
    "M1":  mt5.TIMEFRAME_M1,
    "M5":  mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1":  mt5.TIMEFRAME_H1,
    "H4":  mt5.TIMEFRAME_H4,
    "D1":  mt5.TIMEFRAME_D1,
}


def connect() -> bool:
    if not mt5.initialize():
        return False
    result = mt5.login(
        login=config.MT5_LOGIN,
        password=config.MT5_PASSWORD,
        server=config.MT5_SERVER,
    )
    return result


def ensure_connected() -> bool:
    info = mt5.terminal_info()
    if info is None or not info.connected:
        for attempt in range(5):
            time.sleep(5 * (attempt + 1))
            if connect():
                return True
        return False
    return True


def get_candles(symbol: str, timeframe_str: str, count: int) -> pd.DataFrame | None:
    tf = TIMEFRAME_MAP.get(timeframe_str)
    if tf is None:
        return None

    if not mt5.symbol_select(symbol, True):
        return None

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                        "close": "Close", "tick_volume": "Volume"}, inplace=True)
    return df


def get_account_info() -> dict | None:
    info = mt5.account_info()
    if info is None:
        return None
    return {
        "balance":  info.balance,
        "equity":   info.equity,
        "margin":   info.margin,
        "free_margin": info.margin_free,
        "profit":   info.profit,
        "currency": info.currency,
    }


def get_open_positions() -> list[dict]:
    positions = mt5.positions_get(magic=config.MAGIC_NUMBER)
    if positions is None:
        return []
    result = []
    for p in positions:
        result.append({
            "ticket":  p.ticket,
            "symbol":  p.symbol,
            "type":    "BUY" if p.type == mt5.ORDER_TYPE_BUY else "SELL",
            "volume":  p.volume,
            "open_price": p.price_open,
            "sl":      p.sl,
            "tp":      p.tp,
            "profit":  p.profit,
            "comment": p.comment,
        })
    return result


def get_symbol_info(symbol: str) -> dict | None:
    mt5.symbol_select(symbol, True)
    info = mt5.symbol_info(symbol)
    if info is None:
        return None
    return {
        "bid":         info.bid,
        "ask":         info.ask,
        "spread":      info.spread,       # in points (integer)
        "point":       info.point,
        "digits":      info.digits,
        "volume_min":  info.volume_min,
        "volume_max":  info.volume_max,
        "volume_step": info.volume_step,
        "trade_tick_value":    info.trade_tick_value,
        "trade_tick_size":     info.trade_tick_size,
        "trade_contract_size": info.trade_contract_size,
    }


def shutdown():
    mt5.shutdown()
