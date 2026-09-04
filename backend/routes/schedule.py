"""Aeon 日程模块：CRUD + 逾期顺延 + 重复事件"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import ScheduleEvent, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class EventCreate(BaseModel):
    title: str
    date: str          # YYYY-MM-DD
    time: str = ""
    priority: int = 1  # 0/1/2
    repeat: str = ""   # daily/weekly/monthly/""


class EventUpdate(BaseModel):
    title: str | None = None
    date: str | None = None
    time: str | None = None
    priority: int | None = None
    done: bool | None = None
    repeat: str | None = None


@router.get("")
def list_events(
    view: str = "today",    # today / week / undone / done / all
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """事件列表，分段视图"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    q = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == user.id)

    if view == "today":
        q = q.filter(ScheduleEvent.date == today_str)
    elif view == "week":
        end = (datetime.now() + timedelta(days=6)).strftime("%Y-%m-%d")
        q = q.filter(ScheduleEvent.date >= today_str, ScheduleEvent.date <= end)
    elif view == "undone":
        q = q.filter(ScheduleEvent.done == False)  # noqa: E712
    elif view == "done":
        q = q.filter(ScheduleEvent.done == True)  # noqa: E712

    items = q.order_by(ScheduleEvent.priority.asc(), ScheduleEvent.date, ScheduleEvent.time).all()
    result = []
    for i in items:
        overdue = not i.done and i.date < today_str
        result.append(
            {
                "id": i.id,
                "title": i.title,
                "date": i.date,
                "time": i.time,
                "priority": i.priority,
                "done": bool(i.done),
                "repeat": i.repeat,
                "overdue": overdue,
                "overdue_days": (datetime.strptime(today_str, "%Y-%m-%d") - datetime.strptime(i.date, "%Y-%m-%d")).days if overdue else 0,
            }
        )
    # 逾期放最前
    result.sort(key=lambda x: (not x["overdue"], x["priority"], x["date"]))
    return result


@router.post("")
def create_event(
    body: EventCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.priority not in (0, 1, 2):
        raise HTTPException(status_code=400, detail="priority 必须是 0/1/2")
    e = ScheduleEvent(user_id=user.id, **body.model_dump())
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"id": e.id, "ok": True}


@router.put("/{event_id}")
def update_event(
    event_id: int,
    body: EventUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    e = db.query(ScheduleEvent).filter(ScheduleEvent.id == event_id, ScheduleEvent.user_id == user.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="事件不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(e, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{event_id}")
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    e = db.query(ScheduleEvent).filter(ScheduleEvent.id == event_id, ScheduleEvent.user_id == user.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="事件不存在")
    db.delete(e)
    db.commit()
    return {"ok": True}


@router.post("/{event_id}/toggle")
def toggle_event(
    event_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """完成/未完成切换。完成时若事件有 repeat，生成下一次事件"""
    e = db.query(ScheduleEvent).filter(ScheduleEvent.id == event_id, ScheduleEvent.user_id == user.id).first()
    if not e:
        raise HTTPException(status_code=404, detail="事件不存在")
    e.done = not e.done
    next_created = None
    if e.done and e.repeat:
        base = datetime.strptime(e.date, "%Y-%m-%d")
        if e.repeat == "daily":
            nxt = base + timedelta(days=1)
        elif e.repeat == "weekly":
            nxt = base + timedelta(weeks=1)
        elif e.repeat == "monthly":
            nxt = base.replace(month=base.month + 1) if base.month < 12 else base.replace(year=base.year + 1, month=1)
        else:
            nxt = None
        if nxt:
            ne = ScheduleEvent(
                user_id=user.id,
                title=e.title,
                date=nxt.strftime("%Y-%m-%d"),
                time=e.time,
                priority=e.priority,
                repeat=e.repeat,
                done=False,
            )
            db.add(ne)
            db.flush()
            next_created = {"id": ne.id, "date": ne.date}
    db.commit()
    return {"ok": True, "done": bool(e.done), "next_created": next_created}
