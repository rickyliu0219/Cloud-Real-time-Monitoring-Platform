@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ===== Go to project root (this .bat location) =====
pushd "%~dp0"

REM ===== venv python (no need to activate) =====
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo [ERROR] Virtual environment not found: "%PYTHON%"
  echo Create it first:  python -m venv .venv
  echo Activate:         .\.venv\Scripts\Activate.ps1
  echo Install deps:     pip install -r requirements.txt
  pause
  exit /b 1
)

set "HOST=127.0.0.1"
set "PORT=8000"
set PYTHONUNBUFFERED=1

echo ===============================================
echo  Smart Factory Monitoring System - Public Start
echo  API + Simulator + Cloudflare Tunnel (auto)
echo ===============================================

echo Starting in 3 seconds...
for /l %%i in (3,-1,1) do ( echo %%i... & ping -n 2 127.0.0.1 >nul )

REM ===== Detect arch & prepare cloudflared URL =====
set "ARCH=%PROCESSOR_ARCHITECTURE%"
if defined PROCESSOR_ARCHITEW6432 set "ARCH=%PROCESSOR_ARCHITEW6432%"
REM normalize
if /I "!ARCH!"=="AMD64"  set "CFFILE=cloudflared-windows-amd64.exe"
if /I "!ARCH!"=="ARM64"  set "CFFILE=cloudflared-windows-arm64.exe"
if /I "!ARCH!"=="x86"    set "CFFILE=cloudflared-windows-386.exe"
if not defined CFFILE    set "CFFILE=cloudflared-windows-amd64.exe"

set "CFURL=https://github.com/cloudflare/cloudflared/releases/latest/download/!CFFILE!"
echo [CF] Detected arch: !ARCH!
echo [CF] Binary file   : !CFFILE!
echo [CF] From          : !CFURL!

REM ===== Ensure cloudflared.exe exists (auto-download if missing) =====
if not exist "cloudflared.exe" (
  echo [CF] cloudflared.exe not found, downloading...

  REM --- Try PowerShell Invoke-WebRequest (TLS1.2) ---
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$ErrorActionPreference='SilentlyContinue';" ^
    "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;" ^
    "Invoke-WebRequest -Uri '!CFURL!' -OutFile 'cloudflared.exe' -UseBasicParsing" >nul 2>&1

  if not exist "cloudflared.exe" (
    echo [CF] PowerShell IWR failed, trying BITS...
    REM --- Try BITS (may be disabled on some systems) ---
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$ErrorActionPreference='SilentlyContinue';" ^
      "Import-Module BitsTransfer -ErrorAction SilentlyContinue; Start-BitsTransfer -Source '!CFURL!' -Destination 'cloudflared.exe' -ErrorAction SilentlyContinue" >nul 2>&1
  )

  if not exist "cloudflared.exe" (
    echo [CF] BITS failed, trying curl...
    curl -L -o cloudflared.exe "!CFURL!" 2>nul
  )

  if not exist "cloudflared.exe" (
    echo [CF] curl failed, trying certutil...
    certutil -urlcache -split -f "!CFURL!" cloudflared.exe >nul 2>&1
  )

  if not exist "cloudflared.exe" (
    echo [CF][ERROR] Unable to download cloudflared.exe.
    echo        Check your network/proxy or manually download:
    echo        !CFURL!
    pause
    exit /b 1
  )

  for %%A in ("cloudflared.exe") do set "CF_SIZE=%%~zA"
  if "!CF_SIZE!"=="0" (
    echo [CF][ERROR] Downloaded file is empty. Please try again or download manually:
    echo        !CFURL!
    del /f /q cloudflared.exe >nul 2>&1
    pause
    exit /b 1
  )
  echo [CF] Downloaded cloudflared.exe (size: !CF_SIZE! bytes)
)

REM ===== Launch API & Simulator in new windows =====
start "API Server" "%PYTHON%" -m uvicorn app:app --host %HOST% --port %PORT% --reload
start "Simulator"  "%PYTHON%" simulator.py

REM ===== Start Cloudflare Tunnel =====
set "CF_LOG=%TEMP%\cloudflared_%RANDOM%.log"
echo [CF] Starting Cloudflare Tunnel...
start "Public Tunnel (cloudflared)" cloudflared.exe tunnel --url http://%HOST%:%PORT% --logfile "%CF_LOG%" --loglevel info

echo [CF] Waiting for public URL (up to 60s)...
set "PUBLIC_URL="
for /L %%s in (1,1,60) do (
  for /f "usebackq tokens=* delims=" %%L in (`findstr /i "trycloudflare.com" "%CF_LOG%"`) do (
    set "LINE=%%L"
    for %%W in (!LINE!) do (
      echo %%W | findstr /I "https://.*trycloudflare.com" >nul && set "PUBLIC_URL=%%W"
    )
  )
  if defined PUBLIC_URL goto :found_cf
  timeout /t 1 >nul
)

:found_cf
echo.
echo ===============================================
if defined PUBLIC_URL (
  echo  Public URL: !PUBLIC_URL!
) else (
  echo  Public URL not detected yet.
  echo  Please check the "Public Tunnel (cloudflared)" window
  echo  or the log: %CF_LOG%
)
echo  Local API:  http://%HOST%:%PORT%
echo ===============================================

popd
exit /b
