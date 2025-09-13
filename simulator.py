import time, random, datetime as dt
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
from models import EquipmentMetric

# 確保表存在
Base.metadata.create_all(bind=engine)

# 模擬狀態機（RUN 機率高）
def random_status():
    r = random.random()
    if r < 0.75:
        return "RUN"
    elif r < 0.92:
        return "IDLE"
    else:
        return "ERROR"

production = 0

print("Simulator started. Generating a row every 5 seconds...")

while True:
    with SessionLocal() as db:  # type: Session
        # 產量在 RUN 狀態才成長，IDLE/ERROR 成長較慢或不動
        st = random_status()
        inc = {
            "RUN": random.randint(5, 15),
            "IDLE": random.randint(0, 3),
            "ERROR": 0
        }[st]
        production += inc

        metric = EquipmentMetric(
            equipment_id="M1",
            status=st,
            production=production,
            efficiency=round(random.uniform(0.70, 0.95), 2),
            ts=dt.datetime.utcnow()
        )
        db.add(metric)
        db.commit()

        print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {st:<5} prod={production}")
    time.sleep(5)
