# =============================================================
#  TRADING BOT — CONFIGURATION FILE
#  Edit this file with your details before starting the bot
# =============================================================

# ── MT5 LOGIN CREDENTIALS ────────────────────────────────────
MT5_LOGIN    = 32188806          # Your Deriv MT5 account number (integer)
MT5_PASSWORD = "Amene&4Sons"   # Your MT5 password
MT5_SERVER   = "Deriv-Demo"   # Server name shown in your MT5 app
                                 # e.g. "Deriv-Demo" or "Deriv-Server"

# ── RISK SETTINGS ────────────────────────────────────────────
RISK_PERCENT     = 1.0   # % of balance risked per trade (1% recommended)
DAILY_LOSS_LIMIT = 10.0  # Stop trading today if daily loss hits this %
PROFIT_TARGET_USD= 50.0  # Bot alerts when balance reaches this

# Max open trades — more on demo for testing, fewer on live for safety
MAX_OPEN_TRADES_DEMO = 25
MAX_OPEN_TRADES_LIVE = 10
MAX_OPEN_TRADES = MAX_OPEN_TRADES_DEMO if "demo" in MT5_SERVER.lower() else MAX_OPEN_TRADES_LIVE

# Max trades allowed on a SINGLE pair (lets you add to positions /
# fix bad entries with a second setup on the same symbol).
# Set to 1 to block duplicates, or higher to allow averaging in.
MAX_TRADES_PER_SYMBOL = 3

# Cooldown: 0 = disabled.  Set to N minutes if you want the bot to wait
# N minutes before opening another trade on the same symbol after one closes.
SYMBOL_COOLDOWN_MINUTES = 0

# Signal quality thresholds — THIS is what controls how often the bot
# finds "valid" signals.  Higher = fewer, better-quality trades.
MIN_SIGNAL_STRENGTH_AGREEMENT = 0.5   # when 2 classic strategies agree
MIN_SIGNAL_STRENGTH_SOLO      = 0.7   # when only 1 classic strategy fires
MIN_SMC_CONFLUENCE_SCORE      = 2.5   # SMC setup minimum score (0-4 scale)

# Trailing stop: move SL to break-even once trade is 1R in profit
TRAILING_STOP = True

# ── ACTIVE TRADE MANAGEMENT ──────────────────────────────────
# Early exit:  close trade BEFORE SL hits if M15 structure breaks
#              against the position (saves money on losers)
EARLY_EXIT_ENABLED  = True
EARLY_EXIT_LOOKBACK = 20     # candles on M15 to check for structure break

# TP extension: when 80%+ to TP and momentum still strong,
#               extend TP by 1R.  Only extends once per trade.
TP_EXTENSION_ENABLED = True

# Profit protection: if trade is in profit (below 1R) and momentum
# clearly reverses (2+ of: RSI reversal, EMA cross, engulfing candle),
# close immediately and lock in the current profit rather than ride
# all the way back to SL.
PROFIT_PROTECTION_ENABLED = True

# Peak drawdown lock: track the highest profit each trade reaches.
# If profit drops by PEAK_DRAWDOWN_PERCENT from that peak, close the
# trade immediately — no need to hit SL.  Catches the case where price
# runs up nicely (say +$500) then reverses without warning.
# Only kicks in once profit has reached PEAK_DRAWDOWN_MIN_PROFIT_USD,
# so tiny $0.20 swings don't trigger it.
PEAK_DRAWDOWN_PROTECTION_ENABLED = True
PEAK_DRAWDOWN_PERCENT            = 25.0   # close when profit falls this % from its peak
PEAK_DRAWDOWN_MIN_PROFIT_USD     = 1.0    # don't track until peak reaches at least this much

# Breakeven safety lock — the "no losses after profits" rule.
# Once a trade's peak profit reaches BREAKEVEN_LOCK_AFTER_PROFIT_USD,
# the bot will FORCE CLOSE it the moment profit falls to $0 or below.
# This guarantees a profitable trade never closes at a loss, regardless
# of where the broker's stop-loss is.  Last-resort safety net behind
# the peak-drawdown lock.
BREAKEVEN_LOCK_ENABLED          = True
BREAKEVEN_LOCK_AFTER_PROFIT_USD = 1.0

# Per-second profit history: the fast guard saves a snapshot of every open
# trade's profit/peak/price each second so you can review the curve later
# from the web UI (Trades page → click a symbol).  Old snapshots are
# auto-pruned to keep the DB small.
TRADE_HISTORY_ENABLED          = True
TRADE_HISTORY_RETENTION_HOURS  = 168     # 7 days — older snapshots are deleted

