@echo off
echo 🛑 停止 Smart Factory Monitoring System...

REM 關閉所有 uvicorn 進程
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo ✅ 伺服器已停止
pause
