"""Aeon 书影音收藏模块：书/电影/剧集 CRUD + 统计"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import MediaItem, MediaType, MediaStatus, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/media", tags=["media"])


class MediaCreate(BaseModel):
    title: str
    mtype: str          # book / movie / series
    status: str = "want"
    rating: int = 0
    comment: str = ""
    cover: str = ""


class MediaUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    rating: int | None = None
    comment: str | None = None
    cover: str | None = None


@router.get("")
def list_media(
    mtype: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """书影音列表：可按类型/状态筛选"""
    q = db.query(MediaItem).filter(MediaItem.user_id == user.id)
    if mtype:
        try:
            q = q.filter(MediaItem.mtype == MediaType(mtype))
        except ValueError:
            raise HTTPException(status_code=400, detail="mtype 必须是 book/movie/series")
    if status:
        try:
            q = q.filter(MediaItem.status == MediaStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="status 必须是 want/doing/done")
    items = q.order_by(MediaItem.created_at.desc()).all()
    return [
        {
            "id": i.id,
            "title": i.title,
            "mtype": i.mtype.value,
            "status": i.status.value,
            "rating": i.rating,
            "comment": i.comment,
            "cover": i.cover,
        }
        for i in items
    ]


@router.post("")
def create_media(
    body: MediaCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        mtype = MediaType(body.mtype)
    except ValueError:
        raise HTTPException(status_code=400, detail="mtype 必须是 book/movie/series")
    try:
        status = MediaStatus(body.status)
    except ValueError:
        status = MediaStatus.want
    if body.rating < 0 or body.rating > 5:
        raise HTTPException(status_code=400, detail="rating 必须是 0-5")
    item = MediaItem(
        user_id=user.id,
        title=body.title,
        mtype=mtype,
        status=status,
        rating=body.rating,
        comment=body.comment,
        cover=body.cover,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "ok": True}


@router.put("/{item_id}")
def update_media(
    item_id: int,
    body: MediaUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    data = body.model_dump(exclude_none=True)
    if "status" in data:
        try:
            data["status"] = MediaStatus(data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail="status 必须是 want/doing/done")
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/{item_id}")
def delete_media(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = db.query(MediaItem).filter(MediaItem.id == item_id, MediaItem.user_id == user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/stats")
def media_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """年度统计：类型分布 + 状态分布 + 平均星级"""
    items = db.query(MediaItem).filter(MediaItem.user_id == user.id).all()
    type_dist: dict[str, int] = {}
    status_dist: dict[str, int] = {}
    rated = [i.rating for i in items if i.rating > 0]
    for i in items:
        type_dist[i.mtype.value] = type_dist.get(i.mtype.value, 0) + 1
        status_dist[i.status.value] = status_dist.get(i.status.value, 0) + 1
    return {
        "total": len(items),
        "type_dist": type_dist,
        "status_dist": status_dist,
        "avg_rating": round(sum(rated) / len(rated), 1) if rated else 0,
        "rated_count": len(rated),
    }
