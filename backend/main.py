"""
Aeon — 个人管家后端
FastAPI + SQLite + APScheduler + JWT + WebSocket
"""

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import jwt
import json
import os
import enum

# ─── Config ─────────────────────────────
SECRET_KEY = os.getenv("AEON_SECRET", "aeon-dev-secret-change-me")
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "aeon.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
ADMIN_USERNAME = "Y"
VALID_INVITE_CODES = {"AEON-2026", "ZERO-DEGREE", "PHILOSOPHY-144"}

# ─── Database ───────────────────────────
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine)

class Platform(str, enum.Enum):
    weixin = "weixin"
    feishu = "feishu"
    both = "both"

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    due_at = Column(DateTime, nullable=False)
    platform = Column(String, default="both")
    done = Column(Boolean, default=False)
    created_by = Column(String, default="Y")
    created_at = Column(DateTime, default=datetime.utcnow)

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    cron_expr = Column(String, nullable=False)
    platform = Column(String, default="both")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# ─── App ───────────────────────────────
app = FastAPI(title="Aeon", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Schemas ───────────────────────────
class TodoCreate(BaseModel):
    title: str
    due_at: str  # ISO format
    platform: str = "both"

class ScheduleCreate(BaseModel):
    title: str
    cron_expr: str
    platform: str = "both"

class LoginRequest(BaseModel):
    username: str
    password: str
    invite_code: str = None  # 非管理员注册必填

# ─── Auth ──────────────────────────────
def create_token(username: str, is_admin: bool = False) -> str:
    exp = datetime.utcnow() + timedelta(days=30 if is_admin else 1)
    return jwt.encode({"sub": username, "admin": is_admin, "exp": exp}, SECRET_KEY, algorithm="HS256")

def get_user(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "未登录")
    try:
        payload = jwt.decode(authorization[7:], SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效凭证")

def require_admin(user: dict = Depends(get_user)):
    if not user.get("admin"):
        raise HTTPException(403, "需要管理员权限")
    return user

# ─── DB helper ──────────────────────────
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# ─── Auth Routes ────────────────────────
@app.post("/api/login")
def login(body: LoginRequest):
    if body.username == ADMIN_USERNAME:
        return {"token": create_token(body.username, is_admin=True), "admin": True, "username": body.username}
    if not body.invite_code or body.invite_code not in VALID_INVITE_CODES:
        raise HTTPException(403, "邀请码无效")
    if not body.password:
        raise HTTPException(400, "需要设置密码")
    return {"token": create_token(body.username, is_admin=False), "admin": False, "username": body.username}

@app.get("/api/me")
def me(user: dict = Depends(get_user)):
    return {"username": user["sub"], "admin": user.get("admin", False)}

# ─── Todo Routes ────────────────────────
@app.get("/api/todos")
def list_todos(db: Session = Depends(get_db), user: dict = Depends(get_user)):
    q = db.query(Todo).filter(Todo.done == False)
    if not user.get("admin"):
        q = q.filter(Todo.created_by == user["sub"])
    return [{"id": t.id, "title": t.title, "due_at": t.due_at.isoformat(), "platform": t.platform, "done": t.done} for t in q.order_by(Todo.due_at).all()]

@app.post("/api/todos")
def create_todo(body: TodoCreate, db: Session = Depends(get_db), user: dict = Depends(get_user)):
    todo = Todo(title=body.title, due_at=datetime.fromisoformat(body.due_at), platform=body.platform, created_by=user["sub"])
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return {"id": todo.id, "title": todo.title}

@app.put("/api/todos/{todo_id}/done")
def done_todo(todo_id: int, db: Session = Depends(get_db), user: dict = Depends(get_user)):
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(404, "待办不存在")
    todo.done = True
    db.commit()
    return {"ok": True}

@app.delete("/api/todos/{todo_id}")
def delete_todo(todo_id: int, db: Session = Depends(get_db), user: dict = Depends(get_user)):
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(404, "待办不存在")
    db.delete(todo)
    db.commit()
    return {"ok": True}

# ─── Schedule Routes ────────────────────
@app.get("/api/schedules")
def list_schedules(db: Session = Depends(get_db)):
    return [{"id": s.id, "title": s.title, "cron_expr": s.cron_expr, "platform": s.platform, "active": s.active} for s in db.query(Schedule).all()]

@app.post("/api/schedules")
def create_schedule(body: ScheduleCreate, db: Session = Depends(get_db)):
    sch = Schedule(title=body.title, cron_expr=body.cron_expr, platform=body.platform)
    db.add(sch)
    db.commit()
    db.refresh(sch)
    return {"id": sch.id, "title": sch.title}

@app.put("/api/schedules/{sch_id}/toggle")
def toggle_schedule(sch_id: int, db: Session = Depends(get_db)):
    sch = db.query(Schedule).filter(Schedule.id == sch_id).first()
    if not sch:
        raise HTTPException(404)
    sch.active = not sch.active
    db.commit()
    return {"active": sch.active}

# ─── Health ─────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

# ─── Push Engine (scheduler callback) ───
def check_and_push():
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        todos = db.query(Todo).filter(Todo.done == False, Todo.due_at <= now).all()
        for t in todos:
            # In production: call Hermes cron API
            print(f"[Aeon Push] {t.title} → {t.platform}")
            t.done = True
        db.commit()
    finally:
        db.close()

# ─── Scheduler ──────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(check_and_push, 'interval', seconds=30, id='push_engine')
scheduler.start()

# ─── WebSocket ──────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()
            await ws.send_text(json.dumps({"echo": data, "time": datetime.utcnow().isoformat()}))
    except WebSocketDisconnect:
        pass

# ─── Startup ────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
