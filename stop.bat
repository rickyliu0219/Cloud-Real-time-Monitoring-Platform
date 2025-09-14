@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ===== Go to project root (this .bat location) =====
pushd "%~dp0"

echo ===============================================
echo  Stopping API Server, Simulator, and Public Tunnel
echo ===============================================

REM --- 1) 先用視窗標題關閉（最精準） ---
REM 會關掉由 start "API Server"/"Simulator"/"Public Tunnel (cloudflared)" 開的視窗
powershell -NoProfile -ExecutionPolicy Bypass ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$titles=@('API Server','Simulator','Public Tunnel (cloudflared)');" ^
  "Get-Process | Where-Object { $titles -contains $_.MainWindowTitle } | ForEach-Object { Stop-Process -Id $_.Id -Force }"

REM --- 2) 保險：關掉 cloudflared.exe（若仍存在） ---
taskkill /IM cloudflared.exe /F >nul 2>&1

REM --- 3) 保險：砍掉執行 uvicorn / simulator.py 的 Python 行程 ---
powershell -NoProfile -ExecutionPolicy Bypass ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'uvicorn\s+app:app') -or ($_.CommandLine -match 'simulator\.py') };" ^
  "foreach($p in $procs){ try{ Stop-Process -Id $p.ProcessId -Force }catch{}}"

REM --- 4) 最後：釋放 :8000 連接埠（如果還被佔用） ---
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
  taskkill /PID %%P /F >nul 2>&1
)

echo Done. Closing this window...
REM 稍等 1 秒讓訊息看得到
ping -n 2 127.0.0.1 >nul

popd
exit
