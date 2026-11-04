@echo off
rem Double-click to upload dist/* to PyPI. Reads PYPI_TOKEN from .env; never prints it.
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONUTF8=1
python tools\pypi_upload.py %*
echo.
pause
