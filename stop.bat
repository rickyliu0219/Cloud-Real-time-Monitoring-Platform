@echo off
echo 🛑 Stopping Smart Factory Monitoring System...

REM Kill all uvicorn processes
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1

echo ✅ Server has been stopped
exit
