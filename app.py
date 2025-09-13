from fastapi import FastAPI, Depends, Request, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import datetime as dt

from database import Base, engine, get_db
from models import EquipmentMetric, Equipment

app = FastAPI(title="雲端智慧工廠監控平台")
Base.metadata.create_all(bind=engine)

# 靜態檔與模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ---- 首頁 ----
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ---- 健康檢查 ----
@app.get("/api/health")
def health():
    return {"ok": True}


# ---- KPI 摘要 ----
@app.get("/api/summary")
def get_summary(db: Session = Depends(get_db)):
    latest = db.query(EquipmentMetric).order_by(desc(EquipmentMetric.ts)).first()

    today_start = dt.datetime.utcnow().date()
    today_start_dt = dt.datetime.combine(today_start, dt.time.min)
    today_total = (
        db.query(func.max(EquipmentMetric.production))
          .filter(EquipmentMetric.ts >= today_start_dt)
          .scalar()
        or 0
    )

    return {
        "dailyProduction": today_total,
        "efficiency": round(latest.efficiency, 2) if latest else 0,
        "status": latest.status if latest else "N/A",
        "activeEquipment": 1 if latest and latest.status == "RUN" else 0,
        "totalEquipment": db.query(Equipment).count(),
    }


# ---- 產量趨勢（含「即時」與各時間窗；無資料時回退最近 60 筆）----
@app.get("/api/metrics")
def get_metrics(
    range: str = Query("realtime", description="範圍: realtime, 5m, 1h, 1d, 1mo"),
    db: Session = Depends(get_db)
):
    """
    realtime：取最近 60 筆（不看時間）
    其他時間窗：用 ts 過濾；若無資料，回退到最近 60 筆，避免圖表空白。
    回傳結果為「時間遞增」，方便前端畫線。
    """
    now = dt.datetime.utcnow()
    base_q = db.query(EquipmentMetric)

    def to_items(rows):
        return [{
            "ts": m.ts.isoformat(),
            "equipment_id": m.equipment_id,
            "production": m.production,
            "efficiency": m.efficiency,
            "status": m.status
        } for m in rows]

    if range == "realtime":
        rows = base_q.order_by(desc(EquipmentMetric.ts)).limit(60).all()
        if not rows:
            # 絕對沒有資料時回一筆安全的假資料
            return {"items": [{
                "ts": now.isoformat(),
                "equipment_id": "M1",
                "production": 0,
                "efficiency": 0.9,
                "status": "RUN"
            }]}
        return {"items": to_items(list(reversed(rows)))}

    # 時間窗過濾
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

    rows = base_q.filter(EquipmentMetric.ts >= since).order_by(desc(EquipmentMetric.ts)).all()

    # 若該時間窗沒有資料，回退最近 60 筆，讓圖仍有線
    if not rows:
        fallback = base_q.order_by(desc(EquipmentMetric.ts)).limit(60).all()
        if not fallback:
            return {"items": [{
                "ts": now.isoformat(),
                "equipment_id": "M1",
                "production": 0,
                "efficiency": 0.9,
                "status": "RUN"
            }]}
        return {"items": to_items(list(reversed(fallback)))}

    return {"items": to_items(list(reversed(rows)))}


# ---- 設備 CRUD ----
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
