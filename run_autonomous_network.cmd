@echo off
rem Double-click to start the autonomous AICL network (Claude editor, Gemini fact checker,
rem live weather, artist, publishing desk). Needs ANTHROPIC_API_KEY and GEMINI_API_KEY in .env.
rem After it starts nobody gives it input; to stop it early, create the file out
etwork\STOP.
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python examplesutonomous_network.py %*
echo.
echo Published page and transcript are in the out
etwork folder.
start "" "%~dp0out
etwork"
pause
