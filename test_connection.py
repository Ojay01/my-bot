"""
Connection Tester — run this BEFORE starting the bot.

It will:
  1. Connect to your Deriv MT5 account
  2. Show your account balance and details
  3. Check every symbol in your config and show which ones are
     available on your account (some may have different names)
  4. Show current spreads

Run:  python test_connection.py
"""

import sys
import MetaTrader5 as mt5
import config

RESET  = "\033[0m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"


def line(char="─", n=60):
    print(char * n)


def ok(msg):   print(f"  {GREEN}[OK]{RESET}  {msg}")
def fail(msg): print(f"  {RED}[FAIL]{RESET}  {msg}")
def warn(msg): print(f"  {YELLOW}[WARN]{RESET}  {msg}")
def info(msg): print(f"  {CYAN}{msg}{RESET}")


def main():
    print(f"\n{BOLD}{'='*60}")
    print("  TRADING BOT — CONNECTION TEST")
    print(f"{'='*60}{RESET}\n")

    # ── Step 1: Initialise MT5 ────────────────────────────────
    print(f"{BOLD}[1] Connecting to MT5...{RESET}")
    if not mt5.initialize():
        fail(f"MT5 failed to initialise. Is MetaTrader 5 installed?")
        sys.exit(1)
    ok("MT5 initialised")

    # ── Step 2: Login ─────────────────────────────────────────
    print(f"\n{BOLD}[2] Logging in...{RESET}")
    print(f"  Login  : {config.MT5_LOGIN}")
    print(f"  Server : {config.MT5_SERVER}")

    result = mt5.login(
        login   = config.MT5_LOGIN,
        password= config.MT5_PASSWORD,
        server  = config.MT5_SERVER,
    )

    if not result:
        err = mt5.last_error()
        fail(f"Login failed — error {err}")
        print(f"\n  Check these in config.py:")
        print(f"    MT5_LOGIN    = your account number (integer, no quotes)")
        print(f"    MT5_PASSWORD = your password (in quotes)")
        print(f"    MT5_SERVER   = exact server name from MT5 login screen")
        mt5.shutdown()
        sys.exit(1)

    ok("Login successful")

    # ── Step 3: Account info ──────────────────────────────────
    print(f"\n{BOLD}[3] Account Details{RESET}")
    acc = mt5.account_info()
    if acc:
        print(f"  Name      : {acc.name}")
        print(f"  Balance   : ${acc.balance:.2f} {acc.currency}")
        print(f"  Equity    : ${acc.equity:.2f}")
        print(f"  Leverage  : 1:{acc.leverage}")
        print(f"  Server    : {acc.server}")
        print(f"  Account # : {acc.login}")

        if acc.balance < 1:
            warn("Balance is very low — make sure you have funds in this account")
        else:
            ok(f"Balance ${acc.balance:.2f} confirmed")
    else:
        fail("Could not retrieve account info")

    # ── Step 4: Check all configured symbols ──────────────────
    print(f"\n{BOLD}[4] Symbol Check{RESET}")
    line()

    available   = []
    unavailable = []

    for symbol in config.ACTIVE_SYMBOLS:
        mt5.symbol_select(symbol, True)
        info_s = mt5.symbol_info(symbol)

        if info_s is None:
            unavailable.append(symbol)
            fail(f"{symbol:<40} NOT FOUND")
        else:
            tick   = mt5.symbol_info_tick(symbol)
            spread = info_s.spread

            # Spread in pips: for most instruments, 1 pip = 10 points
            digits = info_s.digits
            if digits >= 4:
                spread_pips = spread / 10.0
            else:
                spread_pips = spread / 1.0

            price  = tick.bid if tick else 0.0
            ok(f"{symbol:<40} price={price:.5f}  spread={spread_pips:.1f} pips")
            available.append(symbol)

    line()
    print(f"\n  Available   : {GREEN}{len(available)}{RESET} symbols")
    print(f"  Unavailable : {RED}{len(unavailable)}{RESET} symbols")

    if unavailable:
        print(f"\n{YELLOW}  Symbols not found on your account:{RESET}")
        for s in unavailable:
            print(f"    - {s}")
        print(f"\n  To fix: open MT5 -> View -> Symbols, find the correct")
        print(f"  name, then update config.py ACTIVE_SYMBOLS accordingly.")
        print(f"  You can also just comment them out with # for now.")

    # ── Step 5: Summary ───────────────────────────────────────
    print(f"\n{BOLD}[5] Summary{RESET}")
    line()

    if not unavailable:
        print(f"\n  {GREEN}{BOLD}ALL GOOD — bot is ready to run!{RESET}")
        print(f"\n  Next step: double-click  start.bat")
        print(f"  IMPORTANT: test on a DEMO account first.\n")
    else:
        print(f"\n  {YELLOW}Fix the unavailable symbols above, then re-run this test.{RESET}\n")

    mt5.shutdown()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTest cancelled.")
        mt5.shutdown()
