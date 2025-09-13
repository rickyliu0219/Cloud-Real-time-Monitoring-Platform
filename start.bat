@echo off
echo 🚀 Starting Smart Factory Monitoring System...

REM Countdown 3 seconds
echo Server will start in 3 seconds...
ping -n 2 127.0.0.1 >nul
echo 2...
ping -n 2 127.0.0.1 >nul
echo 1...
ping -n 2 127.0.0.1 >nul

REM Activate virtual environment
call .venv\Scripts\activate

REM Start server in a new window and close current CMD
start "" uvicorn app:app --reload

echo ✅ Server is running at http://127.0.0.1:8000
exit
