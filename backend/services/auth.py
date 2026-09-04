"""Aeon 认证：JWT 签发/校验 + 登录 + 邀请码"""
import os
import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from db import get_db, SessionLocal
from models import User

SECRET_KEY = os.getenv("AEON_SECRET", "aeon-dev-secret-change-me")
ALGORITHM = "HS256"
ADMIN_USERNAME = "Y"
VALID_INVITE_CODES = {"AEON-2026", "ZERO-DEGREE", "PHILOSOPHY-144"}


def create_token(username: str, is_admin: bool = False) -> str:
    exp = datetime.utcnow() + timedelta(days=30 if is_admin else 1)
    payload = {"sub": username, "is_admin": is_admin, "exp": exp}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    """FastAPI 依赖：从 Authorization: Bearer <token> 解析当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登录已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效凭证")
    username = payload.get("sub")
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def login_or_register(username: str, password: str, invite_code: str = None) -> tuple[str, bool]:
    """登录或注册。返回 (token, is_new_user)
    管理员 Y：免邀请码直接放行（密码暂不校验，后续升级 hash）
    普通用户：需有效邀请码；不存在则注册，存在则校验密码
    """
    if username == ADMIN_USERNAME:
        # 管理员：免邀请码；确保 users 表有记录（密码暂不校验，后续升级 hash）
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if not user:
                user = User(username=username, password=password, is_admin=True)
                db.add(user)
                db.commit()
        finally:
            db.close()
        return create_token(username, True), False

    if not invite_code or invite_code not in VALID_INVITE_CODES:
        raise HTTPException(status_code=403, detail="需要有效邀请码")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        is_new = False
        if not user:
            user = User(username=username, password=password, invite_code=invite_code)
            db.add(user)
            db.commit()
            db.refresh(user)
            is_new = True
        elif user.password != password:
            raise HTTPException(status_code=401, detail="密码错误")
        is_admin = bool(user.is_admin)
        return create_token(username, is_admin), is_new
    finally:
        db.close()
