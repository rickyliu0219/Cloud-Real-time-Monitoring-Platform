# simulator.py
# 事件驅動、產線模擬：Poisson 故障/待機、MTBF/MTTR、班別倍率、報廢率、個體差異
import time
import random
import datetime as dt

from typing import Dict
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import EquipmentMetric, Equipment

# ====== 可調參數 ======
TICK_SECONDS = 5                       # 每幾秒產生一批資料
DEFAULT_EQUIP_IDS = ["M1", "M2", "M3", "M4"]

BASE_MEAN_UNITS = 10                   # RUN 狀態下平均產量
BASE_STD_UNITS  = 3                    # RUN 產量波動（波動大小）
RECOVERY_BOOST  = 1.35                 # 故障/待機剛恢復的瞬間加成（一次）

# 故障/待機行為（每台機器會各自抽樣不同參數，增加異質性）
MTBF_HOURS_RANGE            = (8, 24)        # 平均故障間隔（小時）→ 值越大故障越少
MTTR_MINUTES_RANGE          = (2, 8)         # 平均修復時間（分鐘）
IDLE_MEAN_INTERVAL_MIN_RANGE= (20, 60)       # 平均待機間隔（分鐘）
IDLE_DURATION_SEC_RANGE     = (20, 120)      # 待機持續秒數
SCRAP_RATE_RANGE            = (0.02, 0.10)   # 報廢率

RANDOM_SEED = None  # 若要可重現，改成數字例如 42

# ====== 內部狀態 ======
# 每台設備都有獨立狀態與排程的下一次事件時間
# mode: RUN/IDLE/ERROR
# until: 當前狀態結束的時間 (IDLE/ERROR 才會有)
# next_fail_at: 下一次故障開始的時間（只在 RUN 下會觸發）
# next_idle_at: 下一次待機開始的時間（只在 RUN 下會觸發）
# factor: 機器個體產能差異 0.85~1.15
# params: 該機器的 MTBF/MTTR/IDLE 間隔（秒）

STATE: Dict[str, Dict] = {} # 用來記錄每台設備的當前狀態

if RANDOM_SEED is not None:
    random.seed(RANDOM_SEED)

Base.metadata.create_all(bind=engine)

# 用「指數分布」抽樣，模擬「隨機事件間隔」（像故障）。
def exp_sample(mean_seconds: float) -> float:
    """指數分佈抽樣（平均 mean_seconds）"""
    if mean_seconds <= 0:
        mean_seconds = 1
    return random.expovariate(1.0 / mean_seconds)

def shift_multiplier(now_utc: dt.datetime) -> float:
    """簡易班別倍率（UTC 時間近似）：凌晨/深夜低、午餐低、白天高"""
    h = now_utc.hour
    if 0 <= h < 7:  return 0.6  # 凌晨產量少
    if 7 <= h < 12: return 1.0  # 白天正常
    if 12 <= h < 13:return 0.4  # 午餐休息
    if 13 <= h < 18:return 1.0  # 下午正常
    if 18 <= h < 22:return 0.8  # 晚班稍低
    return 0.6                  # 深夜再降低

#模擬班別不同的產能差異
def ensure_equipments(db: Session):     
    # 確保 DB 裡有設備 M1~M4，沒有的話自動建立
    existing = {e.equipment_id for e in db.query(Equipment).all()}
    for eid in DEFAULT_EQUIP_IDS:
        if eid not in existing:
            db.add(Equipment(equipment_id=eid, status="RUN", production=0, efficiency=0.9))
    db.commit()

def last_prod_today(db: Session, eid: str, now_utc: dt.datetime) -> int:    
    # 查詢今天該機器的最後一筆生產數量，避免累積數據歸零  
    start_of_day = dt.datetime.combine(now_utc.date(), dt.time.min)
    last = (
        db.query(EquipmentMetric)
          .filter(EquipmentMetric.equipment_id == eid,
                  EquipmentMetric.ts >= start_of_day)
          .order_by(EquipmentMetric.ts.desc())
          .first()
    )
    return last.production if last else 0

