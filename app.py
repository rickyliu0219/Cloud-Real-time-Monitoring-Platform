from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, and_
import datetime as dt
from collections import defaultdict

from database import Base, engine, get_db
from models import EquipmentMetric, Equipment

app = FastAPI(title="雲端智慧工廠監控平台")
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 關掉 /static 快取，確保每次取到最新 JS/CSS
@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---------- 首頁 ----------
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---------- 健康檢查 ----------
@app.get("/api/health")
def health():
    return {"ok": True}

# 最近告警（預設 12 小時內）
@app.get("/api/alerts")
def api_alerts(hours: int = Query(12, ge=1, le=168), db: Session = Depends(get_db)):
    since = dt.datetime.utcnow() - dt.timedelta(hours=hours)
    events, _ = build_error_events_and_windows(db, since)
    return {"events": events[:20]}  # 只回前 20 筆最新

# 維修紀錄（預設 24 小時內）
@app.get("/api/maintenance")
def api_maintenance(hours: int = Query(24, ge=1, le=168), db: Session = Depends(get_db)):
    since = dt.datetime.utcnow() - dt.timedelta(hours=hours)
    _, windows = build_error_events_and_windows(db, since)
    return {"records": windows}


# ========== 內部小工具 ==========
#設台灣當地時間更新當日產量數據
def taipei_midnight_utc_naive() -> dt.datetime:
    """回傳『台灣當地今日 00:00』換算成 UTC 的 naive datetime"""
    tz_taipei = dt.timezone(dt.timedelta(hours=8))
    today_local = dt.datetime.now(tz_taipei).replace(hour=0, minute=0, second=0, microsecond=0)
    return today_local.astimezone(dt.timezone.utc).replace(tzinfo=None)

def build_series(rows):
    """
    rows: [(equipment_id, ts, production)]
    回傳：
      items_total: 依 ts 加總的序列（升冪）
      items_by_equipment: 每台設備自己的序列（升冪）
    """
    total_by_ts = defaultdict(int)
    per_eqp = defaultdict(list)
    for eid, ts, prod in rows:
        total_by_ts[ts] += int(prod)
        per_eqp[eid].append({"ts": ts.isoformat(), "production": int(prod)})

    # 依時間排序
    ts_sorted = sorted(total_by_ts.keys())
    items_total = [{"ts": t.isoformat(), "production": total_by_ts[t]} for t in ts_sorted]
    items_by_equipment = [{"equipment_id": eid, "points": pts} for eid, pts in per_eqp.items()]
    return items_total, items_by_equipment

def fetch_recent_ticks(db: Session, ticks: int = 120, eqp_guess: int = 8):
    """
    取最近 N 個 tick（不看時間）。每個 tick 會有『設備數量』筆資料，
    所以先抓 ticks*eqp_guess，再在程式內排序＆組裝。
    """
    limit_rows = ticks * eqp_guess
    raw = (
        db.query(
            EquipmentMetric.equipment_id,
            EquipmentMetric.ts,
            EquipmentMetric.production
        )
        .order_by(desc(EquipmentMetric.ts))
        .limit(limit_rows)
        .all()
    )
    rows = list(reversed(raw))  # 升冪
    return build_series(rows)

