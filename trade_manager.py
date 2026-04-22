import MetaTrader5 as mt5
import mt5_connector as mt5c
import config


def _round_price(price: float, digits: int) -> float:
    return round(price, digits)


def _filling_mode(symbol: str) -> int:
    """
    Deriv (and brokers generally) require a specific order filling mode.
    We read what the symbol actually supports rather than hardcoding one.
    Failing to match this is the #1 reason orders get rejected silently.
    """
    info = mt5.symbol_info(symbol)
    if info is None:
        return mt5.ORDER_FILLING_IOC

    mode = info.filling_mode
    if mode & 1:   # FOK (Fill or Kill) supported
        return mt5.ORDER_FILLING_FOK
    if mode & 2:   # IOC (Immediate or Cancel) supported
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN   # fallback — partial fills allowed


def open_trade(symbol: str, direction: str, lot: float,
               sl_price: float, tp_price: float) -> dict | None:
    sym = mt5c.get_symbol_info(symbol)
    if not sym:
        return None

    digits     = sym["digits"]
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
    price      = sym["ask"] if direction == "BUY" else sym["bid"]

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       symbol,
        "volume":       lot,
        "type":         order_type,
        "price":        price,
        "sl":           _round_price(sl_price, digits),
        "tp":           _round_price(tp_price, digits),
        "deviation":    20,
        "magic":        config.MAGIC_NUMBER,
        "comment":      config.TRADE_COMMENT,
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(symbol),
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        code = result.retcode if result else "N/A"
        return {"error": True, "retcode": code, "symbol": symbol, "direction": direction}

    return {
        "error":     False,
        "ticket":    result.order,
        "symbol":    symbol,
        "direction": direction,
        "lot":       lot,
        "price":     result.price,
        "sl":        sl_price,
        "tp":        tp_price,
    }


def close_trade(ticket: int) -> bool:
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False

    pos       = positions[0]
    direction = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
    tick      = mt5.symbol_info_tick(pos.symbol)
    if not tick:
        return False
    price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask

    request = {
        "action":       mt5.TRADE_ACTION_DEAL,
        "symbol":       pos.symbol,
        "volume":       pos.volume,
        "type":         direction,
        "position":     ticket,
        "price":        price,
        "deviation":    20,
        "magic":        config.MAGIC_NUMBER,
        "comment":      "close",
        "type_time":    mt5.ORDER_TIME_GTC,
        "type_filling": _filling_mode(pos.symbol),
    }

    result = mt5.order_send(request)
    return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE


def modify_sl(ticket: int, new_sl: float) -> bool:
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False

    pos       = positions[0]
    sym_info  = mt5.symbol_info(pos.symbol)
    if not sym_info:
        return False

    request = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol":   pos.symbol,
        "sl":       round(new_sl, sym_info.digits),
        "tp":       pos.tp,
    }

    result = mt5.order_send(request)
    return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE


def modify_tp(ticket: int, new_tp: float) -> bool:
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        return False

    pos       = positions[0]
    sym_info  = mt5.symbol_info(pos.symbol)
    if not sym_info:
        return False

    request = {
        "action":   mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol":   pos.symbol,
        "sl":       pos.sl,
        "tp":       round(new_tp, sym_info.digits),
    }

    result = mt5.order_send(request)
    return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
