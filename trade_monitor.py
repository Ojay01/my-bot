"""
Trade Monitor — intelligent management of open positions.

On every bot cycle, for every open trade, this module:

  1. EARLY EXIT
     If M15 structure breaks against the position (e.g. a BUY trade and
     price makes a fresh 20-candle low that's above our SL), close the
     trade early.  Saves money on losers that aren't going to recover.

  2. BREAKEVEN at 1R profit
     Moves SL to the entry price.  No more winners turning into losers.

  3. TRAILING STOP at 2R+ profit
     Keeps SL 1R behind the current price, locking in progressively more
     profit as the trade runs.

  4. TP EXTENSION
     When 80%+ of the way to TP AND momentum is still strong (rising RSI
     for BUY, falling RSI for SELL), adds another 1R to TP.  Don't leave
     money on the table when a move has legs.  Only extends once per trade.
"""

import threading
import time

import mt5_connector as mt5c
import trade_manager as tm
import indicators   as ind
import database     as db
import logger
import config


class TradeMonitor:
    def __init__(self):
        # Original SL recorded when each trade was opened
        # Needed because after break-even moves, we lose the original 1R distance
        self._original_sl:  dict[int, float] = {}
        self._tp_extended:  set[int]         = set()
        # Highest USD profit each ticket has reached (for peak-drawdown lock)
        self._peak_profit:  dict[int, float] = {}
        self._fast_guard_started = False
        # Tickets seen open on the previous fast-guard tick — used to detect
        # closures within ~1s and write them to the DB immediately
        self._last_seen_tickets: set[int] = set()

    # ── Bookkeeping ───────────────────────────────────────────

    def record_new_trade(self, ticket: int, original_sl: float):
        self._original_sl[ticket] = original_sl

    def forget_trade(self, ticket: int):
        self._original_sl.pop(ticket, None)
        self._tp_extended.discard(ticket)
        self._peak_profit.pop(ticket, None)
        try:
            db.delete_peak(ticket)
        except Exception:
            pass

    def load_peaks_from_db(self):
        """Restore peak-profit memory from the DB so the drawdown lock
        still knows each open trade's historical high after a restart."""
        try:
            self._peak_profit.update(db.get_all_peaks())
            if self._peak_profit:
                logger.info(f"  Restored peaks for {len(self._peak_profit)} trade(s) from DB")
        except Exception as e:
            logger.error(f"Could not load peaks from DB: {e}")

    def cleanup_closed_trades(self, live_tickets: set[int]):
        """Remove any bookkeeping for tickets that no longer exist."""
        stale = [t for t in self._original_sl if t not in live_tickets]
        for t in stale:
            self.forget_trade(t)

    # ── Main entry point (called every cycle for each position) ─

    def manage(self, position: dict):
        ticket = position["ticket"]

        # 1. Early exit if structure breaks against us
        if config.EARLY_EXIT_ENABLED and self._structure_broken(position):
            if tm.close_trade(ticket):
                logger.tm_early_exit(position["symbol"])
                self.forget_trade(ticket)
                return

        # 2. Profit protection — close if in profit + momentum reversing
        if config.PROFIT_PROTECTION_ENABLED and self._profit_threatened(position):
            if tm.close_trade(ticket):
                logger.tm_profit_locked(position["symbol"])
                self.forget_trade(ticket)
                return

        # 2b. Peak drawdown lock is handled by the fast guard thread
        #     (start_fast_guard) which polls every second for instant reaction.
        #     Doing it here too would race with the guard.

        # 3. SL management (breakeven + trailing)
        self._apply_sl_management(position)

        # 4. TP extension
        if config.TP_EXTENSION_ENABLED:
            self._maybe_extend_tp(position)

    # ── 1R distance lookup ────────────────────────────────────

    def _one_r(self, position: dict) -> float:
        """Returns the original risk distance (1R)."""
        ticket = position["ticket"]
        entry  = position["open_price"]

        if ticket in self._original_sl:
            return abs(entry - self._original_sl[ticket])

        # Fallback: assume 1:2 R:R (half the TP distance)
        tp = position["tp"]
        if tp != 0:
            return abs(entry - tp) / config.ATR_TP_MULTIPLIER * config.ATR_SL_MULTIPLIER
        return 0.0

    # ── Early exit: structure break ───────────────────────────

    def _structure_broken(self, position: dict) -> bool:
        df = mt5c.get_candles(position["symbol"], "M15", 50)
        if df is None or len(df) < 25:
            return False

        sym = mt5c.get_symbol_info(position["symbol"])
        if not sym:
            return False

        lookback = config.EARLY_EXIT_LOOKBACK

        if position["type"] == "BUY":
            current = sym["bid"]
            recent_low = df["Low"].iloc[-lookback:-1].min()
            # Structure broken if current price drops below the recent low
            # AND that low is still above the SL (so SL hasn't fired yet)
            if current < recent_low and recent_low > position["sl"]:
                return True

        else:   # SELL
            current = sym["ask"]
            recent_high = df["High"].iloc[-lookback:-1].max()
            if current > recent_high and recent_high < position["sl"]:
                return True

        return False

    # ── Profit protection: close on momentum reversal ─────────

    def _profit_threatened(self, position: dict) -> bool:
        """
        Returns True if the trade is currently in profit AND momentum
        has clearly reversed against it.  Uses 3 reversal signals —
        close if at least 2 trigger.
        """
        sym = mt5c.get_symbol_info(position["symbol"])
        if not sym:
            return False

        entry = position["open_price"]
        if position["type"] == "BUY":
            price = sym["bid"]
            if price <= entry:
                return False   # not in profit
        else:
            price = sym["ask"]
            if price >= entry:
                return False

        # Don't double-protect: if already 1R+ (SL at breakeven), the
        # existing breakeven logic is sufficient — no need to close early
        one_r = self._one_r(position)
        if one_r > 0:
            if position["type"] == "BUY" and price >= entry + one_r:
                return False
            if position["type"] == "SELL" and price <= entry - one_r:
                return False

        # Fetch M15 for reversal analysis
        df = mt5c.get_candles(position["symbol"], "M15", 50)
        if df is None or len(df) < 30:
            return False

        rsi      = ind.rsi(df["Close"], config.RSI_PERIOD)
        ema_fast = ind.ema(df["Close"], config.EMA_FAST)
        ema_slow = ind.ema(df["Close"], config.EMA_SLOW)

        if rsi.iloc[-1] != rsi.iloc[-1]:   # NaN
            return False

        prev = df.iloc[-2]
        curr = df.iloc[-1]
        signals = 0

        if position["type"] == "BUY":
            # 1. RSI was strong, now falling through 50
            if rsi.iloc[-3] > 60 and rsi.iloc[-1] < 50:
                signals += 1

            # 2. Fast EMA crossed below slow EMA
            if (ema_fast.iloc[-3] >= ema_slow.iloc[-3] and
                    ema_fast.iloc[-1] < ema_slow.iloc[-1]):
                signals += 1

            # 3. Bearish engulfing candle
            if (curr["Close"] < curr["Open"] and
                    prev["Close"] > prev["Open"] and
                    curr["Open"] >= prev["Close"] and
                    curr["Close"] <= prev["Open"]):
                signals += 1

        else:   # SELL
            if rsi.iloc[-3] < 40 and rsi.iloc[-1] > 50:
                signals += 1

            if (ema_fast.iloc[-3] <= ema_slow.iloc[-3] and
                    ema_fast.iloc[-1] > ema_slow.iloc[-1]):
                signals += 1

            # Bullish engulfing candle
            if (curr["Close"] > curr["Open"] and
                    prev["Close"] < prev["Open"] and
                    curr["Open"] <= prev["Close"] and
                    curr["Close"] >= prev["Open"]):
                signals += 1

        return signals >= 2   # need 2+ reversal signs to close

    # ── Peak drawdown lock + fast guard thread ────────────────

    def start_fast_guard(self, interval_sec: float = 1.0):
        """
        Spawn a daemon thread that polls open positions every `interval_sec`
        seconds and runs ONLY the peak-drawdown check.  Lets us react to
        profit giveback in ~1 second without rerunning the heavy market
        scan / structure-break checks (which stay on the 60s main cycle).
        """
        if self._fast_guard_started:
            return
        self._fast_guard_started = True
        t = threading.Thread(
            target=self._fast_guard_loop,
            args=(interval_sec,),
            daemon=True,
            name="peak-drawdown-guard",
        )
        t.start()
        logger.info(f"  Peak-drawdown guard running every {interval_sec:g}s")

    def _fast_guard_loop(self, interval_sec: float):
        prune_every = max(60, int(3600 / interval_sec))   # prune ~hourly
        ticks_since_prune = 0

        while True:
            try:
                positions = mt5c.get_open_positions()

                # 0. Detect trades that closed since last tick — write to DB
                #    so the trades page shows the real status within ~1s
                current = {p["ticket"] for p in positions}
                if self._last_seen_tickets:
                    just_closed = self._last_seen_tickets - current
                    for ticket in just_closed:
                        self._record_external_close(ticket)
                self._last_seen_tickets = current

                # 1. Profit safety nets — peak drawdown + breakeven lock.
                #    Run breakeven check FIRST so it has priority (the rule
                #    "no losses after profits" is non-negotiable).
                closed_this_tick: set[int] = set()
                for p in list(positions):
                    if p["ticket"] not in current:
                        continue
                    if getattr(config, "BREAKEVEN_LOCK_ENABLED", True):
                        if self._check_breakeven_lock(p):
                            closed_this_tick.add(p["ticket"])
                            continue
                    if getattr(config, "PEAK_DRAWDOWN_PROTECTION_ENABLED", False):
                        if self._check_peak_drawdown(p):
                            closed_this_tick.add(p["ticket"])

                # 2. History snapshots — one row per open trade per tick.
                #    Make sure every position has a peak set even when locks
                #    are disabled, so snapshots always record a peak.
                if getattr(config, "TRADE_HISTORY_ENABLED", True):
                    snap_rows = []
                    for p in positions:
                        ticket = p["ticket"]
                        if ticket in closed_this_tick:
                            continue
                        if ticket not in self._peak_profit:
                            self._peak_profit[ticket] = p["profit"]
                        sym = mt5c.get_symbol_info(p["symbol"])
                        price = (sym["bid"] if p["type"] == "BUY" else sym["ask"]) if sym else None
                        snap_rows.append((
                            ticket, p["profit"], self._peak_profit[ticket], price
                        ))
                    db.save_snapshots_batch(snap_rows)

                # 3. Periodic prune of old snapshots
                ticks_since_prune += 1
                if ticks_since_prune >= prune_every:
                    ticks_since_prune = 0
                    hrs = int(getattr(config, "TRADE_HISTORY_RETENTION_HOURS", 168))
                    db.prune_snapshots(hrs)

            except Exception as e:
                # Don't let a transient error kill the guard
                logger.error(f"Peak-drawdown guard error: {e}")
            time.sleep(interval_sec)

    # ── Robust close with retry ───────────────────────────────

    def _force_close(self, position: dict, reason: str) -> bool:
        """
        Close a position with up to 3 retries.  Synthetic indices and
        Boom/Crash can move during the close request, causing a requote
        rejection.  Without retry, the lock silently fails.
        """
        ticket = position["ticket"]
        symbol = position["symbol"]
        for attempt in range(1, 4):
            if tm.close_trade(ticket):
                return True
            logger.tm_close_failed(symbol, ticket, attempt, "broker rejected")
            time.sleep(0.4)
        logger.tm_close_gave_up(symbol, ticket, reason)
        return False

    # ── Breakeven safety lock ─────────────────────────────────

    def _check_breakeven_lock(self, position: dict) -> bool:
        """
        Once a trade's peak profit has crossed BREAKEVEN_LOCK_AFTER_PROFIT_USD,
        force-close immediately if profit drops to $0 or below.  Guarantees
        no profitable trade ever closes at a loss.

        Returns True if the trade was closed.
        """
        ticket    = position["ticket"]
        profit    = position["profit"]
        threshold = getattr(config, "BREAKEVEN_LOCK_AFTER_PROFIT_USD", 1.0)
        peak      = self._peak_profit.get(ticket, 0.0)

        if peak < threshold:
            return False    # never crossed the "real profit" threshold
        if profit > 0:
            return False    # still in profit — let the peak-drawdown handle it

        # Trade was profitable, now it's at or below break-even — close NOW
        if self._force_close(position, reason="breakeven safety"):
            logger.tm_breakeven_lock(position["symbol"], peak, profit)
            self._immediate_close_record(
                position, peak, "closed_profit_locked",
                f"breakeven safety: peaked at ${peak:+.2f}",
            )
            self.forget_trade(ticket)
            return True
        return False

    # ── Close detection (1-second) ────────────────────────────

    def _record_external_close(self, ticket: int):
        """
        A ticket disappeared from MT5 since last tick.  Pull final price
        and profit from MT5 history and update the DB right now so the
        trades page reflects the close within ~1 second.
        """
        import MetaTrader5 as mt5
        try:
            deals = mt5.history_deals_get(ticket=ticket)
            if not deals:
                # MT5 doesn't have history yet (rare timing) — skip;
                # main loop's 60s sync will catch it as backup.
                return

            last   = deals[-1]
            profit = sum(d.profit for d in deals) + sum(d.swap for d in deals) + sum(d.commission for d in deals)

            reason = last.comment or ""
            status = "closed"
            rl = reason.lower()
            if "tp" in rl or "take profit" in rl:
                status = "closed_tp"
            elif "sl" in rl or "stop loss" in rl:
                status = "closed_sl"

            peak = self._peak_profit.get(ticket)
            db.log_trade_close(ticket, last.price, profit, status, reason, peak_profit=peak)
            db.delete_peak(ticket)
            self.forget_trade(ticket)
            logger.trade_closed(ticket, last.symbol, profit)
        except Exception as e:
            logger.error(f"  Close-detection error for ticket {ticket}: {e}")

    def _immediate_close_record(self, position: dict, peak: float, status: str, reason: str):
        """
        Write the close to DB *now* with the in-memory peak — don't wait
        for the next tick's _record_external_close (which might miss the
        peak after forget_trade).  The next tick will idempotently update
        with more accurate deal data; peak_profit won't be overwritten.
        """
        try:
            sym         = mt5c.get_symbol_info(position["symbol"])
            close_price = (sym["bid"] if position["type"] == "BUY" else sym["ask"]) if sym else position["open_price"]
            db.log_trade_close(
                position["ticket"], close_price, position["profit"],
                status, reason, peak_profit=peak,
            )
        except Exception as e:
            logger.error(f"  DB write failed for close of ticket {position['ticket']}: {e}")

    def _check_peak_drawdown(self, position: dict) -> bool:
        """
        Track each trade's all-time-high USD profit.  If current profit
        drops by PEAK_DRAWDOWN_PERCENT from that peak, close the trade
        immediately to lock in what's left.  Only starts tracking once
        the peak has cleared PEAK_DRAWDOWN_MIN_PROFIT_USD so trivial
        sub-dollar swings don't trigger it.

        Returns True if the trade was closed (caller should stop
        managing this position for the rest of the cycle).
        """
        ticket  = position["ticket"]
        profit  = position["profit"]
        min_pk  = getattr(config, "PEAK_DRAWDOWN_MIN_PROFIT_USD", 1.0)
        pct     = getattr(config, "PEAK_DRAWDOWN_PERCENT", 25.0)

        # Track the all-time high — including negatives, so the history
        # chart and "peaked at" label reflect the trade's actual best moment.
        # The lock only fires when peak >= min_pk (positive), so negative
        # peaks are recorded but never trigger a close.
        if ticket not in self._peak_profit or profit > self._peak_profit[ticket]:
            self._peak_profit[ticket] = profit
            try:
                db.save_peak(ticket, profit)   # persist so it survives restart
            except Exception:
                pass
            return False   # new high — nothing to do

        peak = self._peak_profit.get(ticket, 0.0)

        # Don't act until peak has cleared the minimum threshold
        if peak < min_pk:
            return False

        # Trigger: current profit has fallen this far from peak
        trigger = peak * (1.0 - pct / 100.0)
        if profit <= trigger:
            if self._force_close(position, reason=f"{pct:.0f}% drawdown lock"):
                logger.tm_peak_lock(position["symbol"], peak, profit, pct)
                self._immediate_close_record(
                    position, peak, "closed_profit_locked",
                    f"drawdown lock: peak ${peak:+.2f} -> ${profit:+.2f}",
                )
                self.forget_trade(ticket)
                return True
        return False

    # ── SL management: breakeven + trailing ───────────────────

    def _apply_sl_management(self, position: dict):
        sym = mt5c.get_symbol_info(position["symbol"])
        if not sym:
            return

        entry       = position["open_price"]
        current_sl  = position["sl"]
        one_r       = self._one_r(position)
        if one_r == 0:
            return

        if position["type"] == "BUY":
            price    = sym["bid"]
            profit_r = (price - entry) / one_r

            if profit_r >= 2.0:
                new_sl = price - one_r
                if new_sl > current_sl:
                    if tm.modify_sl(position["ticket"], new_sl):
                        logger.tm_trailing(position["symbol"], new_sl, profit_r - 1)
                return

            if profit_r >= 1.0 and current_sl < entry:
                new_sl = entry + sym["point"] * 2
                if tm.modify_sl(position["ticket"], new_sl):
                    logger.tm_breakeven(position["symbol"])

        else:   # SELL
            price    = sym["ask"]
            profit_r = (entry - price) / one_r

            if profit_r >= 2.0:
                new_sl = price + one_r
                if new_sl < current_sl:
                    if tm.modify_sl(position["ticket"], new_sl):
                        logger.tm_trailing(position["symbol"], new_sl, profit_r - 1)
                return

            if profit_r >= 1.0 and current_sl > entry:
                new_sl = entry - sym["point"] * 2
                if tm.modify_sl(position["ticket"], new_sl):
                    logger.tm_breakeven(position["symbol"])

    # ── TP extension when momentum is still strong ────────────

    def _maybe_extend_tp(self, position: dict):
        ticket = position["ticket"]
        if ticket in self._tp_extended:
            return   # only extend once per trade

        sym = mt5c.get_symbol_info(position["symbol"])
        if not sym:
            return

        entry = position["open_price"]
        tp    = position["tp"]
        if tp == 0:
            return

        total = abs(tp - entry)
        if total == 0:
            return

        if position["type"] == "BUY":
            price = sym["bid"]
            done  = (price - entry) / total
        else:
            price = sym["ask"]
            done  = (entry - price) / total

        # Must be 80%+ toward TP but not past it
        if done < 0.8 or done > 1.0:
            return

        df = mt5c.get_candles(position["symbol"], "M5", 50)
        if df is None or len(df) < 20:
            return

        rsi_series = ind.rsi(df["Close"], config.RSI_PERIOD)
        rsi_now    = rsi_series.iloc[-1]
        rsi_ref    = rsi_series.iloc[-3]

        if rsi_now != rsi_now or rsi_ref != rsi_ref:  # NaN check
            return

        one_r = self._one_r(position)
        if one_r == 0:
            return

        if position["type"] == "BUY":
            if rsi_now > 60 and rsi_now > rsi_ref:
                new_tp = tp + one_r
                if tm.modify_tp(ticket, new_tp):
                    self._tp_extended.add(ticket)
                    logger.tm_tp_extended(position["symbol"], new_tp)
        else:
            if rsi_now < 40 and rsi_now < rsi_ref:
                new_tp = tp - one_r
                if tm.modify_tp(ticket, new_tp):
                    self._tp_extended.add(ticket)
                    logger.tm_tp_extended(position["symbol"], new_tp)
