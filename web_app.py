"""
Web UI — Flask app on port 4000.
Three pages:  /trades  /signals  /settings
"""

from flask import Flask, render_template, request, redirect, url_for
import database as db
import config

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── Which settings are editable via the UI ───────────────────
# (key, label, type, hint)
# Settings in LIVE_SETTING_KEYS take effect immediately — no bot restart.
# Everything else triggers an auto-restart via start.bat after save.
LIVE_SETTING_KEYS = {"TRADING_ENABLED"}

EDITABLE_SETTINGS = [
    ("TRADING_ENABLED",             "Take new trades (live)",         "bool",  "Off = analysis & signals continue, but bot stops opening trades"),
    ("RISK_PERCENT",                "Risk per trade (%)",             "float", "1.0 = risk 1% of balance per trade"),
    ("MAX_OPEN_TRADES_DEMO",        "Max open trades (demo)",         "int",   "How many trades at once on demo"),
    ("MAX_OPEN_TRADES_LIVE",        "Max open trades (live)",         "int",   "How many trades at once on real"),
    ("MAX_TRADES_PER_SYMBOL",       "Max trades per pair",            "int",   "Allows averaging in / fixing bad entries"),
    ("DAILY_LOSS_LIMIT",            "Daily loss limit (%)",           "float", "Stop trading today if losses hit this"),
    ("PROFIT_TARGET_PERCENT",       "Profit target (% of capital)",   "float", "Goal: grow starting capital by this % (50 = +50%)"),
    ("ACCOUNT_GIVEBACK_PERCENT",    "Account giveback lock (%)",      "float", "After target passed: close ALL if equity falls this % from peak"),
    ("HARD_STOP_BALANCE",           "Hard stop balance ($)",          "float", "Stop ALL trading if balance drops here"),
    ("FOREX_MIN_BALANCE",           "Forex min balance ($)",          "float", "Only trade Forex above this balance"),
    ("MIN_SMC_CONFLUENCE_SCORE",    "Min SMC score",                  "float", "Higher = fewer, better SMC signals"),
    ("MIN_SIGNAL_STRENGTH_AGREEMENT","Min strength when 2 agree",     "float", "0.0 to 1.0 — classic strategies"),
    ("MIN_SIGNAL_STRENGTH_SOLO",    "Min strength when 1 fires",      "float", "0.0 to 1.0 — solo strategy signal"),
    ("SCAN_INTERVAL_SECONDS",       "Scan interval (seconds)",        "int",   "How often the bot checks the market"),
    ("EARLY_EXIT_ENABLED",          "Early exit enabled",             "bool",  "Close trade when structure breaks"),
    ("PROFIT_PROTECTION_ENABLED",   "Profit protection enabled",      "bool",  "Close when profit + momentum reverse"),
    ("PEAK_DRAWDOWN_PROTECTION_ENABLED","Peak drawdown lock enabled", "bool",  "Close trade if profit drops X% from its peak"),
    ("PEAK_DRAWDOWN_PERCENT",       "Peak drawdown %",                "float", "% drop from peak that triggers a close (e.g. 15)"),
    ("PEAK_DRAWDOWN_MIN_PROFIT_PCT","Peak drawdown min profit (% bal)","float", "Only kicks in once profit reaches this % of balance"),
    ("BREAKEVEN_LOCK_ENABLED",      "Breakeven safety lock",          "bool",  "Once trade was in profit, never let it close at a loss"),
    ("BREAKEVEN_LOCK_AFTER_PROFIT_PCT","Breakeven lock after (% bal)","float", "Lock kicks in once peak reaches this % of balance"),
    ("SPREAD_COST_GUARD_ENABLED",   "Spread cost guard",              "bool",  "Skip trade if entry spread cost > X% of balance"),
    ("MAX_SPREAD_COST_PERCENT",     "Max spread cost (%)",            "float", "Skip trade when spread × lot would cost more than this %"),
    ("TP_EXTENSION_ENABLED",        "TP extension enabled",           "bool",  "Extend TP on strong momentum"),
    ("TRAILING_STOP",               "Trailing stop enabled",          "bool",  "Move SL up as price moves"),
    ("SESSION_FILTER_ENABLED",      "Session filter (Forex only)",    "bool",  "Skip Forex outside London/NY hours"),
    ("SPREAD_FILTER_ENABLED",       "Spread filter",                  "bool",  "Skip trade when spread is too wide"),
]


def _current_value(key: str):
    stored = db.get_setting(key, None)
    if stored is not None:
        return stored
    return getattr(config, key, None)


# ── Routes ────────────────────────────────────────────────────

@app.route("/")
def home():
    return redirect(url_for("trades"))


