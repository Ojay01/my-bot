============================================================
  TRADING BOT — QUICK START GUIDE
  Deriv MT5 | Multi-Symbol | 24/7 | Python
============================================================

REQUIREMENTS
  - Windows VPS (required for MT5 Python library)
  - Python 3.10 or newer  →  https://www.python.org/downloads/
  - MetaTrader 5 installed and logged in at least once
  - Deriv MT5 account (real or demo)

------------------------------------------------------------
STEP 1 — Install Python
  Download from python.org, run installer.
  IMPORTANT: Tick "Add Python to PATH" during install.

STEP 2 — Install bot packages
  Double-click:  setup.bat
  Wait for it to finish.

STEP 3 — Edit your credentials
  Open:  config.py  (right-click → Open with Notepad)

  Change these three lines:
    MT5_LOGIN    = 12345678        ← your account number
    MT5_PASSWORD = "YourPassword"  ← your MT5 password
    MT5_SERVER   = "Deriv-Server"  ← find this in MT5 login screen

  To find your server name:
    Open MT5 → File → Open an Account → look at the server list
    Common values: "Deriv-Demo"  "Deriv-Server"

STEP 4 — (Optional) Adjust settings
  In config.py you can also:
  - Change RISK_PERCENT (default 1% — recommended for small accounts)
  - Comment out symbols you don't want to trade (add # before the line)
  - Set PROFIT_TARGET_USD to your goal (default $50)

STEP 5 — Start the bot
  Double-click:  start.bat
  The bot will print its activity in the console window.

------------------------------------------------------------
FILES EXPLAINED
  config.py       ← YOUR settings (edit this)
  main.py         ← Bot engine (do not edit)
  trades.csv      ← Auto-created log of all trades
  bot.log         ← Auto-created activity log
  strategies/     ← Trading strategy files

------------------------------------------------------------
STRATEGIES USED
  1. EMA Crossover (8/21 EMA + RSI filter + 200 EMA trend)
     Best for: Forex + Volatility indices
     Timeframe: M15

  2. RSI + Bollinger Bands (mean-reversion)
     Best for: All symbols
     Timeframe: M15

  3. Boom/Crash Spike Reversal
     Best for: Boom 1000, Crash 1000
     Timeframe: M1

------------------------------------------------------------
RISK MANAGEMENT
  - 1% of balance risked per trade (e.g. $0.10 on $10 account)
  - Maximum 5 trades open at once
  - Daily loss limit: 5% (bot stops trading for the day)
  - Break-even stop: SL moved to open price after 1R profit
  - Only 1 trade per symbol at a time

------------------------------------------------------------
STOPPING THE BOT
  Press Ctrl+C in the console window.
  All open trades remain open in MT5 (you can close them manually).

------------------------------------------------------------
HOSTING ON VPS 24/7
  1. Get a Windows VPS (e.g. Contabo, Vultr, AWS Lightsail)
  2. Install Python + MT5 on the VPS
  3. Copy this entire folder to the VPS
  4. Run setup.bat once, then start.bat
  5. To keep running after you close the window:
     - Use Windows Task Scheduler, OR
     - Run:  pythonw main.py  (runs in background, no window)

============================================================
