@echo off
echo  Stopping server and tunnel...
taskkill /F /IM cloudflared.exe >nul 2>&1
taskkill /F /IM uvicorn.exe >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
echo  Stopped.
exit