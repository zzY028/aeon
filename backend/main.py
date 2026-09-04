"""Aeon — 个人管家后端（v3 架构版）
FastAPI + SQLite + JWT + 多用户预留
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

import os

from db import engine, get_db
from models import Base
from services.auth import login_or_register, get_current_user
from models import User
from routes import ledger, habits, schedule, wishes, media, books, balance, briefing, import_data, files, wiki, life

# 前端目录：backend/../frontend（动态解析，避免硬编码服务器路径）
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Aeon", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ─── Routers ─────────────────────────────
app.include_router(ledger.router)
app.include_router(habits.router)
app.include_router(schedule.router)
app.include_router(wishes.router)
app.include_router(media.router)
app.include_router(books.router)
app.include_router(balance.router)
app.include_router(briefing.router)
app.include_router(import_data.router)
app.include_router(files.router)
app.include_router(wiki.router)
app.include_router(life.router)


# ─── Schemas ─────────────────────────────
class LoginRequest(BaseModel):
    username: str
    password: str
    invite_code: str | None = None


# ─── Auth ────────────────────────────────
@app.post("/api/login")
def login(req: LoginRequest):
    token, is_new = login_or_register(req.username, req.password, req.invite_code)
    return {"token": token, "is_new": is_new, "username": req.username}


@app.get("/api/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username, "is_admin": bool(user.is_admin)}


# ─── Health ─────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "Aeon", "version": "3.0"}


# ─── Static（前端）────────────────────────
@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

# 页面直接可访问：/habits.html → frontend/habits.html
@app.get("/{page}")
def page(page: str):
    if page.endswith(".html"):
        path = os.path.join(FRONTEND_DIR, os.path.basename(page))
        if os.path.exists(path):
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="页面不存在")

# 前端资源静态服务（styles / assets / images）
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
