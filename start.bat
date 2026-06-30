@echo off
echo ============================================
echo   Quant Trading System - Starting Services
echo ============================================
echo.

cd /d "%~dp0"

:: ---- Check prerequisites ---------------------------------
echo [1/3] Checking prerequisites...

python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found. Please install Python 3.9+.
    pause & exit /b 1
)
python --version

node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js not found. Please install Node.js 18+.
    pause & exit /b 1
)
node --version

:: ---- Install backend dependencies ------------------------
echo.
echo [2/3] Installing backend dependencies...
cd /d "%~dp0backend"
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] pip install failed. Trying with --user...
    pip install -r requirements.txt --user
)
echo   Backend deps installed.

:: ---- Install frontend dependencies -----------------------
echo.
echo Installing frontend dependencies...
cd /d "%~dp0frontend"

:: Test both vite AND rollup (npm bug can leave rollup broken)
node -e "require('vite');require('rollup')" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   Frontend deps broken or missing. Removing and reinstalling...
    rmdir /s /q node_modules 2>nul
    del package-lock.json 2>nul
    call npm install
) else (
    echo   Frontend deps OK, skipping install.
)

cd /d "%~dp0"

:: ---- Stop existing processes on target ports -------------
echo.
echo [3/3] Stopping existing processes and starting services...
powershell -Command "$c=Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object {$_.OwningProcess -gt 0}; if($c){$c|ForEach-Object{Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue;Write-Host '  Stopped port 8000 PID:'$_.OwningProcess}}"
powershell -Command "$c=Get-NetTCPConnection -LocalPort 8888 -ErrorAction SilentlyContinue | Where-Object {$_.OwningProcess -gt 0}; if($c){$c|ForEach-Object{Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue;Write-Host '  Stopped port 8888 PID:'$_.OwningProcess}}"

:: ---- Launch backend (python -m uvicorn, not bare uvicorn) --
start "Quant-Backend" /D "%~dp0backend" cmd /k "title Quant Backend :8000 && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: ---- Launch frontend -------------------------------------
start "Quant-Frontend" /D "%~dp0frontend" cmd /k "title Quant Frontend :8888 && npm run dev"

echo   Waiting for services to start...
timeout /t 6 /nobreak >nul

echo.
echo ============================================
echo   Quant Trading System Ready!
echo.
echo   Frontend:   http://localhost:8888
echo   Backend:    http://localhost:8000
echo   API Docs:   http://localhost:8000/api/docs
echo.
echo   Accounts: admin/admin123  demo/demo123
echo.
echo   Close the two popup windows or run stop.bat
echo ============================================
echo.
pause