# ── CAPITAL PROTECTION ───────────────────────────────────────
# Hard floor — if balance drops to this, stop ALL trading immediately
# For a $10 account this prevents total wipeout
HARD_STOP_BALANCE = 5.0   # USD — stop everything below this

# Small account guard — Forex minimum lots can risk 20%+ on a $10 account
# Bot will skip Forex/Metals pairs until balance reaches this threshold
# Synthetics (Deriv) support nano lots (0.001) so they work fine at $10
FOREX_MIN_BALANCE = 50.0  # USD — only trade Forex/Metals above this balance

# ── SESSION FILTER (Forex & Metals only) ─────────────────────
# Synthetics trade 24/7 and ignore this filter
# All times are UTC
SESSION_FILTER_ENABLED = False   # 24/7 — forex/metals trade in all hours

LONDON_START  = 7    # 07:00 UTC
LONDON_END    = 16   # 16:00 UTC

NEW_YORK_START = 12  # 12:00 UTC
NEW_YORK_END   = 21  # 21:00 UTC

ASIAN_START   = 0    # 00:00 UTC
ASIAN_END     = 9    # 09:00 UTC

# Which sessions to allow trading in (best = London + NY overlap)
ALLOWED_SESSIONS = ["LONDON", "NEW_YORK"]
# Options: "LONDON", "NEW_YORK", "ASIAN"
# London+NY overlap (12:00–16:00 UTC) = highest volume = best signals

# ── SPREAD FILTER ────────────────────────────────────────────
# Skip a trade if the broker spread is too wide — protects profit on small account
# Values are in PIPS
SPREAD_FILTER_ENABLED = False   # set to True to re-enable protection
MAX_SPREAD_PIPS = {
    "FOREX":  5.0,   # more generous now — skip Forex only if spread > 5 pips
    "METALS": 10.0,  # Gold/Silver spreads can be naturally wider
}
# Synthetics don't use "pips" — use spread as % of price instead
MAX_SPREAD_PCT_SYNTHETIC = 0.30   # 0.30% of price (generous)

# ── NEWS BLACKOUT ─────────────────────────────────────────────
# Bot pauses Forex/Metals trading 30 min before and after major news
# Update this list manually on Sunday before each trading week
# Format: "YYYY-MM-DD HH:MM"  (UTC time)
NEWS_FILTER_ENABLED = True
NEWS_BLACKOUT_MINUTES = 30   # pause this many minutes before AND after news

# Add upcoming high-impact news times here each week:
NEWS_EVENTS_UTC = [
    # "2024-01-05 13:30",   # NFP example
    # "2024-01-10 13:30",   # CPI example
    # "2024-01-31 19:00",   # FOMC example
]
# Synthetics are NOT affected by news — they keep running 24/7

# ── TIMEFRAMES ───────────────────────────────────────────────
# Options: "M1","M5","M15","M30","H1","H4","D1"
SIGNAL_TF = "M15"   # Main signal timeframe
TREND_TF  = "H1"    # Higher timeframe trend filter

