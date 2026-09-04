"""Aeon 习惯模块：CRUD + 打卡 + 热力图数据"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import Habit, HabitLog, User, HabitType
from services.auth import get_current_user

router = APIRouter(prefix="/api/habits", tags=["habits"])


class HabitCreate(BaseModel):
    name: str
    htype: str = "check"   # check / count / value
    target: float = 1
    unit: str = ""


class HabitUpdate(BaseModel):
    name: str | None = None
    target: float | None = None
    unit: str | None = None


class HabitLogCreate(BaseModel):
    date: str            # YYYY-MM-DD
    value: float = 1


@router.get("")
def list_habits(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """习惯列表 + 今日状态 + 连续天数"""
    habits = db.query(Habit).filter(Habit.user_id == user.id).all()
    today = datetime.now().strftime("%Y-%m-%d")
    result = []
    for h in habits:
        # 今日打卡值
        today_log = (
            db.query(HabitLog)
            .filter(HabitLog.habit_id == h.id, HabitLog.date == today)
            .first()
        )
        # 连续天数
        streak = 0
        d = datetime.now()
        while True:
            key = d.strftime("%Y-%m-%d")
            log = (
                db.query(HabitLog)
                .filter(HabitLog.habit_id == h.id, HabitLog.date == key)
                .first()
            )
            if not log:
                break
            streak += 1
            d -= timedelta(days=1)
        # 30 天完成率
        total30 = 0
        done30 = 0
        for i in range(30):
            key = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            log = (
                db.query(HabitLog)
                .filter(HabitLog.habit_id == h.id, HabitLog.date == key)
                .first()
            )
            total30 += 1
            if log:
                done30 += 1
        rate = round(done30 / total30 * 100) if total30 else 0

        result.append(
            {
                "id": h.id,
                "name": h.name,
                "htype": h.htype.value,
                "target": h.target,
                "unit": h.unit,
                "today_value": today_log.value if today_log else 0,
                "today_done": today_log is not None,
                "streak": streak,
                "rate30": rate,
            }
        )
    return result


@router.post("")
def create_habit(
    body: HabitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        htype = HabitType(body.htype)
    except ValueError:
        raise HTTPException(status_code=400, detail="htype 必须是 check/count/value")
    h = Habit(user_id=user.id, name=body.name, htype=htype, target=body.target, unit=body.unit)
    db.add(h)
    db.commit()
    db.refresh(h)
    return {"id": h.id, "ok": True}


@router.put("/{habit_id}")
def update_habit(
    habit_id: int,
    body: HabitUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if not h:
        raise HTTPException(status_code=404, detail="习惯不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(h, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{habit_id}")
def delete_habit(
    habit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    h = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if not h:
        raise HTTPException(status_code=404, detail="习惯不存在")
    db.query(HabitLog).filter(HabitLog.habit_id == habit_id).delete()
    db.delete(h)
    db.commit()
    return {"ok": True}


@router.post("/{habit_id}/log")
def log_habit(
    habit_id: int,
    body: HabitLogCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """打卡：同日重复打卡则累加/覆盖（count 累加，check 覆盖为 1）"""
    h = db.query(Habit).filter(Habit.id == habit_id, Habit.user_id == user.id).first()
    if not h:
        raise HTTPException(status_code=404, detail="习惯不存在")
    log = (
        db.query(HabitLog)
        .filter(HabitLog.habit_id == habit_id, HabitLog.date == body.date)
        .first()
    )
    if log:
        if h.htype == HabitType.cnt:
            log.value += body.value
        else:
            log.value = body.value
    else:
        log = HabitLog(user_id=user.id, habit_id=habit_id, date=body.date, value=body.value)
        db.add(log)
    db.commit()
    return {"ok": True, "date": body.date, "value": log.value}


@router.get("/heatmap")
def habit_heatmap(
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """热力图数据：近 N 天每日完成数"""
    habits = db.query(Habit).filter(Habit.user_id == user.id).all()
    habit_ids = [h.id for h in habits]
    if not habit_ids:
        return {"days": []}
    start = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    logs = (
        db.query(HabitLog)
        .filter(HabitLog.user_id == user.id, HabitLog.date >= start)
        .all()
    )
    # 按日期聚合
    by_date: dict[str, int] = {}
    for log in logs:
        by_date[log.date] = by_date.get(log.date, 0) + 1
    days_list = []
    for i in range(days):
        key = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        days_list.append({"date": key, "count": by_date.get(key, 0), "total": len(habit_ids)})
    return {"days": days_list}
