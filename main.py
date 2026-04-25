"""
Trading Bot — main entry point
Run:  python main.py
Stop: Ctrl+C
Web UI: http://localhost:4000
"""

import os
import time
import sys
from datetime import datetime, timezone
from threading import Thread

import config
import logger
import database as db
import mt5_connector as mt5c
import trade_manager as tm
import session_filter as sf
from risk_manager   import RiskManager
from signal_engine  import SignalEngine
from trade_monitor  import TradeMonitor


# ── Sync trade updates with the SQLite database ──────────────

def _sync_trade_state(previously_open: set[int]) -> set[int]:
    """
    Detect newly opened and newly closed trades, write events to DB.
    Returns the new set of currently open tickets.
    """
    import MetaTrader5 as mt5
    positions     = mt5c.get_open_positions()
    current_tickets = {p["ticket"] for p in positions}

    # Newly closed trades
    for ticket in (previously_open - current_tickets):
        deals = mt5.history_deals_get(ticket=ticket)
        if not deals:
            continue
        # Last deal is the close
        last = deals[-1]
        profit = sum(d.profit for d in deals) + sum(d.swap for d in deals) + sum(d.commission for d in deals)

        # Classify close type from comment or SL/TP hit
        status = "closed"
        reason = last.comment or ""
        if "tp" in reason.lower() or "take profit" in reason.lower():
            status = "closed_tp"
        elif "sl" in reason.lower() or "stop loss" in reason.lower():
            status = "closed_sl"

        db.log_trade_close(ticket, last.price, profit, status, reason)

    # Keep SL/TP updates in DB
    for p in positions:
        db.update_trade_sl_tp(p["ticket"], sl=p["sl"], tp=p["tp"])

    return current_tickets


def manage_open_trades(monitor: TradeMonitor):
    positions = mt5c.get_open_positions()
    live_tickets = {p["ticket"] for p in positions}
    monitor.cleanup_closed_trades(live_tickets)

    for pos in positions:
        monitor.manage(pos)


def _start_web_ui():
    if not getattr(config, "WEB_UI_ENABLED", True):
        return
    try:
        from web_app import run_web
        Thread(
            target=run_web,
            kwargs={"port": config.WEB_UI_PORT},
            daemon=True,
            name="web-ui",
        ).start()
        logger.info(f"  Web UI     : http://localhost:{config.WEB_UI_PORT}")
    except Exception as e:
        logger.error(f"Web UI failed to start: {e}")