@app.route("/trades")
def trades():
    all_trades = db.get_all_trades(300)

    # Summary stats
    closed_trades = [t for t in all_trades if t["status"] != "open"]
    open_trades   = [t for t in all_trades if t["status"] == "open"]

    wins    = [t for t in closed_trades if (t["profit"] or 0) > 0]
    losses  = [t for t in closed_trades if (t["profit"] or 0) <= 0]
    total_profit = sum((t["profit"] or 0) for t in closed_trades)
    win_rate = (len(wins) / len(closed_trades) * 100) if closed_trades else 0

    return render_template("trades.html",
                           trades=all_trades,
                           open_count=len(open_trades),
                           closed_count=len(closed_trades),
                           wins=len(wins),
                           losses=len(losses),
                           total_profit=total_profit,
                           win_rate=win_rate)


@app.route("/signals")
def signals():
    rows = db.get_recent_signals(300)
    # Count taken vs skipped
    taken   = sum(1 for r in rows if r["action"] == "taken")
    skipped = sum(1 for r in rows if r["action"] == "skipped")
    return render_template("signals.html",
                           signals=rows,
                           taken=taken,
                           skipped=skipped)


@app.route("/settings", methods=["GET", "POST"])
def settings():
    saved = False

    if request.method == "POST":
        non_live_changed = False
        for key, _, typ, _ in EDITABLE_SETTINGS:
            raw = request.form.get(key)
            if typ == "bool":
                val = (request.form.get(key) == "on")
            else:
                if raw is None or raw == "":
                    continue
                try:
                    val = int(raw)   if typ == "int"   else \
                          float(raw) if typ == "float" else \
                          raw
                except ValueError:
                    continue

            old_val = _current_value(key)
            db.set_setting(key, val)
            if key not in LIVE_SETTING_KEYS and old_val != val:
                non_live_changed = True

        # Only trigger an auto-restart if a non-live setting actually changed
        if non_live_changed:
            db.set_restart_flag()
            return redirect(url_for("settings", saved="restart"))
        return redirect(url_for("settings", saved="live"))

    current = {key: _current_value(key) for key, _, _, _ in EDITABLE_SETTINGS}

    return render_template("settings.html",
                           fields=EDITABLE_SETTINGS,
                           current=current,
                           saved=request.args.get("saved"))


@app.route("/trade/<int:ticket>")
def trade_history(ticket):
    trade = db.get_trade_by_ticket(ticket)
    snaps = db.get_trade_snapshots(ticket, limit=10000)

    # Build a simple SVG line chart of profit + peak over time
    chart = _build_profit_svg(snaps) if snaps else None

    final_peak = max((s["peak"] or 0) for s in snaps) if snaps else 0
    return render_template("trade_history.html",
                           trade=trade,
                           ticket=ticket,
                           snaps=snaps,
                           chart=chart,
                           final_peak=final_peak)


def _build_profit_svg(snaps: list) -> dict:
    """Render an SVG line chart of profit (blue) and peak (gold) over time."""
    W, H, PAD = 800, 280, 30
    profits = [s["profit"] or 0 for s in snaps]
    peaks   = [s["peak"]   or 0 for s in snaps]
    lo = min(min(profits), 0)
    hi = max(max(peaks),   0.01)
    span = (hi - lo) or 1
    n = len(snaps)

    def x(i): return PAD + (W - 2 * PAD) * (i / max(n - 1, 1))
    def y(v): return PAD + (H - 2 * PAD) * (1 - (v - lo) / span)

    profit_pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(profits))
    peak_pts   = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(peaks))
    zero_y     = y(0)

    return {
        "w": W, "h": H,
        "profit_pts": profit_pts,
        "peak_pts":   peak_pts,
        "zero_y":     zero_y,
        "lo":         lo,
        "hi":         hi,
    }


@app.route("/api/live")
def api_live():
    """Live snapshot of open positions and account — polled every second by the trades page."""
    try:
        import mt5_connector as mt5c
        positions = mt5c.get_open_positions()
        acc       = mt5c.get_account_info() or {}

        rows = []
        for p in positions:
            sym     = mt5c.get_symbol_info(p["symbol"])
            current = (sym["bid"] if p["type"] == "BUY" else sym["ask"]) if sym else None
            rows.append({
                "ticket":  p["ticket"],
                "symbol":  p["symbol"],
                "type":    p["type"],
                "current": current,
                "profit":  p["profit"],
                "sl":      p["sl"],
                "tp":      p["tp"],
            })

        return {
            "ok":         True,
            "positions":  rows,
            "open_count": len(rows),
            "balance":    acc.get("balance"),
            "equity":     acc.get("equity"),
            "floating":   acc.get("profit"),
            "currency":   acc.get("currency", "USD"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.route("/api/restart", methods=["POST"])
def api_restart():
    db.set_restart_flag()
    return redirect(url_for("settings"))


def run_web(port: int = 4000):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
