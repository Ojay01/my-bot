import csv
import logging
import os
import sys
from datetime import datetime, timezone
from colorama import Fore, Style, init

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

init(autoreset=True)

LOG_FILE   = "bot.log"
TRADE_FILE = "trades.csv"

_TRADE_HEADERS = [
    "timestamp", "symbol", "direction", "lot", "open_price",
    "sl", "tp", "ticket", "strategy", "result",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
_log = logging.getLogger("TradingBot")


# ── Friendly translations ────────────────────────────────────

STRATEGY_NAMES = {
    "SMC":             "Smart Money setup",
    "EMA_Crossover":   "Trend crossover",
    "RSI_Bollinger":   "Overbought/Oversold reversal",
    "Spike_Reversal":  "Spike reversal",
}


def _strength_label(strength: float) -> str:
    if strength >= 0.8: return "VERY STRONG"
    if strength >= 0.6: return "STRONG"
    if strength >= 0.4: return "moderate"
    return "weak"


def _ensure_trade_file():
    if not os.path.exists(TRADE_FILE):
        with open(TRADE_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(_TRADE_HEADERS)


# ── Basic log levels ─────────────────────────────────────────

def info(msg: str):     _log.info(msg)
def warning(msg: str):  _log.warning(Fore.YELLOW + msg)
def error(msg: str):    _log.error(Fore.RED + msg)


# ── Trade lifecycle ──────────────────────────────────────────

def trade_opened(ticket: int, symbol: str, direction: str,
                 lot: float, price: float, sl: float, tp: float,
                 strategy: str):
    color = Fore.GREEN if direction == "BUY" else Fore.RED
    arrow = "BUY (going up)" if direction == "BUY" else "SELL (going down)"
    nice  = STRATEGY_NAMES.get(strategy, strategy)

    risk   = abs(price - sl)
    reward = abs(tp - price)
    rr     = (reward / risk) if risk > 0 else 0

    _log.info(color + f"\n  >>> NEW TRADE OPENED <<<")
    _log.info(color + f"      {symbol} — {arrow}")
    _log.info(color + f"      Entry price : {price:.5f}")
    _log.info(color + f"      Stop loss   : {sl:.5f}  (if hit: lose 1% of balance)")
    _log.info(color + f"      Take profit : {tp:.5f}  (if hit: gain about {rr:.1f}% of balance)")
    _log.info(color + f"      Lot size    : {lot}")
    _log.info(color + f"      Reason      : {nice}")
    _log.info(color + f"      Ticket #    : {ticket}\n")

    _ensure_trade_file()
    with open(TRADE_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            datetime.now(timezone.utc).isoformat(), symbol, direction,
            lot, price, sl, tp, ticket, strategy, "open",
        ])


def trade_closed(ticket: int, symbol: str, profit: float):
    if profit >= 0:
        _log.info(Fore.GREEN + f"  WON  {symbol}  +${profit:.2f}  (ticket {ticket})")
    else:
        _log.info(Fore.RED + f"  LOST  {symbol}  -${abs(profit):.2f}  (ticket {ticket})")


# ── Per-symbol scan output ───────────────────────────────────

def scan_no_signal(symbol: str):
    _log.info(f"  {symbol:<26}  · no opportunity")


def scan_signal_found(symbol: str, direction: str, strength: float, strategy: str):
    color = Fore.GREEN if direction == "BUY" else Fore.RED
    label = _strength_label(strength)
    nice  = STRATEGY_NAMES.get(strategy, strategy)
    _log.info(color +
        f"  {symbol:<26}  >>  {label} {direction}  —  {nice}")


def scan_skipped(symbol: str, reason: str):
    _log.info(Fore.CYAN + f"  {symbol:<26}  -  skipped: {reason}")


# ── Account snapshot ─────────────────────────────────────────

def account_snapshot(balance: float, equity: float, profit: float,
                     target: float):
    profit_str = (Fore.GREEN if profit >= 0 else Fore.RED) + f"{profit:+.2f}" + Style.RESET_ALL

    header = (f"\n  Balance: ${balance:.2f}   Equity (incl open trades): ${equity:.2f}   "
              f"Open trades P&L: ${profit_str}")

    if target <= 0:
        _log.info(header + "\n")
        return

    # Demo accounts often start at $10,000 — the $50 target is then meaningless
    # so show something sensible instead of a 20,000% bar.
    if balance >= target * 5:
        _log.info(header +
            f"\n  {Fore.CYAN}Target ${target:.0f} already exceeded "
            f"(you have ${balance:.2f}){Style.RESET_ALL}\n")
        return

    pct     = balance / target * 100
    filled  = int(30 * min(pct, 100) / 100)
    bar     = Fore.GREEN + "#" * filled + Style.RESET_ALL + "-" * (30 - filled)
    _log.info(header +
        f"\n  Progress toward ${target:.0f} target: [{bar}] {min(pct, 100):.1f}%\n")


# ── Trade management messages ────────────────────────────────

def tm_early_exit(symbol: str):
    _log.info(Fore.YELLOW +
        f"  Closed {symbol} EARLY — the market turned against us, saving loss")


def tm_profit_locked(symbol: str):
    _log.info(Fore.GREEN +
        f"  Closed {symbol} in PROFIT — momentum reversing, keeping the win")


def tm_breakeven(symbol: str):
    _log.info(Fore.CYAN +
        f"  {symbol}: Stop loss moved to entry price — trade can no longer lose money")


def tm_trailing(symbol: str, new_sl: float, locked_r: float):
    _log.info(Fore.CYAN +
        f"  {symbol}: Stop loss moved up to {new_sl:.5f} — locking in {locked_r:.1f}x profit")


def tm_tp_extended(symbol: str, new_tp: float):
    _log.info(Fore.MAGENTA +
        f"  {symbol}: Take profit extended to {new_tp:.5f} — market still moving strong")


# ── System messages ──────────────────────────────────────────

def daily_limit_hit():
    _log.warning(Fore.YELLOW +
        "  STOP — daily loss limit reached. No new trades until tomorrow.")


def hard_floor_hit(balance: float, floor: float):
    _log.error(Fore.RED +
        f"  STOP — balance ${balance:.2f} hit the hard floor (${floor:.2f}). "
        f"No new trades. Add funds to resume.")


def target_reached(balance: float):
    _log.info(Fore.CYAN + Style.BRIGHT +
        f"\n  *** TARGET REACHED!  Balance = ${balance:.2f} ***\n")
