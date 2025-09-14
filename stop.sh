#!/bin/bash

# 關閉 uvicorn
pkill -f "uvicorn app:app"

# 關閉 simulator.py
pkill -f "simulator.py"

# 關閉 cloudflared（如果有開）
pkill -f "cloudflared"

echo "All processes stopped."