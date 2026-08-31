# =============================================================
#  TRADING BOT — CONFIGURATION FILE
#  Edit this file with your details before starting the bot
# =============================================================

# ── MT5 LOGIN CREDENTIALS ────────────────────────────────────
MT5_LOGIN    = 32384683          # Your Deriv MT5 account number (integer)
MT5_PASSWORD = "Amene&4Sons"   # Your MT5 password
MT5_SERVER   = "Deriv-Demo"   # Server name shown in your MT5 app
                                 # e.g. "Deriv-Demo" or "Deriv-Server"

# ── RISK SETTINGS ────────────────────────────────────────────
RISK_PERCENT     = 1.0   # % of balance risked per trade (1% recommended)
DAILY_LOSS_LIMIT = 5.0   # Stop trading today if daily loss hits this %
                         # (checked against EQUITY, so open losses count)
# ── PROFIT TARGET (percent of starting capital) ──────────────
# Goal: grow the account by this %.  $100 capital + 50% = $150 target.
# Starting capital is recorded automatically the first time the bot runs
# on an account.  All targets scale with whatever you deposit.
PROFIT_TARGET_PERCENT = 50.0

# Don't be greedy — account level.  Once the target has been PASSED, the
# bot tracks the account's peak equity; if equity gives back this % from
# that peak, it CLOSES ALL TRADES and stops opening new ones.
# Example: capital $100, target $150, equity runs to $300 (peak), then
# falls 15% to $255 -> everything is closed, profit locked in.
ACCOUNT_GIVEBACK_PERCENT = 15.0

# Hard cap on the TOTAL amount at risk at once: the combined loss if
# every open trade hit its SL may not exceed this % of balance.
# Per-trade sizing alone doesn't stop many small risks stacking up.
MAX_TOTAL_OPEN_RISK_PERCENT = 5.0

# Max open trades — more on demo for testing, fewer on live for safety
MAX_OPEN_TRADES_DEMO = 10
MAX_OPEN_TRADES_LIVE = 5
MAX_OPEN_TRADES = MAX_OPEN_TRADES_DEMO if "demo" in MT5_SERVER.lower() else MAX_OPEN_TRADES_LIVE

# Max trades allowed on a SINGLE pair.  1 = one position per symbol —
# no averaging into losers, which is how small accounts die.
MAX_TRADES_PER_SYMBOL = 1

# Cooldown: after a trade closes on a symbol, wait this many minutes
# before opening another there.  Stops instant re-entry into the same
# zone right after a loss.  0 = disabled.
SYMBOL_COOLDOWN_MINUTES = 30

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
PEAK_DRAWDOWN_PERCENT            = 15.0   # close when profit falls this % from its peak
PEAK_DRAWDOWN_MIN_PROFIT_PCT     = 0.5    # arm only once peak profit >= this % of balance
                                          # (percent-based so it scales with account size)

# Breakeven safety lock — the "no losses after profits" rule.
# Once a trade's peak profit reaches BREAKEVEN_LOCK_AFTER_PROFIT_USD,
# the bot will FORCE CLOSE it the moment profit falls to $0 or below.
# This guarantees a profitable trade never closes at a loss, regardless
# of where the broker's stop-loss is.  Last-resort safety net behind
# the peak-drawdown lock.
BREAKEVEN_LOCK_ENABLED          = True
BREAKEVEN_LOCK_AFTER_PROFIT_PCT = 0.5   # % of balance — arm once profit reaches this

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