def build_error_events_and_windows(db: Session, since: dt.datetime):
    """
    從 EquipmentMetric(ts,status) 偵測：
      - 事件：ERROR_START / ERROR_END
      - 維修區段：start_ts, end_ts, duration_sec
    僅掃描 since 之後資料；若 since 之前已在 ERROR，中斷點以 since 為近似 start。
    """
    # since 前最後狀態（判斷是否已在 ERROR）
    subq_prev = (
        db.query(
            EquipmentMetric.equipment_id,
            func.max(EquipmentMetric.ts).label("ts")
        )
        .filter(EquipmentMetric.ts < since)
        .group_by(EquipmentMetric.equipment_id)
        .subquery()
    )
    prev_rows = (
        db.query(EquipmentMetric.equipment_id, EquipmentMetric.status)
        .join(subq_prev,
              and_(EquipmentMetric.equipment_id == subq_prev.c.equipment_id,
                   EquipmentMetric.ts == subq_prev.c.ts))
        .all()
    )
    prev_status = {eid: st for eid, st in prev_rows}

    # since 之後的序列
    rows = (
        db.query(EquipmentMetric.equipment_id, EquipmentMetric.ts, EquipmentMetric.status)
        .filter(EquipmentMetric.ts >= since)
        .order_by(EquipmentMetric.equipment_id.asc(), EquipmentMetric.ts.asc())
        .all()
    )

    events = []   # [{equipment_id, type, ts}]
    windows = []  # [{equipment_id, start_ts, end_ts, duration_sec, ongoing}]
    now = dt.datetime.utcnow()
    curr_err_start = {}  # eid -> start_ts
    last_seen_status = prev_status.copy()

    # 若 since 時已在 ERROR，視為自 since 開始
    for eid, st in prev_status.items():
        if st == "ERROR":
            curr_err_start[eid] = since

    # 掃描狀態變化
    for eid, ts, st in rows:
        prev = last_seen_status.get(eid)
        if prev != "ERROR" and st == "ERROR":
            curr_err_start[eid] = ts
            events.append({"equipment_id": eid, "type": "ERROR_START", "ts": ts.isoformat()})
        elif prev == "ERROR" and st != "ERROR":
            if eid in curr_err_start:
                start = curr_err_start[eid]
                end = ts
                duration = int((end - start).total_seconds())
                windows.append({
                    "equipment_id": eid,
                    "start_ts": start.isoformat(),
                    "end_ts": end.isoformat(),
                    "duration_sec": duration,
                    "ongoing": False
                })
                del curr_err_start[eid]
            events.append({"equipment_id": eid, "type": "ERROR_END", "ts": ts.isoformat()})
        last_seen_status[eid] = st

    # 還在 ERROR 中 → 進行中
    for eid, start in curr_err_start.items():
        duration = int((now - start).total_seconds())
        windows.append({
            "equipment_id": eid,
            "start_ts": start.isoformat(),
            "end_ts": None,
            "duration_sec": duration,
            "ongoing": True
        })

    events.sort(key=lambda x: x["ts"], reverse=True)
    windows.sort(key=lambda x: x["start_ts"], reverse=True)
    return events, windows


# ---------- KPI 摘要（台灣午夜起算 + 加總全部設備；無資料時做友善回退） ----------
@app.get("/api/summary")
def get_summary(db: Session = Depends(get_db)):
    """
    當日產量（台灣 0:00 起算、即時更新）：
    若尚未跨 UTC 午夜：    daily = latest_>=S - last_<S
    若已跨過 UTC 午夜：    daily = (last_<U - last_<S) + latest_>=U
      其中 S 為台灣 0:00（轉 UTC），U 為「今天的 UTC 午夜」。
    """
    S = taipei_midnight_utc_naive()           # 台灣 0:00 -> UTC naive
    now_utc = dt.datetime.utcnow()
    U = dt.datetime(now_utc.year, now_utc.month, now_utc.day)  # 今天 UTC 午夜（naive）

    # ---- 取設備清單（沒有資料的設備也要計入 0）----
    eq_ids = [e.equipment_id for e in db.query(Equipment).all()]

    # ---- 共同子查詢工具：取某一「區間的邊界點」----
    def last_before(ts_cut):
        """回傳 {eid: production_at_last_ts_before_cut}"""
        subq = (
            db.query(
                EquipmentMetric.equipment_id,
                func.max(EquipmentMetric.ts).label("ts")
            )
            .filter(EquipmentMetric.ts < ts_cut)
            .group_by(EquipmentMetric.equipment_id)
            .subquery()
        )
        rows = (
            db.query(EquipmentMetric.equipment_id, EquipmentMetric.production)
            .join(
                subq,
                and_(
                    EquipmentMetric.equipment_id == subq.c.equipment_id,
                    EquipmentMetric.ts == subq.c.ts,
                ),
            )
            .all()
        )
        return {eid: int(prod) for eid, prod in rows}

    def latest_after(ts_cut):
        """回傳 {eid: production_at_latest_ts_after_or_equal_cut}"""
        subq = (
            db.query(
                EquipmentMetric.equipment_id,
                func.max(EquipmentMetric.ts).label("ts")
            )
            .filter(EquipmentMetric.ts >= ts_cut)
            .group_by(EquipmentMetric.equipment_id)
            .subquery()
        )
        rows = (
            db.query(EquipmentMetric.equipment_id, EquipmentMetric.production)
            .join(
                subq,
                and_(
                    EquipmentMetric.equipment_id == subq.c.equipment_id,
                    EquipmentMetric.ts == subq.c.ts,
                ),
            )
            .all()
        )
        return {eid: int(prod) for eid, prod in rows}

    # ---- 取各邊界值 ----
    before_S = last_before(S)          # 台灣日開始前的基準
    latest_ge_S = latest_after(S)      # 台灣日開始後目前最新

    crossed_utc_midnight = now_utc >= U  # 是否已跨過 UTC 午夜

    if not crossed_utc_midnight:
        # 未跨 UTC 午夜：同一個 UTC 天內，直接差值
        daily_total = 0
        for eid in eq_ids:
            curr = latest_ge_S.get(eid, None)
            base = before_S.get(eid, 0)
            inc = max(0, (curr - base)) if curr is not None else 0
            daily_total += inc
    else:
        # 已跨 UTC 午夜：分兩段累加
        before_U = last_before(U)      # UTC 午夜前最後一筆
        latest_ge_U = latest_after(U)  # UTC 午夜後目前最新（已從 0 累積）

        partA = 0  # S~U 之間的增量 = last_<U - last_<S
        partB = 0  # U~now 的增量 = latest_>=U （因為 UTC 日重置為 0）
        for eid in eq_ids:
            a = max(0, before_U.get(eid, 0) - before_S.get(eid, 0))
            b = max(0, latest_ge_U.get(eid, 0))
            partA += a
            partB += b
        daily_total = partA + partB

    # 其它 KPI：沿用最新一筆
    latest = db.query(EquipmentMetric).order_by(desc(EquipmentMetric.ts)).first()

    return {
        "dailyProduction": int(daily_total),
        "efficiency": round(latest.efficiency, 2) if latest else 0,
        "status": latest.status if latest else "N/A",
        "activeEquipment": 1 if latest and latest.status == "RUN" else 0,
        "totalEquipment": db.query(Equipment).count(),
        "updatedAt": dt.datetime.utcnow().isoformat(),
    }

