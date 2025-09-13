# Smart Factory Monitoring System

---

## 1️⃣ 安裝環境 | Setup Environment

### Windows (PowerShell)
在專案資料夾打開 PowerShell (建議直接進到 `Cloud-monitoring-platform/`)

```powershell
# 建立虛擬環境
python -m venv .venv

# 啟動虛擬環境
.\.venv\Scripts\Activate.ps1

# 安裝依賴
pip install -r requirements.txt
````

⚠️ **PowerShell 執行政策限制**
如果出現「無法載入檔案 … Activate.ps1」，執行以下指令（只需一次）：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

---

### Mac / Linux (Bash / zsh)

```bash
# 進入專案資料夾
cd Smart-Factory-Monitoring-System

# 建立虛擬環境
python3 -m venv .venv

# 啟動虛擬環境
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt
```

---

## 2️⃣ 啟動伺服器 | Run Server

### (a) 手動啟動

```bash
uvicorn app:app --reload
```

### (b) 一鍵啟動 / 停止 (僅限 Windows)

```text
start.bat → 啟動伺服器
stop.bat  → 停止伺服器
```

---

## 3️⃣ 產生虛擬數據 | Generate Virtual Data

開新終端機，啟動 venv 後執行：

```bash
python simulator.py
```

---

## 4️⃣ 外網分享 | Public Access (Cloudflare Tunnel)

若要讓老師/同學從外網直接連線，可使用 **Cloudflare Tunnel**。

### Windows

安裝 cloudflared（只需一次）：

```powershell
winget install --id Cloudflare.cloudflared -e
```

啟動公開連線：

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

執行後會產生一個網址，例如：

```
https://xxxx-xxxx-xxxx.trycloudflare.com
```

把這個網址分享給對方即可。
⚠️ 注意：cmd視窗要保持開啟，網址是臨時的，每次啟動會更換。

---

## 📂 專案結構 | Project Structure

```
Smart-Factory-Monitoring-System/
│
├─ app.py              # 主程式 FastAPI
├─ models.py           # 資料庫模型
├─ database.py         # 資料庫連線
├─ simulator.py        # 模擬數據產生器
├─ requirements.txt    # 依賴套件
├─ start.bat           # 一鍵啟動 (Windows)
├─ stop.bat            # 一鍵停止 (Windows)
│
├─ templates/
│   └─ index.html      # 前端 HTML 模板
│
├─ static/
│   └─ main.js         # 前端 JavaScript
│
└─ database.db         # SQLite 資料庫 (執行後產生)
```

---

## 👤 作者 | Author

禹寬 (YU KUAN)
📧 Email: [U1222342@o365.nuu.edu.tw](mailto:U1222342@o365.nuu.edu.tw)

```
