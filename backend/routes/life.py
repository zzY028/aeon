"""Aeon 生活簿生成器：把生活数据翻译成可读文档 + 页面字幕"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import User, Ledger, Habit, HabitLog, ScheduleEvent, Wish, Book
from services.auth import get_current_user
import os, json, urllib.request

router = APIRouter(prefix="/api/life", tags=["life"])

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

CATS = {"food":"餐饮","trans":"交通","shop":"购物","fun":"娱乐","edu":"学习","health":"健康","other":"其他"}


def build_lifebook(db: Session, user: User) -> dict:
    """汇总各模块数据 → 生活簿结构化数据"""
    now = datetime.now()
    today = now.date()
    month_start = today.replace(day=1)

    # 账目
    today_str = today.strftime("%Y-%m-%d")
    month_start_str = month_start.strftime("%Y-%m-%d")
    entries = db.query(Ledger).filter(Ledger.user_id == user.id).all()
    today_out = sum(e.amount for e in entries if e.type == "out" and e.date == today_str)
    today_entries = [e for e in entries if e.date == today_str and e.type == "out"]
    month_out = sum(e.amount for e in entries if e.type == "out" and e.date >= month_start_str)
    month_in = sum(e.amount for e in entries if e.type == "in" and e.date >= month_start_str)
    max_entry = max(entries, key=lambda e: e.amount) if entries else None

    # 习惯
    habits = db.query(Habit).filter(Habit.user_id == user.id).all()
    habit_stats = []
    for h in habits:
        logs = db.query(HabitLog).filter(HabitLog.user_id == user.id, HabitLog.habit_id == h.id).order_by(HabitLog.date.desc()).all()
        streak = 0
        for i, log in enumerate(logs):
            expected = today - timedelta(days=i)
            if log.date == expected:
                streak += 1
            else:
                break
        today_log = any(log.date == today_str for log in logs)
        habit_stats.append({"name": h.name, "type": h.htype, "streak": streak, "today_done": today_log})
    done_today = sum(1 for h in habit_stats if h["today_done"])

    # 日程
    today_str = today.strftime("%Y-%m-%d")
    events = db.query(ScheduleEvent).filter(ScheduleEvent.user_id == user.id, ScheduleEvent.date >= today_str).order_by(ScheduleEvent.date).all()
    today_events = [e for e in events if e.date == today_str]
    upcoming = [e for e in events if e.date > today_str][:3]

    # 书影音
    books = db.query(Book).filter(Book.user_id == user.id).all()
    reading = [b for b in books if b.total_chapters and b.current_chapter and b.current_chapter < b.total_chapters]

    return {
        "date": today.strftime("%Y-%m-%d"),
        "weekday": ["一","二","三","四","五","六","日"][today.weekday()],
        "ledger": {
            "today_out": today_out,
            "today_count": len(today_entries),
            "month_out": month_out,
            "month_in": month_in,
            "month_balance": month_in - month_out,
            "max": {"amount": max_entry.amount, "cat": CATS.get(max_entry.cat, max_entry.cat), "note": max_entry.note}
                if max_entry and max_entry.type == "out" else None,
        },
        "habits": {
            "done_today": done_today,
            "total": len(habits),
            "list": habit_stats,
        },
        "schedule": {
            "today_count": len(today_events),
            "today": [{"time": e.time or "全天", "title": e.title, "done": e.done} for e in today_events],
            "upcoming": [{"date": str(e.date), "title": e.title} for e in upcoming],
        },
        "reading": [{"title": b.title, "chapter": b.current_chapter, "total": b.total_chapters,
                     "percent": round(b.current_chapter / b.total_chapters * 100) if b.total_chapters else 0}
                    for b in reading],
        "updated_at": now.strftime("%H:%M"),
    }


@router.get("/book")
def get_lifebook(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """返回生活簿结构化数据"""
    return build_lifebook(db, user)


@router.post("/subtitles")
async def generate_subtitles(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """生活簿更新后，调 DeepSeek 生成每页字幕（一次生成一批）"""
    book = build_lifebook(db, user)
    if not DEEPSEEK_KEY:
        # 没 key 时返回规则模板（不调 AI）
        return {"subtitles": fallback_subtitles(book), "mode": "fallback"}

    prompt = f"""你是 Aeon（个人生活管家）的电影旁白。根据以下生活数据，为每个页面写 1 句字幕（15-30 字）。

