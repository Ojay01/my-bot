"""
One-off analysis script — pulls the real close info for every trade
the bot has opened (from MT5 history) and prints a win/loss summary
broken down by strategy and by symbol.

Run:  python summarize_trades.py
"""

import sqlite3
from collections import defaultdict
from datetime import datetime

import MetaTrader5 as mt5
import config


def _connect_mt5() -> bool:
    if not mt5.initialize():
        return False
    return bool(mt5.login(
        login    = config.MT5_LOGIN,
        password = config.MT5_PASSWORD,
        server   = config.MT5_SERVER,
    ))


def _close_info(ticket: int):
    """Returns (profit, close_time, close_price) for a closed ticket, or None."""
    deals = mt5.history_deals_get(position=ticket)
    if not deals or len(deals) < 2:
        return None
    profit = sum(d.profit + d.swap + d.commission for d in deals)
    closing_deal = deals[-1]
    return profit, closing_deal.time, closing_deal.price


def _fmt_money(x: float) -> str:
    sign = "+" if x >= 0 else ""
    return f"{sign}{x:>8.2f}"


def main():
    print("Connecting to MT5 ...")
    if not _connect_mt5():
        print("ERROR: could not connect to MT5. Check credentials in config.py")
        return

    conn   = sqlite3.connect("bot.db")
    cursor = conn.cursor()

    rows = cursor.execute(
        "SELECT ticket, symbol, direction, lot, strategy, open_time "
        "FROM trades ORDER BY id"
    ).fetchall()

    if not rows:
        print("No trades in bot.db.")
        return

    closed_trades = []   # list of dicts
    still_open    = 0

    for ticket, symbol, direction, lot, strategy, open_time in rows:
        info = _close_info(ticket)
        if info is None:
            still_open += 1
            continue
        profit, close_time, close_price = info
        closed_trades.append({
            "ticket":     ticket,
            "symbol":     symbol,
            "direction":  direction,
            "lot":        lot,
            "strategy":   strategy or "unknown",
            "profit":     profit,
            "open_time":  open_time,
            "close_time": datetime.fromtimestamp(close_time).isoformat(),
        })

    if not closed_trades:
        print(f"All {still_open} trades are still open in MT5 — nothing closed yet.")
        return

    print(f"\nFound {len(closed_trades)} closed trades  ({still_open} still open)\n")

    total = sum(t["profit"] for t in closed_trades)
    wins  = [t for t in closed_trades if t["profit"] > 0]
    loses = [t for t in closed_trades if t["profit"] <= 0]

    print("=" * 60)
    print("  OVERALL")
    print("=" * 60)
    print(f"  Total trades  : {len(closed_trades)}")
    print(f"  Wins          : {len(wins):>4}   "
          f"({len(wins)/len(closed_trades)*100:.0f}% win rate)")
    print(f"  Losses        : {len(loses):>4}")
    print(f"  Net profit    : ${_fmt_money(total)}")
    if wins:
        print(f"  Avg win       : ${_fmt_money(sum(t['profit'] for t in wins)/len(wins))}")
    if loses:
        print(f"  Avg loss      : ${_fmt_money(sum(t['profit'] for t in loses)/len(loses))}")

    # ── By strategy ─────────────────────────────────────────
    by_strategy = defaultdict(list)
    for t in closed_trades:
        by_strategy[t["strategy"]].append(t)

    print()
    print("=" * 60)
    print("  BY STRATEGY")
    print("=" * 60)
    print(f"  {'Strategy':<20} {'Trades':>7} {'Wins':>6} {'Win%':>6} {'Net P/L':>12}")
    print("  " + "-" * 56)
    for strat, trades in sorted(by_strategy.items(),
                                key=lambda kv: sum(t['profit'] for t in kv[1])):
        net   = sum(t["profit"] for t in trades)
        nwin  = sum(1 for t in trades if t["profit"] > 0)
        winp  = nwin / len(trades) * 100
        print(f"  {strat:<20} {len(trades):>7} {nwin:>6} {winp:>5.0f}% "
              f"  ${_fmt_money(net)}")

    # ── By symbol ───────────────────────────────────────────
    by_symbol = defaultdict(list)
    for t in closed_trades:
        by_symbol[t["symbol"]].append(t)

    print()
    print("=" * 60)
    print("  BY SYMBOL (worst performers first)")
    print("=" * 60)
    print(f"  {'Symbol':<32} {'Trades':>7} {'Wins':>6} {'Net P/L':>12}")
    print("  " + "-" * 56)
    for sym, trades in sorted(by_symbol.items(),
                              key=lambda kv: sum(t['profit'] for t in kv[1])):
        net  = sum(t["profit"] for t in trades)
        nwin = sum(1 for t in trades if t["profit"] > 0)
        print(f"  {sym:<32} {len(trades):>7} {nwin:>6}   ${_fmt_money(net)}")

    # ── Sync close info back to bot.db ─────────────────────
    print()
    print("Updating bot.db with real close info ...")
    for t in closed_trades:
        status = "closed_tp" if t["profit"] > 0 else "closed_sl"
        cursor.execute(
            "UPDATE trades SET status=?, profit=?, close_time=? "
            "WHERE ticket=?",
            (status, t["profit"], t["close_time"], t["ticket"]),
        )
    conn.commit()
    conn.close()
    mt5.shutdown()
    print("Done.")


if __name__ == "__main__":
    main()
