@echo off
echo 🚀 啟動 Smart Factory Monitoring System...

REM 啟動虛擬環境
call .venv\Scripts\activate

REM 啟動伺服器 (背景執行)
start uvicorn app:app --reload

echo ✅ 伺服器已啟動，請開啟 http://127.0.0.1:8000
pause
