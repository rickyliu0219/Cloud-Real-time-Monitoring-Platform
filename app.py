from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import datetime as dt

from database import Base, engine, get_db
from models import EquipmentMetric, Equipment

app = FastAPI(title="雲端即時監控平台")
Base.metadata.create_all(bind=engine)

# 靜態與模板
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ---- 頁面 ----
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# ---- 健康檢查 ----
@app.get("/api/health")
def health():
    return {"ok": True}

# ---- 摘要 KPI ----
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

# ---- 最近 N 筆數據 ----
@app.get("/api/metrics")
def get_metrics(limit: int = 60, db: Session = Depends(get_db)):
    q = (
        db.query(EquipmentMetric)
          .order_by(desc(EquipmentMetric.ts))
          .limit(limit)
          .all()
    )
    items = [
        {
            "ts": m.ts.isoformat(),
            "equipment_id": m.equipment_id,
            "production": m.production,
            "efficiency": m.efficiency,
            "status": m.status
        }
        for m in reversed(q)
    ]
    return {"items": items}

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
