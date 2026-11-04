@echo off
rem Double-click to run the read-back evaluation on Gemini (first 10 messages). Reads the API key from .env.
cd /d "%~dp0"
chcp 65001 >nul
python evals\readback.py --provider gemini --model gemini-3.5-flash-lite --limit 10 --sleep 6 --out evals\results\gemini-latest.json %*
echo.
pause