生活数据：
- 今日支出 ¥{book['ledger']['today_out']}（{book['ledger']['today_count']} 笔），本月支出 ¥{book['ledger']['month_out']} / 收入 ¥{book['ledger']['month_in']}
- 习惯：今日完成 {book['habits']['done_today']}/{book['habits']['total']} 项
- 日程：今日 {book['schedule']['today_count']} 个事件，近期：{', '.join(e['title'] for e in book['schedule']['upcoming']) or '无'}
- 阅读：{'、'.join(f"{b['title']}({b['percent']}%)" for b in book['reading']) or '无'}

为这些页面各写 1 句：
1. 首页：今天整体状态
2. 记账：账目洞察
3. 习惯：习惯进展
4. 日程：日程提醒
5. 待买：待买建议
6. 书影音：阅读/收藏进展
7. 早报：一句话今日要点

要求：像 1999 老电影的字幕旁白，温暖克制，每句 15-30 字，不要口号，不要"加油"，每条都不一样。只输出 7 行，每行对应一个页面，不要编号。

输出格式（严格）：
[首页]xxx
[记账]xxx
[习惯]xxx
[日程]xxx
[待买]xxx
[书影音]xxx
[早报]xxx"""

    try:
        req = urllib.request.Request(DEEPSEEK_URL,
            data=json.dumps({
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.9,
                "max_tokens": 300,
            }).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {DEEPSEEK_KEY}"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        raw = data["choices"][0]["message"]["content"]
        subtitles = parse_subtitles(raw)
        return {"subtitles": subtitles, "mode": "ai"}
    except Exception as e:
        return {"subtitles": fallback_subtitles(book), "mode": f"fallback:{str(e)[:50]}"}


def parse_subtitles(raw: str) -> dict:
    """解析 AI 输出 → {页面: 字幕}"""
    result = {}
    pages = {"首页": "index", "记账": "ledger", "习惯": "habits", "日程": "schedule",
             "待买": "wishlist", "书影音": "media", "早报": "briefing"}
    for line in raw.split("\n"):
        line = line.strip()
        for name, key in pages.items():
            if line.startswith("[" + name + "]"):
                result[key] = line.split("]", 1)[1].strip()
    return result


def fallback_subtitles(book: dict) -> dict:
    """无 AI key 时的规则模板字幕"""
    lb = book["ledger"]
    subs = {}
    if lb["today_out"] > 0:
        subs["index"] = f"今天花了 ¥{lb['today_out']}，共 {lb['today_count']} 笔。"
    else:
        subs["index"] = "今天还没花钱，稳稳的。"
    subs["ledger"] = f"本月支出 ¥{lb['month_out']}，收入 ¥{lb['month_in']}。"
    subs["habits"] = f"今日习惯完成 {book['habits']['done_today']}/{book['habits']['total']} 项。"
    if book["schedule"]["today"]:
        subs["schedule"] = f"今日 {book['schedule']['today_count']} 件事待办，别忘啦。"
    else:
        subs["schedule"] = "今天日程空空的，自由一天。"
    subs["wishlist"] = "待买清单还躺着几样东西，冷静期过了再决定。"
    if book["reading"]:
        b = book["reading"][0]
        subs["media"] = f"《{b['title']}》读到 {b['percent']}% 了，慢慢来。"
    else:
        subs["media"] = "书架还空着，找本书来读吧。"
    subs["briefing"] = "今天的早报已更新，去看看吧。"
    return subs
