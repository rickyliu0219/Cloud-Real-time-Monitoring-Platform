import datetime as dt
from sqlalchemy import Column, Integer, String, Float, DateTime
from database import Base

# 生產數據 (歷史資料)
class EquipmentMetric(Base):
    __tablename__ = "metrics"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, index=True, nullable=False)
    status = Column(String, nullable=False)
    production = Column(Integer, nullable=False)
    efficiency = Column(Float, nullable=False)
    ts = Column(DateTime, default=dt.datetime.utcnow, index=True)

# 設備清單 (持久化 CRUD)
class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(String, nullable=False)
    status = Column(String, default="RUN")
    production = Column(Integer, default=0)
    efficiency = Column(Float, default=0.9)
