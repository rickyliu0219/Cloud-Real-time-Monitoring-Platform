# Smart Factory Monitoring System  
智慧工廠雲端即時監控平台  

## 📖 專案介紹 | Project Overview
這是一個基於 **FastAPI + SQLite + Chart.js** 的雲端監控平台，  
能夠即時顯示生產數據、設備狀態、告警訊息，並提供設備清單的 **新增 / 編輯 / 刪除** 功能。  

This project is a cloud-based monitoring platform built with **FastAPI + SQLite + Chart.js**,  
providing real-time monitoring of production data, equipment status, alerts,  
and CRUD functions (add/edit/delete) for equipment management.  

---

## ⚡ 功能特色 | Features
- 📊 **即時數據**：顯示今日產量、效率、設備狀態  
- 📈 **折線圖表**：產量趨勢隨時間變化  
- 🔔 **即時告警**：設備異常時即時提示  
- 🛠️ **設備清單 CRUD**：新增、編輯、刪除設備  
- 💾 **SQLite 持久化**：資料存入資料庫，刷新頁面不會消失  

---

## 🚀 快速開始 | Quick Start

1️⃣ 安裝環境 | Setup Environment
```bash
# 建立虛擬環境
python -m venv .venv

# 啟動虛擬環境 (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# 安裝依賴
pip install -r requirements.txt

2️⃣ 啟動伺服器 | Run Server

有兩種方式：

(a) 手動
uvicorn app:app --reload

(b) 一鍵啟動 / 停止

start.bat → 啟動伺服器

stop.bat → 停止伺服器

📂 專案結構 | Project Structure
Smart-Factory-Monitoring-System/
│
├─ app.py              # 主程式 FastAPI
├─ models.py           # 資料庫模型
├─ database.py         # 資料庫連線
├─ simulator.py        # 模擬數據產生器
├─ requirements.txt    # 依賴套件
├─ start.bat           # 一鍵啟動
├─ stop.bat            # 一鍵停止
│
├─ templates/
│   └─ index.html      # 前端 HTML 模板
│
├─ static/
│   └─ main.js         # 前端 JavaScript
│
└─ database.db         # SQLite 資料庫 (執行後產生)

📊產生虛擬數據 | Generate Virtual Data:
開新視窗啟動 venv 後執行：
python simulator.py


👤 作者 | Author

禹寬 (YU KUAN)
📧 Email: U1222342@o365.nuu.edu.tw
