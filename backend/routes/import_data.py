"""Aeon 数据导入：JSON 备份恢复"""
from datetime import datetime
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import Ledger, Habit, HabitLog, ScheduleEvent, Wish, MediaItem, Book, BookChapter, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/import", tags=["import"])


class ImportData(BaseModel):
    ledger: list = []
    habits: list = []
    schedule: list = []
    wishes: list = []
    media: list = []
    books: list = []


@router.post("")
def import_data(
    body: ImportData,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """导入数据：先清空当前用户数据，再写入"""
    uid = user.id

    # 清空
    db.query(BookChapter).filter(BookChapter.book_id.in_(
        db.query(Book.id).filter(Book.user_id == uid)
    )).delete(synchronize_session=False)
    db.query(Book).filter(Book.user_id == uid).delete()
    db.query(MediaItem).filter(MediaItem.user_id == uid).delete()
    db.query(Wish).filter(Wish.user_id == uid).delete()
    db.query(ScheduleEvent).filter(ScheduleEvent.user_id == uid).delete()
    db.query(HabitLog).filter(HabitLog.user_id == uid).delete()
    db.query(Habit).filter(Habit.user_id == uid).delete()
    db.query(Ledger).filter(Ledger.user_id == uid).delete()
    db.flush()

    counts = {}

    # 记账
    for item in body.ledger:
        db.add(Ledger(user_id=uid, date=item.get("date", ""), type=item.get("type", "expense"),
                      amount=item.get("amount", 0), category=item.get("category", "其他"),
                      note=item.get("note", "")))
    counts["ledger"] = len(body.ledger)

    # 习惯（含打卡记录）
    for h in body.habits:
        nh = Habit(user_id=uid, name=h.get("name", ""), htype=h.get("htype", "check"),
                   target=h.get("target", 1), unit=h.get("unit", ""))
        db.add(nh)
        db.flush()
        for log in h.get("logs", []):
            db.add(HabitLog(user_id=uid, habit_id=nh.id, date=log.get("date", ""),
                            value=log.get("value", 1)))
    counts["habits"] = len(body.habits)

    # 日程
    for e in body.schedule:
        db.add(ScheduleEvent(user_id=uid, title=e.get("title", ""), date=e.get("date", ""),
                             time=e.get("time", ""), priority=e.get("priority", 1),
                             done=e.get("done", False), repeat=e.get("repeat", "")))
    counts["schedule"] = len(body.schedule)

    # 待买
    for w in body.wishes:
        db.add(Wish(user_id=uid, name=w.get("name", ""), level=w.get("level", "want"),
                    note=w.get("note", ""), bought=w.get("bought", False),
                    bought_at=w.get("bought_at")))
    counts["wishes"] = len(body.wishes)

    # 书影音
    for m in body.media:
        db.add(MediaItem(user_id=uid, title=m.get("title", ""), mtype=m.get("mtype", "book"),
                         status=m.get("status", "want"), rating=m.get("rating", 0),
                         comment=m.get("comment", ""), cover=m.get("cover", "")))
    counts["media"] = len(body.media)

    # 书（含章节）
    for b in body.books:
        nb = Book(user_id=uid, title=b.get("title", ""), author=b.get("author", ""),
                  source=b.get("source", "upload"), total_chapters=b.get("total_chapters", 0),
                  current_chapter=b.get("current_chapter", 1), position=b.get("position", 0))
        db.add(nb)
        db.flush()
        for ch in b.get("chapters", []):
            db.add(BookChapter(book_id=nb.id, idx=ch.get("idx", 1), title=ch.get("title", ""),
                               content=ch.get("content", "")))
    counts["books"] = len(body.books)

    db.commit()
    return {"ok": True, "message": f"导入完成：记账 {counts['ledger']} · 习惯 {counts['habits']} · 日程 {counts['schedule']} · 待买 {counts['wishes']} · 书影音 {counts['media']} · 书 {counts['books']}"}
