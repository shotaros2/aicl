@echo off
rem Double-click to let Claude (@a) and Meta Muse Spark (@b) negotiate a signed agreement.
rem Needs ANTHROPIC_API_KEY and MODEL_API_KEY in .env (see .env.example).
cd /d "%~dp0"
chcp 65001 >nul
python examples\contract_dialogue.py --b muse %*
echo.
pause