# ── SYMBOLS TO TRADE ─────────────────────────────────────────
# Comment out any pair by adding # at the start of the line
ACTIVE_SYMBOLS = [
    # --- Forex Majors ---
    "EURUSD",   # Euro / US Dollar
    "GBPUSD",   # British Pound / US Dollar
    "USDJPY",   # US Dollar / Japanese Yen
    "USDCHF",   # US Dollar / Swiss Franc
    "AUDUSD",   # Australian Dollar / US Dollar
    "USDCAD",   # US Dollar / Canadian Dollar
    "NZDUSD",   # New Zealand Dollar / US Dollar

    # --- Forex Crosses ---
    "GBPJPY",   # British Pound / Japanese Yen (most volatile cross)
    "EURJPY",   # Euro / Japanese Yen
    "EURGBP",   # Euro / British Pound
    "GBPAUD",   # British Pound / Australian Dollar
    "AUDJPY",   # Australian Dollar / Japanese Yen

    # --- Metals ---
    "XAUUSD",   # Gold  (best SMC instrument — cleanest structure)
    "XAGUSD",   # Silver

    # --- Volatility Indices (Deriv — trade 24/7) ---
    # Lower numbers = calmer price action.  High-vol ones commented out
    # to reduce balance swings on a small account.
    "Volatility 10 Index",
    "Volatility 25 Index",
    "Volatility 50 Index",
    # "Volatility 75 Index",            # high volatility — disabled
    # "Volatility 100 Index",           # very high volatility — disabled
    # "Volatility 10 (1s) Index",       # 1-second tick = very fast — disabled
    # "Volatility 25 (1s) Index",       # 1-second tick = very fast — disabled
    # "Volatility 50 (1s) Index",       # 1-second tick = very fast — disabled
    # "Volatility 75 (1s) Index",       # 1-second tick = very fast — disabled
    # "Volatility 100 (1s) Index",      # 1-second tick = very fast — disabled

    # --- Boom & Crash Indices (Deriv — spike reversal strategy) ---
    # Tuned from real results: Boom 1000 (+$630) and Boom 500 (+$102)
    # are profitable; Crash 1000 (-$307) and Crash 500 (-$80) are not.
    "Boom 1000 Index",
    "Boom 500 Index",                   # 67% wins, +$102 in testing
    # "Boom 300 Index",                 # spikes very often — disabled
    # "Crash 1000 Index",               # losing strategy (-$307) — disabled
    # "Crash 500 Index",                # losing strategy (-$80)  — disabled
    # "Crash 300 Index",                # spikes very often — disabled

    # --- Jump Indices (Deriv — sudden jumps both directions) ---
    # Disabled entirely — jumps are unpredictable on a small account.
    # "Jump 10 Index",
    # "Jump 25 Index",
    # "Jump 50 Index",
    # "Jump 75 Index",
    # "Jump 100 Index",

    # --- Step & Range Break Indices (Deriv) ---
    "Step Index",                       # very calm — smallest tick moves
    "Range Break 100 Index",            # range-bound = lower volatility
    # "Range Break 200 Index",          # bigger ranges — disabled
]

# ── SYMBOL CATEGORIES (do not edit) ──────────────────────────
FOREX_SYMBOLS = [
    "EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD",
    "GBPJPY","EURJPY","EURGBP","GBPAUD","AUDJPY",
]
METAL_SYMBOLS = ["XAUUSD", "XAGUSD"]

BOOM_CRASH_SYMBOLS = [
    "Boom 1000 Index","Boom 500 Index","Boom 300 Index",
    "Crash 1000 Index","Crash 500 Index","Crash 300 Index",
]
JUMP_SYMBOLS = [
    "Jump 10 Index","Jump 25 Index","Jump 50 Index",
    "Jump 75 Index","Jump 100 Index",
]
STEP_RANGE_SYMBOLS = [
    "Step Index","Range Break 100 Index","Range Break 200 Index",
]

# ── STRATEGY PARAMETERS ──────────────────────────────────────
EMA_FAST  = 8
EMA_SLOW  = 21
EMA_TREND = 200

RSI_PERIOD     = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD   = 30

BB_PERIOD = 20
BB_STD    = 2.0

ATR_PERIOD        = 14
ATR_SL_MULTIPLIER = 1.5   # SL = 1.5 × ATR
ATR_TP_MULTIPLIER = 3.0   # TP = 3.0 × ATR  (1:2 risk-reward)

LOOKBACK_CANDLES = 300

# ── BOT OPERATION ────────────────────────────────────────────
SCAN_INTERVAL_SECONDS = 60
MAGIC_NUMBER          = 20240101
TRADE_COMMENT         = "TradingBot_v1"

# Master switch: when False, bot still scans markets and logs signals
# but will NOT open any new trades.  Existing open trades continue to
# be managed (peak-drawdown lock, breakeven, trailing SL, profit
# protection, early exit) so positions don't go unwatched.
# Live setting — toggling from the web UI takes effect instantly,
# no restart required.
TRADING_ENABLED = True

# ── WEB UI ───────────────────────────────────────────────────
WEB_UI_ENABLED = True
WEB_UI_PORT    = 4000


# ─────────────────────────────────────────────────────────────
# Load setting overrides from SQLite database (set via web UI)
# This lets you change settings from the browser without editing
# this file.  Credentials and symbols stay here for safety.
# ─────────────────────────────────────────────────────────────
def _load_db_overrides():
    try:
        import database as _db
        _db.init_db()
        overrides = _db.get_all_settings()
        g = globals()
        for key, value in overrides.items():
            if key in g:           # only override keys that exist
                g[key] = value
        # Recompute derived value after overrides
        g["MAX_OPEN_TRADES"] = (
            g.get("MAX_OPEN_TRADES_DEMO", 25)
            if "demo" in g.get("MT5_SERVER", "").lower()
            else g.get("MAX_OPEN_TRADES_LIVE", 10)
        )
    except Exception:
        pass   # on any error, fall back to defaults above

_load_db_overrides()
