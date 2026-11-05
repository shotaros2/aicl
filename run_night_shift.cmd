@echo off
rem Double-click to run the AICL night shift now: the AI team works through out\night\inbox
rem (one task per .txt file) and writes a report. Needs GEMINI_API_KEY in .env.
rem To run it every night instead: powershell -ExecutionPolicy Bypass -File tools\install_night_shift.ps1
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
if not exist "out\night\inbox" mkdir "out\night\inbox"
python -X utf8 examples\night_shift.py %*
echo.
echo The report is in the newest folder under out\night.
start "" "%~dp0out\night"
pause
