"""Aeon 认证：JWT 签发/校验 + 登录 + 邀请码 + 密码哈希

安全说明：
- 管理员也走完整密码校验（此前 username == 'Y' 时直接放行，等于无密码后门）
- 密码用 PBKDF2-HMAC-SHA256 存储，不再明文
- 兼容历史明文密码：首次成功登录后自动升级为哈希
- AEON_SECRET 未设置时生成随机临时密钥，不再使用公开默认值
"""
import os
import re
import jwt
import hmac
import base64
import hashlib
import secrets
import logging
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session

from db import get_db, SessionLocal
from models import User

log = logging.getLogger("aeon.auth")

ALGORITHM = "HS256"
ADMIN_USERNAME = "Y"
VALID_INVITE_CODES = {"AEON-2026", "ZERO-DEGREE", "PHILOSOPHY-144"}
# 管理员邀请码：用它注册的新账号直接获得管理员权限（与用户名解绑）
ADMIN_INVITE_CODES = {"AEON-ROOT"}

# 密码学参数
PBKDF2_ITERATIONS = 200_000
_MIN_PASSWORD_LEN = 4

# ─── JWT 密钥 ────────────────────────────────────────────
_env_secret = os.getenv("AEON_SECRET")
if _env_secret:
    SECRET_KEY = _env_secret
else:
    # 不再使用公开的硬编码默认值：未配置时随机生成，重启后登录态失效
    SECRET_KEY = secrets.token_urlsafe(48)
    log.warning(
        "AEON_SECRET 未设置，已生成临时随机密钥（服务重启后所有人需重新登录）。"
        "生产环境请在 .env 中配置 AEON_SECRET。"
    )


# ─── 密码哈希 ────────────────────────────────────────────
def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """生成 pbkdf2_sha256$迭代次数$salt$hash 格式的密码串"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256$%d$%s$%s" % (
        iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(dk).decode("ascii"),
    )


def _hash_with_salt(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)


def verify_password(password: str, stored: str | None) -> bool:
    """校验密码。兼容历史明文存储（无 $ 分隔的旧值）"""
    if not stored:
        return False
    # 历史明文
    if "$" not in stored:
        return hmac.compare_digest(stored, password)
    try:
        algo, iters_s, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expect = base64.b64decode(hash_b64)
    except Exception:
        return False
    actual = _hash_with_salt(password, salt, int(iters_s))
    return hmac.compare_digest(actual, expect)


def needs_rehash(stored: str | None) -> bool:
    """明文或迭代次数低于当前标准的，都值得重新哈希"""
    if not stored or "$" not in stored:
        return True
    try:
        return int(stored.split("$")[1]) < PBKDF2_ITERATIONS
    except Exception:
        return True


def _validate_password(password: str):
    if not password or len(password) < _MIN_PASSWORD_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"密码至少 {_MIN_PASSWORD_LEN} 位",
        )


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


def _finalize_login(db: Session, user: User, password: str, is_new: bool) -> tuple[str, bool]:
    """校验通过后：必要时把明文升级为哈希，然后签发 token"""
    if needs_rehash(user.password):
        user.password = hash_password(password)
        db.add(user)
        db.commit()
    return create_token(user.username, bool(user.is_admin)), is_new


def login_or_register(username: str, password: str, invite_code: str = None) -> tuple[str, bool]:
    """登录或注册。返回 (token, is_new_user)

    - 管理员 Y：免邀请码，但**必须校验密码**；首次登录（库里没有该用户）时用
      本次提交的密码建立管理员账号。
    - 普通用户：需有效邀请码；不存在则注册，存在则校验密码。
    """
    username = (username or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="用户名不能为空")

    is_admin_flow = username == ADMIN_USERNAME
    _validate_password(password)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()

        if user is None:
            # 新用户注册：必须校验邀请码（管理员首次登录亦走此分支，免码建管理员账号）
            # 管理员码（ADMIN_INVITE_CODES）注册即管理员；普通码注册普通用户
            used_admin_code = invite_code and invite_code in ADMIN_INVITE_CODES
            if not is_admin_flow and not (
                invite_code and (invite_code in VALID_INVITE_CODES or used_admin_code)
            ):
                raise HTTPException(status_code=403, detail="需要有效邀请码")
            user = User(
                username=username,
                password=hash_password(password),
                is_admin=is_admin_flow or bool(used_admin_code),
                invite_code=None if is_admin_flow else invite_code,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return create_token(username, bool(user.is_admin)), True

        # 已存在 → 校验密码
        if not verify_password(password, user.password):
            raise HTTPException(status_code=401, detail="用户名或密码错误")

        return _finalize_login(db, user, password, False)
    finally:
        db.close()
