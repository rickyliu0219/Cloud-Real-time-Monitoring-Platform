#!/bin/bash

# 進到腳本所在目錄
cd "$(dirname "$0")"

PYTHON=".venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
  echo "[ERROR] Virtual environment not found: $PYTHON"
  echo "Create it first: python3 -m venv .venv"
  echo "Activate:       source .venv/bin/activate"
  echo "Install deps:   pip install -r requirements.txt"
  exit 1
fi

HOST=127.0.0.1
PORT=8000

echo "==============================================="
echo " Smart Factory Monitoring System - Starter (Mac)"
echo " API + Simulator will launch"
echo "==============================================="
echo "Starting in 3 seconds..."
sleep 3

# 啟動 API Server
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd); $PYTHON -m uvicorn app:app --host $HOST --port $PORT --reload\""

# 啟動 Simulator
osascript -e "tell application \"Terminal\" to do script \"cd $(pwd); $PYTHON simulator.py\""

echo "API Server running at: http://$HOST:$PORT"