"""Aeon 数据库配置：SQLAlchemy 引擎 + 会话管理"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# DB 路径：backend/../data/aeon.db（项目自包含，位于 aeon/data/）
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aeon.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db():
    """FastAPI 依赖：请求级数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