# ── SPREAD COST GUARD (account-size aware) ───────────────────
# Different from SPREAD_FILTER above: this checks the actual DOLLAR cost
# of opening a trade (spread × lot × tick value) against the account
# balance.  Boom/Volatility synthetics can have entry spread costs that
# exceed your planned 1% risk, silently wiping small accounts.
# Default cap = 2% of balance.  On a $10k demo this rarely triggers;
# on a $20 real account it correctly blocks wide-spread synthetics
# until the account grows.
SPREAD_COST_GUARD_ENABLED = True
MAX_SPREAD_COST_PERCENT   = 2.0   # skip trade if entry spread cost > X% of balance

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
    "Volatility 10 Index",
    "Volatility 25 Index",
    "Volatility 50 Index",
    "Volatility 75 Index",
    "Volatility 100 Index",
    "Volatility 10 (1s) Index",
    "Volatility 25 (1s) Index",
    "Volatility 50 (1s) Index",
    "Volatility 75 (1s) Index",
    "Volatility 100 (1s) Index",

    # --- Boom & Crash Indices (Deriv — spike reversal strategy) ---
    # Only Boom 1000 is whitelisted for Spike_Reversal (see
    # STRATEGY_SYMBOL_RULES) — the others were scanned every cycle but
    # every signal was dropped, so they're disabled to save time.
    "Boom 1000 Index",
    # "Boom 500 Index",
    # "Boom 300 Index",
    # "Crash 1000 Index",
    # "Crash 500 Index",
    # "Crash 300 Index",

    # --- Jump Indices (Deriv — sudden jumps both directions) ---
    # Same: only Jump 25 / Jump 50 are whitelisted for Spike_Reversal.
    # "Jump 10 Index",
    "Jump 25 Index",
    "Jump 50 Index",
    # "Jump 75 Index",
    # "Jump 100 Index",

    # --- Step & Range Break Indices (Deriv) ---
    "Step Index",
    "Range Break 100 Index",
    "Range Break 200 Index",
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

# ── STRATEGY-SYMBOL WHITELIST ────────────────────────────────
# Derived from real performance data: each strategy is only allowed to
# fire on the symbols it has actually been profitable on.  Signals on
# any other symbol are silently dropped before reaching the trade engine.
# Use ["*"] to allow a strategy on all symbols.
STRATEGY_WHITELIST_ENABLED = True
STRATEGY_SYMBOL_RULES = {
    # Spike_Reversal: profitable on Boom 1000 (+$493). Marginal on Jump 25/50.
    # Loses heavily on Crash variants and Boom 500/300.
    "Spike_Reversal": [
        "Boom 1000 Index",
        "Jump 25 Index",
        "Jump 50 Index",
    ],

    # SMC: clean structure works on Forex, Metals, and calm synthetics.
    # Has lost heavily on Volatility 75/100 (whipsaw structure).
    "SMC": [
        # Forex
        "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
        "GBPJPY", "EURJPY", "EURGBP", "GBPAUD", "AUDJPY",
        # Metals
        "XAUUSD", "XAGUSD",
        # Calm synthetics where SMC has been profitable
        "Step Index", "Range Break 100 Index", "Range Break 200 Index",
        "Volatility 10 Index", "Volatility 25 Index",
        "Volatility 25 (1s) Index",
    ],

    # EMA_Crossover & RSI_Bollinger: 100% win rate in history — quality
    # filter is built-in (signal strength + agreement check). No restriction.
    "EMA_Crossover": ["*"],
    "RSI_Bollinger": ["*"],
}

# ── PER-STRATEGY PROTECTION OVERRIDES ────────────────────────
# SMC trades develop slowly and need room to breathe.  Default 25%
# drawdown / $1 breakeven thresholds close them at $5 average win,
# while losses run to full SL ($43 avg).  Looser thresholds let
# winners develop into bigger gains.
LOCK_OVERRIDES_BY_STRATEGY = {
    "SMC": {
        "PEAK_DRAWDOWN_PERCENT":           25.0,   # vs default 15 — needs room
        "PEAK_DRAWDOWN_MIN_PROFIT_PCT":    1.0,    # vs default 0.5 (% of balance)
        "BREAKEVEN_LOCK_AFTER_PROFIT_PCT": 1.0,    # vs default 0.5 (% of balance)
        "MAX_TP_EXTENSIONS":               3,      # vs default 1 — let it ride
    },
}

# ── ENTRY CONFIRMATION (momentum candle) ──────────────────────
# Require the most recently CLOSED candle to confirm the signal direction
# before opening.  BUY signals need a bullish closed candle; SELL needs
# bearish.  Filters out noise entries where the bot reacts to a
# half-formed pattern that immediately reverses.
ENTRY_CONFIRMATION_ENABLED = True

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