def run():
    # Ensure DB exists even before anything else
    db.init_db()

    logger.info("=" * 60)
    logger.info("  TRADING BOT STARTING")
    logger.info(f"  Symbols    : {len(config.ACTIVE_SYMBOLS)}")
    logger.info(f"  Risk/trade : {config.RISK_PERCENT}%")
    logger.info(f"  Max trades : {config.MAX_OPEN_TRADES}")
    logger.info(f"  Target     : ${config.PROFIT_TARGET_USD}")
    logger.info(f"  Early exit : {config.EARLY_EXIT_ENABLED}")
    logger.info(f"  TP extend  : {config.TP_EXTENSION_ENABLED}")
    _start_web_ui()
    logger.info("=" * 60)

    logger.info("Connecting to MT5 ...")
    if not mt5c.connect():
        logger.error("Failed to connect to MT5. Check credentials in config.py")
        sys.exit(1)

    acc = mt5c.get_account_info()
    if acc:
        logger.info(
            f"Connected  |  Account: {config.MT5_LOGIN}  "
            f"Balance: ${acc['balance']:.2f}  Currency: {acc['currency']}"
        )

    risk    = RiskManager()
    engine  = SignalEngine()
    monitor = TradeMonitor()

    previously_open: set[int] = {p["ticket"] for p in mt5c.get_open_positions()}
    cycle = 0

    while True:
        try:
            # Web UI asked for a restart?
            if db.consume_restart_flag():
                logger.warning("Settings changed in Web UI — restarting bot ...")
                mt5c.shutdown()
                time.sleep(2)
                os._exit(0)   # start.bat will auto-restart

            if not mt5c.ensure_connected():
                logger.error("Lost MT5 connection — retrying ...")
                time.sleep(30)
                continue

            cycle += 1
            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            logger.info(f"\n{'─'*60}\n  Cycle {cycle}  |  {now}")

            acc = mt5c.get_account_info()
            if acc:
                logger.account_snapshot(
                    acc["balance"], acc["equity"],
                    acc["profit"], config.PROFIT_TARGET_USD
                )
                if acc["balance"] >= config.PROFIT_TARGET_USD:
                    logger.target_reached(acc["balance"])

            # Sync trade events to DB
            previously_open = _sync_trade_state(previously_open)

            if risk.is_hard_floor_hit():
                balance = acc["balance"] if acc else 0
                logger.hard_floor_hit(balance, config.HARD_STOP_BALANCE)
                manage_open_trades(monitor)
                time.sleep(config.SCAN_INTERVAL_SECONDS)
                continue

            if risk.is_daily_limit_hit():
                logger.daily_limit_hit()
                manage_open_trades(monitor)
                time.sleep(config.SCAN_INTERVAL_SECONDS)
                continue

            logger.info(f"  {sf.current_session_info()}")

            risk.update_closed_trades()
            manage_open_trades(monitor)

            for symbol in config.ACTIVE_SYMBOLS:
                try:
                    allowed, reason = sf.can_trade_symbol(symbol)
                    if not allowed:
                        logger.scan_skipped(symbol, reason)
                        db.log_signal(symbol, "NONE", 0, "-", "skipped", reason)
                        continue

                    if getattr(config, "SYMBOL_COOLDOWN_MINUTES", 0) > 0 and risk.is_in_cooldown(symbol):
                        mins_left = risk.cooldown_remaining(symbol)
                        reason = f"cooling down for {mins_left} more min"
                        logger.scan_skipped(symbol, reason)
                        db.log_signal(symbol, "NONE", 0, "-", "skipped", reason)
                        continue

                    is_forex_or_metal = (symbol in config.FOREX_SYMBOLS or
                                         symbol in config.METAL_SYMBOLS)
                    if is_forex_or_metal and not risk.can_trade_forex_balance():
                        reason = f"need ${config.FOREX_MIN_BALANCE}+ balance (synthetics only)"
                        logger.scan_skipped(symbol, reason)
                        db.log_signal(symbol, "NONE", 0, "-", "skipped", reason)
                        continue

                    signal = engine.get_signal(symbol)

                    if signal.direction == "NONE":
                        logger.scan_no_signal(symbol)
                        continue

                    logger.scan_signal_found(
                        symbol, signal.direction,
                        signal.strength, signal.strategy
                    )

                    positions = mt5c.get_open_positions()
                    if len(positions) >= config.MAX_OPEN_TRADES:
                        reason = f"already have {config.MAX_OPEN_TRADES} trades open (overall max)"
                        logger.scan_skipped(symbol, reason)
                        db.log_signal(symbol, signal.direction, signal.strength,
                                       signal.strategy, "skipped", reason)
                        continue

                    on_this_pair = sum(1 for p in positions if p["symbol"] == symbol)
                    if on_this_pair >= config.MAX_TRADES_PER_SYMBOL:
                        reason = (f"already have {on_this_pair} trade(s) on this pair "
                                  f"(max per pair = {config.MAX_TRADES_PER_SYMBOL})")
                        logger.scan_skipped(symbol, reason)
                        db.log_signal(symbol, signal.direction, signal.strength,
                                       signal.strategy, "skipped", reason)
                        continue

                    sl_dist = abs(signal.sl_price - (
                        mt5c.get_symbol_info(symbol)["ask"]
                        if signal.direction == "BUY"
                        else mt5c.get_symbol_info(symbol)["bid"]
                    ))

                    lot = risk.calculate_lot(symbol, sl_dist)
                    if lot == 0.0:
                        reason = "minimum lot size too risky for current balance"
                        logger.scan_skipped(symbol, reason)
                        db.log_signal(symbol, signal.direction, signal.strength,
                                       signal.strategy, "skipped", reason)
                        continue

                    result = tm.open_trade(
                        symbol     = symbol,
                        direction  = signal.direction,
                        lot        = lot,
                        sl_price   = signal.sl_price,
                        tp_price   = signal.tp_price,
                    )

                    if result and not result["error"]:
                        logger.trade_opened(
                            ticket   = result["ticket"],
                            symbol   = symbol,
                            direction= signal.direction,
                            lot      = lot,
                            price    = result["price"],
                            sl       = signal.sl_price,
                            tp       = signal.tp_price,
                            strategy = signal.strategy,
                        )
                        monitor.record_new_trade(result["ticket"], signal.sl_price)
                        db.log_trade_open(
                            result["ticket"], symbol, signal.direction, lot,
                            result["price"], signal.sl_price, signal.tp_price,
                            signal.strategy,
                        )
                        db.log_signal(symbol, signal.direction, signal.strength,
                                       signal.strategy, "taken",
                                       f"opened ticket {result['ticket']}")
                        previously_open.add(result["ticket"])
                    else:
                        code = result["retcode"] if result else "N/A"
                        logger.error(
                            f"  Could not place trade on {symbol} — "
                            f"broker rejected with error code {code}"
                        )
                        db.log_signal(symbol, signal.direction, signal.strength,
                                       signal.strategy, "skipped",
                                       f"broker rejected (error {code})")

                except Exception as e:
                    logger.error(f"  Problem while checking {symbol}: {e}")

            # Trim old signals from DB to keep it small
            if cycle % 50 == 0:
                db.trim_signals(2000)

            logger.info(f"  Next scan in {config.SCAN_INTERVAL_SECONDS}s ...")
            time.sleep(config.SCAN_INTERVAL_SECONDS)

        except KeyboardInterrupt:
            logger.info("\nBot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(10)

    mt5c.shutdown()
    logger.info("MT5 disconnected. Goodbye.")


if __name__ == "__main__":
    run()
