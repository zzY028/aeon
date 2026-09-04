"""Aeon 待买模块：三档意愿 + 购买转记账"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import Wish, WishLevel, Ledger, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/wishes", tags=["wishes"])


class WishCreate(BaseModel):
    name: str
    level: str = "want"   # want / need / wait
    note: str = ""


class WishUpdate(BaseModel):
    name: str | None = None
    level: str | None = None
    note: str | None = None
    bought: bool | None = None


@router.get("")
def list_wishes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """待买列表：含冷静期状态（need 挂满 7 天提醒）"""
    wishes = db.query(Wish).filter(Wish.user_id == user.id).order_by(Wish.created_at.desc()).all()
    today = datetime.now()
    result = []
    for w in wishes:
        created = w.created_at.replace(tzinfo=None) if w.created_at.tzinfo else w.created_at
        hold_days = (today - created).days if not w.bought else 0
        cooling_done = w.level == WishLevel.need and not w.bought and hold_days >= 7
        result.append(
            {
                "id": w.id,
                "name": w.name,
                "level": w.level.value,
                "note": w.note,
                "bought": bool(w.bought),
                "hold_days": hold_days,
                "cooling_done": cooling_done,
                "bought_at": w.bought_at,
            }
        )
    return result


@router.post("")
def create_wish(
    body: WishCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        level = WishLevel(body.level)
    except ValueError:
        raise HTTPException(status_code=400, detail="level 必须是 want/need/wait")
    w = Wish(user_id=user.id, name=body.name, level=level, note=body.note)
    db.add(w)
    db.commit()
    db.refresh(w)
    return {"id": w.id, "ok": True}


@router.put("/{wish_id}")
def update_wish(
    wish_id: int,
    body: WishUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    w = db.query(Wish).filter(Wish.id == wish_id, Wish.user_id == user.id).first()
    if not w:
        raise HTTPException(status_code=404, detail="条目不存在")
    data = body.model_dump(exclude_none=True)
    if "level" in data:
        try:
            data["level"] = WishLevel(data["level"])
        except ValueError:
            raise HTTPException(status_code=400, detail="level 必须是 want/need/wait")
    if data.get("bought") and not w.bought:
        w.bought_at = datetime.now().strftime("%Y-%m-%d")
    for k, v in data.items():
        setattr(w, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{wish_id}")
def delete_wish(
    wish_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    w = db.query(Wish).filter(Wish.id == wish_id, Wish.user_id == user.id).first()
    if not w:
        raise HTTPException(status_code=404, detail="条目不存在")
    db.delete(w)
    db.commit()
    return {"ok": True}


@router.post("/{wish_id}/buy")
def buy_wish(
    wish_id: int,
    amount: float | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """标记已买：可选同时写入记账支出"""
    w = db.query(Wish).filter(Wish.id == wish_id, Wish.user_id == user.id).first()
    if not w:
        raise HTTPException(status_code=404, detail="条目不存在")
    w.bought = True
    w.bought_at = datetime.now().strftime("%Y-%m-%d")
    ledger_id = None
    if amount and amount > 0:
        item = Ledger(
            user_id=user.id,
            date=datetime.now().strftime("%Y-%m-%d"),
            type="expense",
            amount=amount,
            category="购物",
            note=f"待买：{w.name}",
        )
        db.add(item)
        db.flush()
        ledger_id = item.id
    db.commit()
    return {"ok": True, "ledger_id": ledger_id}
