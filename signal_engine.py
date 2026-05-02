"""
Signal Engine — runs all strategies on each symbol and returns the
best signal, prioritising SMC (highest quality) over classic TA.

Priority order:
  1. SMC  — Order Block + FVG + Fibonacci + Liquidity + BOS/CHOCH
  2. EMA Crossover — trend-following confirmation
  3. RSI + Bollinger — mean-reversion entries
  4. Boom/Crash Spike — spike reversal (synthetic indices only)

For non-Boom/Crash symbols:
  - If SMC gives a signal  → use it (it already includes all confluence)
  - If SMC is silent but EMA + RSI/BB AGREE on direction → take that trade
  - If only one classic strategy fires → require strength ≥ 0.4

For Boom/Crash:
  - Always use the dedicated spike strategy (markets behave differently)
"""

import mt5_connector as mt5c
import config
from strategies.base_strategy    import Signal, NONE_SIGNAL
from strategies.smc_strategy     import SmcStrategy
from strategies.ema_crossover    import EmaCrossoverStrategy
from strategies.rsi_bollinger    import RsiBollingerStrategy
from strategies.boom_crash       import BoomCrashStrategy


class SignalEngine:
    def __init__(self):
        self._smc    = SmcStrategy()
        self._ema    = EmaCrossoverStrategy()
        self._rsibb  = RsiBollingerStrategy()
        self._bc     = BoomCrashStrategy()

    # ── Whitelist + confirmation helpers ──────────────────────

    def _is_allowed(self, strategy: str, symbol: str) -> bool:
        """Strategy-symbol whitelist gate. Drop signal if the strategy
        isn't proven on this symbol."""
        if not getattr(config, "STRATEGY_WHITELIST_ENABLED", True):
            return True
        rules   = getattr(config, "STRATEGY_SYMBOL_RULES", {})
        allowed = rules.get(strategy)
        if allowed is None or "*" in allowed:
            return True
        return symbol in allowed

    def _confirms_direction(self, df, direction: str) -> bool:
        """Require the most recently CLOSED candle to move in the signal
        direction. iloc[-1] in MT5 data is the still-forming bar; iloc[-2]
        is the last completed candle."""
        if not getattr(config, "ENTRY_CONFIRMATION_ENABLED", True):
            return True
        if df is None or len(df) < 3:
            return True
        last_closed = df.iloc[-2]
        if direction == "BUY":
            return last_closed["Close"] > last_closed["Open"]
        if direction == "SELL":
            return last_closed["Close"] < last_closed["Open"]
        return True

    def _filter(self, sig: Signal, symbol: str, df) -> Signal:
        """Apply both gates (whitelist + confirmation) to any candidate
        signal before returning it. Returns NONE_SIGNAL if blocked."""
        if sig.direction == "NONE":
            return sig
        if not self._is_allowed(sig.strategy, symbol):
            return NONE_SIGNAL
        if not self._confirms_direction(df, sig.direction):
            return NONE_SIGNAL
        return sig

    def get_signal(self, symbol: str) -> Signal:

        # ── Boom, Crash, and Jump indices (spike reversal) ───
        if symbol in config.BOOM_CRASH_SYMBOLS or symbol in config.JUMP_SYMBOLS:
            df = mt5c.get_candles(symbol, "M1", config.LOOKBACK_CANDLES)
            if df is None or len(df) < 30:
                return NONE_SIGNAL
            sym_info = mt5c.get_symbol_info(symbol)
            if not sym_info:
                return NONE_SIGNAL
            return self._filter(
                self._bc.generate_signal(df, symbol, sym_info["ask"]),
                symbol, df,
            )

        # ── All other symbols (Forex + Volatility indices) ────
        df = mt5c.get_candles(symbol, config.SIGNAL_TF, config.LOOKBACK_CANDLES)
        if df is None or len(df) < 50:
            return NONE_SIGNAL

        sym_info = mt5c.get_symbol_info(symbol)
        if not sym_info:
            return NONE_SIGNAL

        price = sym_info["ask"]

        # 1. Try SMC first — highest quality signal
        smc_sig = self._smc.generate_signal(df, symbol, price)
        if smc_sig.direction != "NONE":
            filtered = self._filter(smc_sig, symbol, df)
            if filtered.direction != "NONE":
                return filtered
            # SMC blocked — fall through to classic TA below

        # 2. Fall back to classic TA strategies
        ema_sig   = self._ema.generate_signal(df, symbol, price)
        rsibb_sig = self._rsibb.generate_signal(df, symbol, price)

        candidates = [s for s in (ema_sig, rsibb_sig) if s.direction != "NONE"]

        if not candidates:
            return NONE_SIGNAL

        buys  = [s for s in candidates if s.direction == "BUY"]
        sells = [s for s in candidates if s.direction == "SELL"]

        # Both classic strategies agree → good signal, but still needs strength
        if len(buys) == 2:
            best = max(buys, key=lambda s: s.strength)
            if best.strength < config.MIN_SIGNAL_STRENGTH_AGREEMENT:
                return NONE_SIGNAL
            return self._filter(best, symbol, df)
        if len(sells) == 2:
            best = max(sells, key=lambda s: s.strength)
            if best.strength < config.MIN_SIGNAL_STRENGTH_AGREEMENT:
                return NONE_SIGNAL
            return self._filter(best, symbol, df)

        # Only one fires — require much higher strength
        best = max(candidates, key=lambda s: s.strength)
        if best.strength < config.MIN_SIGNAL_STRENGTH_SOLO:
            return NONE_SIGNAL
        return self._filter(best, symbol, df)