# ---------- 產量趨勢（總量 + 各機；realtime 忽略時間；其他範圍查不到則回退） ----------
@app.get("/api/metrics")
def get_metrics(
    range: str = Query("realtime", description="範圍: realtime, 5m, 1h, 1d, 1mo"),
    db: Session = Depends(get_db)
):
    now = dt.datetime.utcnow()

    # ✅ realtime：取最近 60 筆（約 5 分鐘，TICK=5s）
    if range == "realtime":
        items_total, items_by_equipment = fetch_recent_ticks(db, ticks=60, eqp_guess=12)
        if not items_total:
            return {"items": [{"ts": now.isoformat(), "production": 0}],
                    "items_total": [{"ts": now.isoformat(), "production": 0}],
                    "items_by_equipment": []}
        return {"items": items_total, "items_total": items_total, "items_by_equipment": items_by_equipment}

    # 其他時間窗：用 since 過濾；若為空則回退到最近 N 個 tick
    if range == "5m":
        since = now - dt.timedelta(minutes=5)
    elif range == "1h":
        since = now - dt.timedelta(hours=1)
    elif range == "1d":
        since = now - dt.timedelta(days=1)
    elif range == "1mo":
        since = now - dt.timedelta(days=30)
    else:
        since = now - dt.timedelta(minutes=5)

    filtered = (
        db.query(
            EquipmentMetric.equipment_id,
            EquipmentMetric.ts,
            EquipmentMetric.production
        )
        .filter(EquipmentMetric.ts >= since)
        .order_by(EquipmentMetric.ts.asc())
        .all()
    )
    if filtered:
        items_total, items_by_equipment = build_series(filtered)
    else:
        # 回退
        items_total, items_by_equipment = fetch_recent_ticks(db, ticks=120, eqp_guess=12)

    if not items_total:
        return {"items": [{"ts": now.isoformat(), "production": 0}],
                "items_total": [{"ts": now.isoformat(), "production": 0}],
                "items_by_equipment": []}

    return {"items": items_total, "items_total": items_total, "items_by_equipment": items_by_equipment}

# ---------- 設備 CRUD ----------
@app.get("/api/equipment")
def get_equipment(db: Session = Depends(get_db)):
    return db.query(Equipment).all()

@app.post("/api/equipment")
def add_equipment(equip: dict, db: Session = Depends(get_db)):
    new_e = Equipment(equipment_id=equip["equipment_id"])
    db.add(new_e)
    db.commit()
    db.refresh(new_e)
    return new_e

@app.put("/api/equipment/{equip_id}")
def update_equipment(equip_id: int, equip: dict, db: Session = Depends(get_db)):
    e = db.query(Equipment).filter(Equipment.id == equip_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="設備不存在")
    e.equipment_id = equip["equipment_id"]
    db.commit()
    db.refresh(e)
    return e

@app.delete("/api/equipment/{equip_id}")
def delete_equipment(equip_id: int, db: Session = Depends(get_db)):
    e = db.query(Equipment).filter(Equipment.id == equip_id).first()
    if not e:
        raise HTTPException(status_code=404, detail="設備不存在")
    db.delete(e)
    db.commit()
    return {"ok": True}
