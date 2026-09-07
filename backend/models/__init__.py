"""Aeon 数据模型：8 张业务表，全部带 user_id（多用户预留）"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
import enum
from db import Base  # db.py 在 backend 根目录


class Platform(str, enum.Enum):
    weixin = "weixin"
    feishu = "feishu"
    both = "both"


class HabitType(str, enum.Enum):
    check = "check"      # 勾选打卡
    cnt = "count"        # 计数打卡（Enum 内 count 与内置冲突）
    val = "value"        # 数值打卡（Enum 内 value 与内置冲突）


class WishLevel(str, enum.Enum):
    want = "want"        # 想要
    need = "need"        # 需要
    wait = "wait"        # 观望


class MediaType(str, enum.Enum):
    book = "book"
    movie = "movie"
    series = "series"
    music = "music"


class MediaStatus(str, enum.Enum):
    want = "want"        # 想看
    doing = "doing"      # 进行中
    done = "done"        # 已完成


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)  # PBKDF2-SHA256 哈希（services.auth.hash_password）
    is_admin = Column(Boolean, default=False)
    invite_code = Column(String, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)


class Ledger(Base):
    __tablename__ = "ledger"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    date = Column(String, nullable=False)          # YYYY-MM-DD
    type = Column(String, nullable=False)          # income / expense
    amount = Column(Float, nullable=False)
    category = Column(String, default="其他")
    note = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Habit(Base):
    __tablename__ = "habits"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    htype = Column(SAEnum(HabitType), default=HabitType.check)
    target = Column(Float, default=1)              # count/value 的目标值
    unit = Column(String, default="")              # 单位（次/杯/分钟）
    created_at = Column(DateTime, default=datetime.utcnow)


class HabitLog(Base):
    __tablename__ = "habit_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    habit_id = Column(Integer, ForeignKey("habits.id"), nullable=False, index=True)
    date = Column(String, nullable=False)          # YYYY-MM-DD
    value = Column(Float, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScheduleEvent(Base):
    __tablename__ = "schedule_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    date = Column(String, nullable=False)          # YYYY-MM-DD
    time = Column(String, default="")              # HH:MM
    priority = Column(Integer, default=1)          # 0/1/2 → P0/P1/P2
    done = Column(Boolean, default=False)
    repeat = Column(String, default="")            # daily / weekly / monthly / ""
    created_at = Column(DateTime, default=datetime.utcnow)


class Wish(Base):
    __tablename__ = "wishes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    level = Column(SAEnum(WishLevel), default=WishLevel.want)
    note = Column(String, default="")
    bought = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    bought_at = Column(String, default=None)


class MediaItem(Base):
    __tablename__ = "media_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    mtype = Column(SAEnum(MediaType), nullable=False)
    status = Column(SAEnum(MediaStatus), default=MediaStatus.want)
    rating = Column(Integer, default=0)            # 1-5
    comment = Column(String, default="")
    cover = Column(String, default="")             # 封面 URL 或空（渐变占位）
    book_id = Column(Integer, nullable=True)       # 关联书架 Book.id（同步用）
    created_at = Column(DateTime, default=datetime.utcnow)


class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    author = Column(String, default="")
    source = Column(String, default="upload")      # upload / search / serial
    file_path = Column(String, default="")         # 服务端存储路径
    cover = Column(String, default="")
    total_chapters = Column(Integer, default=0)
    current_chapter = Column(Integer, default=1)
    position = Column(Float, default=0)            # 章节内进度 0-100
    created_at = Column(DateTime, default=datetime.utcnow)


class BookChapter(Base):
    __tablename__ = "book_chapters"
    id = Column(Integer, primary_key=True, autoincrement=True)
    book_id = Column(Integer, ForeignKey("books.id"), nullable=False, index=True)
    idx = Column(Integer, nullable=False)          # 章节序号（从 1 起）
    title = Column(String, default="")
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
