"""
SQLite database — stores settings, signals, and trades for the web UI.
Auto-creates schema on first run.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "bot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL,
    type   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS signals (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT DEFAULT (datetime('now')),
    symbol    TEXT,
    direction TEXT,
    strength  REAL,
    strategy  TEXT,
    action    TEXT,   -- 'taken' or 'skipped'
    reason    TEXT
);

CREATE TABLE IF NOT EXISTS trades (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket       INTEGER UNIQUE,
    symbol       TEXT,
    direction    TEXT,
    lot          REAL,
    open_price   REAL,
    sl           REAL,
    tp           REAL,
    open_time    TEXT DEFAULT (datetime('now')),
    close_time   TEXT,
    close_price  REAL,
    profit       REAL,
    status       TEXT DEFAULT 'open',
    strategy     TEXT,
    close_reason TEXT
);

CREATE TABLE IF NOT EXISTS control (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_signals_time ON signals(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
"""


@contextmanager
def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)


# ── Settings ──────────────────────────────────────────────────

def get_setting(key: str, default=None):
    with _conn() as c:
        row = c.execute("SELECT value, type FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return default

    val, typ = row["value"], row["type"]
    if typ == "int":   return int(val)
    if typ == "float": return float(val)
    if typ == "bool":  return val.lower() == "true"
    if typ == "list":  return [x for x in val.split(",") if x]
    return val


def set_setting(key: str, value):
    if isinstance(value, bool):    typ = "bool"
    elif isinstance(value, int):   typ = "int"
    elif isinstance(value, float): typ = "float"
    elif isinstance(value, list):  typ = "list"; value = ",".join(value)
    else:                          typ = "string"

    with _conn() as c:
        c.execute("""INSERT INTO settings (key, value, type) VALUES (?, ?, ?)
                     ON CONFLICT(key) DO UPDATE SET value=excluded.value, type=excluded.type""",
                  (key, str(value), typ))


def get_all_settings() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT key, value, type FROM settings").fetchall()
    out = {}
    for r in rows:
        val, typ = r["value"], r["type"]
        if typ == "int":   out[r["key"]] = int(val)
        elif typ == "float": out[r["key"]] = float(val)
        elif typ == "bool":  out[r["key"]] = val.lower() == "true"
        elif typ == "list":  out[r["key"]] = [x for x in val.split(",") if x]
        else:                out[r["key"]] = val
    return out


# ── Signals ───────────────────────────────────────────────────

def log_signal(symbol: str, direction: str, strength: float,
               strategy: str, action: str, reason: str = ""):
    with _conn() as c:
        c.execute("""INSERT INTO signals
                     (symbol, direction, strength, strategy, action, reason)
                     VALUES (?, ?, ?, ?, ?, ?)""",
                  (symbol, direction, strength, strategy, action, reason))


def get_recent_signals(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""SELECT * FROM signals ORDER BY id DESC LIMIT ?""",
                          (limit,)).fetchall()
    return [dict(r) for r in rows]


def trim_signals(keep_last: int = 2000):
    with _conn() as c:
        c.execute("""DELETE FROM signals WHERE id NOT IN
                     (SELECT id FROM signals ORDER BY id DESC LIMIT ?)""",
                  (keep_last,))


# ── Trades ────────────────────────────────────────────────────

def log_trade_open(ticket: int, symbol: str, direction: str, lot: float,
                    open_price: float, sl: float, tp: float, strategy: str):
    with _conn() as c:
        c.execute("""INSERT OR REPLACE INTO trades
                     (ticket, symbol, direction, lot, open_price, sl, tp, strategy, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
                  (ticket, symbol, direction, lot, open_price, sl, tp, strategy))


def log_trade_close(ticket: int, close_price: float, profit: float,
                    status: str, reason: str = ""):
    with _conn() as c:
        c.execute("""UPDATE trades
                     SET close_time = datetime('now'),
                         close_price = ?, profit = ?, status = ?, close_reason = ?
                     WHERE ticket = ?""",
                  (close_price, profit, status, reason, ticket))


def update_trade_sl_tp(ticket: int, sl: float = None, tp: float = None):
    with _conn() as c:
        if sl is not None:
            c.execute("UPDATE trades SET sl = ? WHERE ticket = ?", (sl, ticket))
        if tp is not None:
            c.execute("UPDATE trades SET tp = ? WHERE ticket = ?", (tp, ticket))


def get_all_trades(limit: int = 200) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM trades ORDER BY id DESC LIMIT ?",
                          (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_open_trades() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM trades WHERE status = 'open' ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


# ── Control flags ─────────────────────────────────────────────

def set_restart_flag():
    with _conn() as c:
        c.execute("""INSERT INTO control (key, value) VALUES ('restart', 'true')
                     ON CONFLICT(key) DO UPDATE SET value='true'""")


def consume_restart_flag() -> bool:
    with _conn() as c:
        row = c.execute("SELECT value FROM control WHERE key='restart'").fetchone()
        if row and row["value"] == "true":
            c.execute("UPDATE control SET value='false' WHERE key='restart'")
            return True
    return False
