"""Aeon 记账模块：CRUD + 月度统计"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import Ledger, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/ledger", tags=["ledger"])


class LedgerCreate(BaseModel):
    date: str          # YYYY-MM-DD
    type: str          # income / expense
    amount: float
    category: str = "其他"
    note: str = ""


class LedgerUpdate(BaseModel):
    date: str | None = None
    type: str | None = None
    amount: float | None = None
    category: str | None = None
    note: str | None = None


@router.get("")
def list_ledger(
    month: str | None = None,      # YYYY-MM
    type: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """流水列表：支持月份/类型/分类/关键词筛选"""
    q = db.query(Ledger).filter(Ledger.user_id == user.id)
    if month:
        q = q.filter(Ledger.date.like(f"{month}%"))
    if type:
        q = q.filter(Ledger.type == type)
    if category:
        q = q.filter(Ledger.category == category)
    if keyword:
        q = q.filter(Ledger.note.contains(keyword))
    items = q.order_by(Ledger.date.desc(), Ledger.id.desc()).all()
    return [
        {
            "id": i.id,
            "date": i.date,
            "type": i.type,
            "amount": i.amount,
            "category": i.category,
            "note": i.note,
        }
        for i in items
    ]


@router.post("")
def create_ledger(
    body: LedgerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = Ledger(user_id=user.id, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "ok": True}


@router.put("/{item_id}")
def update_ledger(
    item_id: int,
    body: LedgerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(Ledger).filter(Ledger.id == item_id, Ledger.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(item, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{item_id}")
def delete_ledger(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(Ledger).filter(Ledger.id == item_id, Ledger.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def ledger_stats(
    month: str,                    # YYYY-MM
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """月度统计：收支合计/分类汇总/日均"""
    items = (
        db.query(Ledger)
        .filter(Ledger.user_id == user.id, Ledger.date.like(f"{month}%"))
        .all()
    )
    income = sum(i.amount for i in items if i.type == "income")
    expense = sum(i.amount for i in items if i.type == "expense")
    days = datetime.strptime(month + "-01", "%Y-%m-%d")
    import calendar
    total_days = calendar.monthrange(days.year, days.month)[1]

    # 分类汇总（支出）
    cat_totals: dict[str, float] = {}
    for i in items:
        if i.type == "expense":
            cat_totals[i.category] = cat_totals.get(i.category, 0) + i.amount

    return {
        "month": month,
        "income": round(income, 2),
        "expense": round(expense, 2),
        "balance": round(income - expense, 2),
        "avg_daily_expense": round(expense / total_days, 2) if total_days else 0,
        "cat_totals": [{"category": k, "amount": round(v, 2)} for k, v in sorted(cat_totals.items(), key=lambda x: -x[1])],
    }


@router.get("/trend")
def ledger_trend(
    months: int = 6,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """近 N 个月收支趋势（分组柱状图数据）"""
    from dateutil.relativedelta import relativedelta
    result = []
    today = datetime.now()
    for i in range(months - 1, -1, -1):
        m = today - relativedelta(months=i)
        key = m.strftime("%Y-%m")
        items = (
            db.query(Ledger)
            .filter(Ledger.user_id == user.id, Ledger.date.like(f"{key}%"))
            .all()
        )
        income = round(sum(x.amount for x in items if x.type == "income"), 2)
        expense = round(sum(x.amount for x in items if x.type == "expense"), 2)
        result.append({"month": key, "income": income, "expense": expense})
    return result
