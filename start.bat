@echo off
set HOST=127.0.0.1
set PORT=8000

echo  Starting Smart Factory Monitoring System (public)...
for /l %%i in (3,-1,1) do (
  echo Starting in %%i...
  ping -n 2 127.0.0.1 >nul
)

REM activate venv
call .venv\Scripts\activate

REM start uvicorn in background
start "" cmd /c "uvicorn app:app --host %HOST% --port %PORT% --reload"

REM wait a moment for the server to boot
ping -n 4 127.0.0.1 >nul

REM check cloudflared
where cloudflared >nul 2>&1
if errorlevel 1 (
  echo ❗ cloudflared not found. Install with: winget install Cloudflare.cloudflared
  pause
  exit /b 1
)

echo 🌐 Opening public tunnel... keep this window open.
echo Shareable URL will appear below (https://xxxxx.trycloudflare.com):
cloudflared tunnel --url http://%HOST%:%PORT%
