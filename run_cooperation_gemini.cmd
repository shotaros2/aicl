@echo off
rem Double-click to run the Gemini cooperation demo. Reads the API key from .env.
cd /d "%~dp0"
chcp 65001 >nul
python examples\cooperation_gemini.py %*
echo.
pause
