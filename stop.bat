@echo off
echo ============================================
echo   Quant Trading System - Stopping Services
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] Stopping backend (port 8000)...
powershell -Command "$c=Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Where-Object {$_.OwningProcess -gt 0}; if($c){$c|ForEach-Object{Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue;Write-Host '  Stopped PID:'$_.OwningProcess}}else{Write-Host '  No process on port 8000.'}"

echo.
echo [2/2] Stopping frontend (port 8888)...
powershell -Command "$c=Get-NetTCPConnection -LocalPort 8888 -ErrorAction SilentlyContinue | Where-Object {$_.OwningProcess -gt 0}; if($c){$c|ForEach-Object{Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue;Write-Host '  Stopped PID:'$_.OwningProcess}}else{Write-Host '  No process on port 8888.'}"

echo.
echo ============================================
echo   Services stopped.
echo ============================================
timeout /t 2 /nobreak >nul
