from datetime import date, datetime, timedelta
import mt5_connector as mt5c
import config


class RiskManager:
    def __init__(self):
        self._daily_start_balance: float = 0.0
        self._last_checked_date: date = date.min
        self._daily_loss_locked: bool = False
        # ticket -> (symbol, close_time) for recently-closed trades
        self._recent_closes: dict[str, datetime] = {}
        self._previously_open_tickets: set[int] = set()

    # ── Per-symbol cooldown ───────────────────────────────────

    def update_closed_trades(self):
        """
        Called each cycle.  Detects trades that were open last cycle
        but are now closed, and records their close time so we can
        enforce the cooldown per symbol.
        """
        current_positions = mt5c.get_open_positions()
        current_tickets   = {p["ticket"] for p in current_positions}
        current_symbols   = {p["ticket"]: p["symbol"] for p in current_positions}

        # Trades that were open last time but not now = just closed
        closed_tickets = self._previously_open_tickets - current_tickets
        now            = datetime.utcnow()

        for ticket in closed_tickets:
            # We don't know the symbol of the closed one from current_positions,
            # so look it up from MT5 history
            import MetaTrader5 as mt5
            deals = mt5.history_deals_get(ticket=ticket)
            if deals:
                sym = deals[-1].symbol
                self._recent_closes[sym] = now

        # Update tracking for next cycle
        self._previously_open_tickets = current_tickets

    def is_in_cooldown(self, symbol: str) -> bool:
        """True if a trade closed on this symbol within the cooldown window."""
        last_close = self._recent_closes.get(symbol)
        if not last_close:
            return False
        elapsed = datetime.utcnow() - last_close
        return elapsed < timedelta(minutes=config.SYMBOL_COOLDOWN_MINUTES)

    def cooldown_remaining(self, symbol: str) -> int:
        """Minutes of cooldown remaining, 0 if none."""
        last_close = self._recent_closes.get(symbol)
        if not last_close:
            return 0
        elapsed = datetime.utcnow() - last_close
        remaining = timedelta(minutes=config.SYMBOL_COOLDOWN_MINUTES) - elapsed
        return max(0, int(remaining.total_seconds() / 60) + 1)

    # ── Hard balance floor ────────────────────────────────────

    def is_hard_floor_hit(self) -> bool:
        """Stop ALL trading if balance drops to HARD_STOP_BALANCE."""
        info = mt5c.get_account_info()
        if not info:
            return False
        return info["balance"] <= config.HARD_STOP_BALANCE

    # ── Small account Forex guard ─────────────────────────────

    def can_trade_forex_balance(self) -> bool:
        """
        Forex minimum lots often risk 20%+ on a $10 account.
        Only allow Forex/Metals once balance reaches FOREX_MIN_BALANCE.
        Below that, synthetics only.
        """
        info = mt5c.get_account_info()
        if not info:
            return False
        return info["balance"] >= config.FOREX_MIN_BALANCE

    # ── Spread filter ─────────────────────────────────────────

    def spread_is_acceptable(self, symbol: str) -> bool:
        """Returns False if the current spread is too wide to trade."""
        if not config.SPREAD_FILTER_ENABLED:
            return True

        sym = mt5c.get_symbol_info(symbol)
        if not sym:
            return False

        # Forex & Metals — pip-based check
        if symbol in config.FOREX_SYMBOLS or symbol in config.METAL_SYMBOLS:
            digits      = sym.get("digits", 5)
            spread_pips = sym["spread"] / 10.0 if digits >= 4 else float(sym["spread"])
            limit = config.MAX_SPREAD_PIPS["FOREX"] \
                    if symbol in config.FOREX_SYMBOLS \
                    else config.MAX_SPREAD_PIPS["METALS"]
            return spread_pips <= limit

        # Synthetics — percentage-of-price check (pip concept doesn't apply)
        mid_price = (sym["bid"] + sym["ask"]) / 2
        if mid_price <= 0:
            return True   # no tick yet, allow (will be re-checked at trade time)
        spread_in_price = sym["spread"] * sym["point"]
        spread_pct      = (spread_in_price / mid_price) * 100
        return spread_pct <= config.MAX_SPREAD_PCT_SYNTHETIC

    # ── Daily loss tracking ───────────────────────────────────

    def _refresh_daily_baseline(self):
        today = date.today()
        if today != self._last_checked_date:
            info = mt5c.get_account_info()
            if info:
                self._daily_start_balance = info["balance"]
                self._last_checked_date = today
                self._daily_loss_locked = False

    def is_daily_limit_hit(self) -> bool:
        self._refresh_daily_baseline()
        if self._daily_loss_locked:
            return True
        info = mt5c.get_account_info()
        if not info or self._daily_start_balance == 0:
            return False
        loss_pct = ((self._daily_start_balance - info["balance"]) /
                    self._daily_start_balance) * 100
        if loss_pct >= config.DAILY_LOSS_LIMIT:
            self._daily_loss_locked = True
            return True
        return False

    # ── Concurrent trade limit ────────────────────────────────

    def can_open_trade(self, symbol: str) -> bool:
        positions = mt5c.get_open_positions()
        if len(positions) >= config.MAX_OPEN_TRADES:
            return False
        on_pair = sum(1 for p in positions if p["symbol"] == symbol)
        if on_pair >= config.MAX_TRADES_PER_SYMBOL:
            return False
        return True

    # ── Position sizing ───────────────────────────────────────

    def calculate_lot(self, symbol: str, sl_distance_price: float) -> float:
        """
        Returns the correct lot size so that if SL is hit the loss equals
        RISK_PERCENT % of current balance.  Returns 0.0 if trade should
        be skipped (e.g. min lot would risk too much).
        """
        info = mt5c.get_account_info()
        sym  = mt5c.get_symbol_info(symbol)
        if not info or not sym or sl_distance_price <= 0:
            return 0.0

        balance    = info["balance"]
        risk_money = balance * (config.RISK_PERCENT / 100.0)

        tick_size  = sym["trade_tick_size"]
        tick_value = sym["trade_tick_value"]

        if tick_size == 0 or tick_value == 0:
            return 0.0

        value_per_lot = (sl_distance_price / tick_size) * tick_value

        if value_per_lot <= 0:
            return 0.0

        raw_lot = risk_money / value_per_lot
        step    = sym["volume_step"]
        lot     = round(raw_lot / step) * step
        lot     = max(sym["volume_min"], min(lot, sym["volume_max"]))

        # Skip if minimum lot risks more than 3× intended (too large for account)
        actual_risk = (lot / 1.0) * value_per_lot
        if actual_risk > risk_money * 3:
            return 0.0

        return round(lot, 8)

    # ── Break-even trailing stop ──────────────────────────────

    def get_breakeven_sl(self, position: dict) -> float | None:
        if not config.TRAILING_STOP:
            return None

        sym = mt5c.get_symbol_info(position["symbol"])
        if not sym:
            return None

        open_price = position["open_price"]
        current_sl = position["sl"]
        tp         = position["tp"]
        trade_type = position["type"]

        if tp == 0 or current_sl == 0:
            return None

        if trade_type == "BUY":
            one_r     = open_price - current_sl
            be_target = open_price + one_r
            if sym["bid"] >= be_target and current_sl < open_price:
                return open_price + sym["point"] * 2
        else:
            one_r     = current_sl - open_price
            be_target = open_price - one_r
            if sym["ask"] <= be_target and current_sl > open_price:
                return open_price - sym["point"] * 2

        return None
