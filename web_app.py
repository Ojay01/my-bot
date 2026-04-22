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
EDITABLE_SETTINGS = [
    ("RISK_PERCENT",                "Risk per trade (%)",             "float", "1.0 = risk 1% of balance per trade"),
    ("MAX_OPEN_TRADES_DEMO",        "Max open trades (demo)",         "int",   "How many trades at once on demo"),
    ("MAX_OPEN_TRADES_LIVE",        "Max open trades (live)",         "int",   "How many trades at once on real"),
    ("MAX_TRADES_PER_SYMBOL",       "Max trades per pair",            "int",   "Allows averaging in / fixing bad entries"),
    ("DAILY_LOSS_LIMIT",            "Daily loss limit (%)",           "float", "Stop trading today if losses hit this"),
    ("PROFIT_TARGET_USD",           "Profit target ($)",              "float", "Goal balance in USD"),
    ("HARD_STOP_BALANCE",           "Hard stop balance ($)",          "float", "Stop ALL trading if balance drops here"),
    ("FOREX_MIN_BALANCE",           "Forex min balance ($)",          "float", "Only trade Forex above this balance"),
    ("MIN_SMC_CONFLUENCE_SCORE",    "Min SMC score",                  "float", "Higher = fewer, better SMC signals"),
    ("MIN_SIGNAL_STRENGTH_AGREEMENT","Min strength when 2 agree",     "float", "0.0 to 1.0 — classic strategies"),
    ("MIN_SIGNAL_STRENGTH_SOLO",    "Min strength when 1 fires",      "float", "0.0 to 1.0 — solo strategy signal"),
    ("SCAN_INTERVAL_SECONDS",       "Scan interval (seconds)",        "int",   "How often the bot checks the market"),
    ("EARLY_EXIT_ENABLED",          "Early exit enabled",             "bool",  "Close trade when structure breaks"),
    ("PROFIT_PROTECTION_ENABLED",   "Profit protection enabled",      "bool",  "Close when profit + momentum reverse"),
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
            db.set_setting(key, val)

        db.set_restart_flag()
        return redirect(url_for("settings", saved="1"))

    current = {key: _current_value(key) for key, _, _, _ in EDITABLE_SETTINGS}

    return render_template("settings.html",
                           fields=EDITABLE_SETTINGS,
                           current=current,
                           saved=request.args.get("saved") == "1")


@app.route("/api/restart", methods=["POST"])
def api_restart():
    db.set_restart_flag()
    return redirect(url_for("settings"))


def run_web(port: int = 4000):
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
