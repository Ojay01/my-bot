@echo off
title Trading Bot
echo ============================================
echo  Trading Bot Starting...
echo  Press Ctrl+C to stop
echo ============================================
echo.

:loop
echo [%date% %time%] Starting bot...
python main.py
echo.
echo [%date% %time%] Bot stopped. Restarting in 10 seconds...
echo (Press Ctrl+C to cancel restart)
timeout /t 10
goto loop