def init_state_for(eid: str, now: dt.datetime):
    if eid in STATE:
        return
    mtbf_s   = random.uniform(*MTBF_HOURS_RANGE) * 3600.0
    mttr_s   = random.uniform(*MTTR_MINUTES_RANGE) * 60.0
    idle_int = random.uniform(*IDLE_MEAN_INTERVAL_MIN_RANGE) * 60.0

    STATE[eid] = {
        "mode": "RUN",
        "until": None,
        "recovery_boost": False,
        "factor": random.uniform(0.85, 1.15),
        "params": {
            "mtbf_s": mtbf_s,
            "mttr_s": mttr_s,
            "idle_mean_interval_s": idle_int
        },
        "next_fail_at": now + dt.timedelta(seconds=exp_sample(mtbf_s)),
        "next_idle_at": now + dt.timedelta(seconds=exp_sample(idle_int)),
    }

# ====== 核心一步 ======
def step_one_equipment(db: Session, eid: str, now: dt.datetime):
    init_state_for(eid, now)
    st = STATE[eid]

    # 狀態期滿 → 回 RUN 並給一次性恢復加成
    if st["mode"] in ("ERROR", "IDLE") and st["until"] and now >= st["until"]:
        st["mode"] = "RUN"
        st["until"] = None
        st["recovery_boost"] = True

    # RUN 下才會觸發下一個事件（故障或待機）
    if st["mode"] == "RUN":
        # 故障觸發
        if now >= st["next_fail_at"]:
            st["mode"] = "ERROR"
            dur = max(5, exp_sample(st["params"]["mttr_s"]))  # MTTR 指數分佈
            st["until"] = now + dt.timedelta(seconds=dur)
            # 下一次故障重新排程（修好之後再算）
            st["next_fail_at"] = st["until"] + dt.timedelta(seconds=exp_sample(st["params"]["mtbf_s"]))
        # 待機觸發（若同一個瞬間同時到，優先 ERROR；未 ERROR 才可能 IDLE）
        elif now >= st["next_idle_at"]:
            st["mode"] = "IDLE"
            dur = random.randint(*IDLE_DURATION_SEC_RANGE)
            st["until"] = now + dt.timedelta(seconds=dur)
            # 下一次待機重新排程（待機結束之後再算）
            st["next_idle_at"] = st["until"] + dt.timedelta(seconds=exp_sample(st["params"]["idle_mean_interval_s"]))

    # 計算產量 & 效率
    base = max(0, int(random.gauss(BASE_MEAN_UNITS, BASE_STD_UNITS)))
    base = base * shift_multiplier(now) * st["factor"]

    if st["mode"] == "ERROR":
        produced = 0
        eff = random.uniform(0.05, 0.2)
    elif st["mode"] == "IDLE":
        produced = int(base * 0.12)   # 待機近乎不產出
        eff = random.uniform(0.45, 0.7)
    else:
        produced = int(base)
        if st["recovery_boost"]:
            produced = int(produced * RECOVERY_BOOST)
            st["recovery_boost"] = False
        eff = random.uniform(0.86, 0.98)

    # 報廢
    scrap = random.uniform(*SCRAP_RATE_RANGE)
    produced = int(round(produced * (1 - scrap)))

    # 今日累積
    new_total = last_prod_today(db, eid, now) + produced

    # 寫入 metrics
    m = EquipmentMetric(
        equipment_id=eid,
        production=new_total,
        efficiency=round(eff, 2),
        status=st["mode"],
        ts=now
    )
    db.add(m)

    # 更新 equipment 表
    e = db.query(Equipment).filter(Equipment.equipment_id == eid).first()
    if e:
        e.production = new_total
        e.efficiency = round(eff, 2)
        e.status = st["mode"]

    return produced, st["mode"], eff, new_total


def generate_batch():
    now = dt.datetime.utcnow()
    db: Session = SessionLocal()
    try:
        ensure_equipments(db)
        lines = []
        for eid in DEFAULT_EQUIP_IDS:
            prod, mode, eff, total = step_one_equipment(db, eid, now)
            lines.append(f"{eid}:{mode} +{prod} (eff={eff:.2f}, total={total})")
        db.commit()
        print(f"[{now.strftime('%H:%M:%S')}] " + " | ".join(lines))
    finally:
        db.close()


if __name__ == "__main__":
    print("🚀 模擬器啟動（Poisson 故障、隨機待機、班別倍率、報廢、個體差異）...")
    while True:
        generate_batch()
        time.sleep(TICK_SECONDS)



