from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# SQLite 檔案在專案根目錄
SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"

# check_same_thread=False 讓多執行緒安全地共享連線（FastAPI + 背景執行）
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# FastAPI 依賴：每請求產生一個 DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
