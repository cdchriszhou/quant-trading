@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo   Quant Trading - Build for Production
echo ============================================
echo.

:: ---- Prerequisites -----------------------------------------
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Install Python 3.9+ and add to PATH.
    pause
    exit /b 1
)

where npm >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] npm not found. Install Node.js 18+ and add to PATH.
    pause
    exit /b 1
)

python --version
call npm --version
echo.

:: ---- Build -------------------------------------------------
python build.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Build failed. See messages above.
    pause
    exit /b 1
)

echo.
echo Build succeeded. Upload the zip + quant-update.sh to the server.
pause
exit /b 0
