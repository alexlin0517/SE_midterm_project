"""
資料庫連線與 Session 管理模組 (db.py)
職責：負責 PostgreSQL 資料庫連線設定、SQLAlchemy Session 建立與 Model 基礎類別 (Base) 宣告。
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ==============================================================================
# 【重要提醒 / NOTICE】
# 請依據您的 PostgreSQL 資料庫環境設定修改下方的連線字串：
# 格式：postgresql://<帳號>:<密碼>@<主機位址>:<連接埠>/<資料庫名稱>
# 範例：postgresql://postgres:your_password@localhost:5432/manuscript_db
# 請務必確認該資料庫已在 PostgreSQL 中建立（例如：CREATE DATABASE manuscript_db;）
# ==============================================================================
DATABASE_URL = "postgresql://postgres:xup6m4fu6@localhost:5432/manuscript_db"

# 建立 SQLAlchemy Engine
# pool_pre_ping=True 可自動檢查連線有效性，若連線中斷會自動重連
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# 建立 SessionLocal 類別，供每次 HTTP 請求產生獨立 Session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 宣告 ORM Model 的 Base 類別
Base = declarative_base()


def get_db():
    """
    FastAPI 依賴注入 (Dependency Injection) 使用的資料庫 Session 產生器。
    確保每個請求皆有獨立的 Session，並在請求結束後自動關閉釋放資源。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
