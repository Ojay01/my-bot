"""
Session Filter — controls WHEN the bot trades.

Forex and Metals are only liquid during active market sessions.
Trading during dead hours (e.g. Sunday night, late Asian session for
European pairs) means wide spreads, choppy price, and unreliable signals.

Deriv Synthetic Indices trade 24/7 and are NOT affected by this filter.

Sessions (UTC):
  Asian    : 00:00 – 09:00   (JPY pairs most active)
  London   : 07:00 – 16:00   (GBP, EUR most active)
  New York : 12:00 – 21:00   (USD pairs most active)
  Overlap  : 12:00 – 16:00   ← highest volume, best signals
"""

from datetime import datetime, timezone, timedelta
import config


def _current_utc_hour() -> int:
    return datetime.now(timezone.utc).hour


def _current_utc_time() -> datetime:
    return datetime.now(timezone.utc)


def in_session(session: str) -> bool:
    hour = _current_utc_hour()
    if session == "LONDON":
        return config.LONDON_START <= hour < config.LONDON_END
    if session == "NEW_YORK":
        return config.NEW_YORK_START <= hour < config.NEW_YORK_END
    if session == "ASIAN":
        return config.ASIAN_START <= hour < config.ASIAN_END
    return False


def can_trade_forex() -> bool:
    """Returns True if we are inside at least one allowed session."""
    if not config.SESSION_FILTER_ENABLED:
        return True
    return any(in_session(s) for s in config.ALLOWED_SESSIONS)


def is_news_blackout() -> bool:
    """
    Returns True if we are within NEWS_BLACKOUT_MINUTES of a scheduled
    high-impact news event.  Only blocks Forex/Metals — synthetics run through.
    """
    if not config.NEWS_FILTER_ENABLED:
        return False
    if not config.NEWS_EVENTS_UTC:
        return False

    now     = _current_utc_time()
    window  = timedelta(minutes=config.NEWS_BLACKOUT_MINUTES)

    for event_str in config.NEWS_EVENTS_UTC:
        try:
            event_time = datetime.strptime(event_str, "%Y-%m-%d %H:%M")
            event_time = event_time.replace(tzinfo=timezone.utc)
            if abs(now - event_time) <= window:
                return True
        except ValueError:
            continue

    return False


def can_trade_symbol(symbol: str) -> tuple[bool, str]:
    """
    Returns (allowed, reason).
    Synthetics always return (True, "").
    Forex/Metals check session + news blackout.
    """
    is_forex  = symbol in config.FOREX_SYMBOLS
    is_metal  = symbol in config.METAL_SYMBOLS

    if not is_forex and not is_metal:
        return True, ""   # synthetic — always allowed

    if is_news_blackout():
        return False, "news blackout"

    if not can_trade_forex():
        active = [s for s in config.ALLOWED_SESSIONS if in_session(s)]
        return False, f"outside session (active={active or 'none'})"

    return True, ""


def current_session_info() -> str:
    active = [s for s in ["LONDON", "NEW_YORK", "ASIAN"] if in_session(s)]
    hour   = _current_utc_hour()
    return f"{hour:02d}:xx UTC | active sessions: {active if active else ['CLOSED']}"
