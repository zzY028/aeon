"""Aeon 书架模块：上传/解析/章节/阅读进度"""
import os
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from db import get_db
from models import Book, BookChapter, User
from services.auth import get_current_user

router = APIRouter(prefix="/api/books", tags=["books"])

BOOK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "books")
os.makedirs(BOOK_DIR, exist_ok=True)

# 章节正则：第X章 / 第X节 / Chapter X / 数字标题
CHAPTER_RE = re.compile(r"^\s*第\s*[0-9一二三四五六七八九十百千零两]+\s*[章节回卷部篇][^\n]*|^\s*Chapter\s+\d+[^\n]*|^\s*CHAPTER\s+\d+[^\n]*|^\s*\d+\s*[.、．][^\n]*", re.MULTILINE)


class BookMeta(BaseModel):
    title: str
    author: str = ""


class ProgressUpdate(BaseModel):
    chapter: int
    position: float = 0  # 0-100


def parse_txt(content: str) -> list[dict]:
    """txt 按章节正则切分"""
    # 找到所有章节标题的位置
    matches = list(CHAPTER_RE.finditer(content))
    chapters = []
    if not matches:
        # 没有章节标记：整本作为一章
        return [{"title": "全文", "content": content.strip()}]
    for idx, m in enumerate(matches):
        start = m.end()  # 内容从标题行结束之后开始（标题单独存）
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        title = m.group().strip()
        body = content[start:end].strip()
        # 跳过空内容章节（标题后没正文 → 不产生空页）
        if not body:
            continue
        chapters.append({"title": title, "content": body})
    # 如果全部章节都空，退回整本
    if not chapters:
        return [{"title": "全文", "content": content.strip()}]
    return chapters


def parse_epub(file_path: str) -> list[dict]:
    """epub 用 ebooklib 解析"""
    from ebooklib import epub
    from bs4 import BeautifulSoup

    book = epub.read_epub(file_path)
    chapters = []
    for item in book.get_items_of_type(9):  # ITEM_DOCUMENT
        if not item.get_name().endswith((".html", ".xhtml")):
            continue
        soup = BeautifulSoup(item.get_content(), "html.parser")
        # 提取标题（h1/h2 或文件名）
        h = soup.find(["h1", "h2", "h3", "title"])
        title = h.get_text().strip() if h else item.get_name().split("/")[-1]
        # 去掉标题节点，取正文
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text("\n", strip=True)
        if text:
            chapters.append({"title": title, "content": text})
    return chapters


@router.get("")
def list_books(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """书架列表：书名/封面/进度"""
    books = db.query(Book).filter(Book.user_id == user.id).order_by(Book.created_at.desc()).all()
    return [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "source": b.source,
            "cover": b.cover,
            "total_chapters": b.total_chapters,
            "current_chapter": b.current_chapter,
            "position": b.position,
        }
        for b in books
    ]


@router.post("/upload")
async def upload_book(
    file: UploadFile = File(...),
    title: str = Form(""),
    author: str = Form(""),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传小说（txt/epub），自动解析章节，可填书名/作者"""
    fname = file.filename or ""
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if ext not in ("txt", "epub"):
        raise HTTPException(status_code=400, detail="仅支持 txt / epub")

    # 书名：表单优先，否则用文件名
    book_title = title.strip() or fname.rsplit(".", 1)[0].strip()
    book_author = author.strip()

    # 保存文件
    safe = uuid.uuid4().hex + "." + ext
    dest = os.path.join(BOOK_DIR, safe)
    content_bytes = await file.read()
    with open(dest, "wb") as f:
        f.write(content_bytes)

    # 解析章节
    try:
        if ext == "txt":
            text = content_bytes.decode("utf-8", errors="replace")
            chapters = parse_txt(text)
        else:
            chapters = parse_epub(dest)
    except Exception as e:
        os.remove(dest)
        raise HTTPException(status_code=400, detail=f"解析失败：{str(e)}")

    if not chapters:
        os.remove(dest)
        raise HTTPException(status_code=400, detail="未解析出任何章节")

    # 书名：去掉扩展名
    title = fname.rsplit(".", 1)[0]
    book = Book(
        user_id=user.id,
        title=book_title,
        author=book_author,
        source="upload",
        file_path=dest,
        total_chapters=len(chapters),
        current_chapter=1,
        position=0,
    )
    db.add(book)
    db.flush()

    for idx, ch in enumerate(chapters, 1):
        db.add(BookChapter(
            book_id=book.id,
            idx=idx,
            title=ch["title"][:200],
            content=ch["content"],
        ))
    # 同步到书影音收藏（书架的书自动出现在收藏里，status=doing 进行中）
    from models import MediaItem, MediaType, MediaStatus
    existing = db.query(MediaItem).filter(MediaItem.user_id == user.id, MediaItem.title == book_title).first()
    if not existing:
        db.add(MediaItem(
            user_id=user.id,
            title=book_title,
            mtype=MediaType.book,
            status=MediaStatus.doing,
            rating=0,
            comment="",
            book_id=book.id,
        ))
    db.commit()
    return {"id": book.id, "title": book_title, "total_chapters": len(chapters), "ok": True}


@router.get("/{book_id}/chapters")
def book_chapters(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """章节目录（不含正文，轻量）"""
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书不存在")
    chapters = (
        db.query(BookChapter)
        .filter(BookChapter.book_id == book_id)
        .order_by(BookChapter.idx)
        .all()
    )
    return {
        "book": {"id": book.id, "title": book.title, "total_chapters": book.total_chapters,
                 "current_chapter": book.current_chapter, "position": book.position},
        "chapters": [{"idx": c.idx, "title": c.title} for c in chapters],
    }


@router.get("/{book_id}/read")
def read_chapter(
    book_id: int,
    chapter: int = 1,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """读取指定章节正文"""
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书不存在")
    ch = (
        db.query(BookChapter)
        .filter(BookChapter.book_id == book_id, BookChapter.idx == chapter)
        .first()
    )
    if not ch:
        raise HTTPException(status_code=404, detail="章节不存在")
    return {
        "book_id": book.id,
        "chapter": ch.idx,
        "title": ch.title,
        "content": ch.content,
        "total": book.total_chapters,
        "prev": ch.idx - 1 if ch.idx > 1 else None,
        "next": ch.idx + 1 if ch.idx < book.total_chapters else None,
    }


@router.put("/{book_id}/progress")
def save_progress(
    book_id: int,
    body: ProgressUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """保存阅读进度（章节 + 位置%）"""
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书不存在")
    book.current_chapter = body.chapter
    book.position = max(0, min(100, body.position))
    db.commit()
    return {"ok": True, "chapter": book.current_chapter, "position": book.position}


@router.put("/{book_id}")
def update_book(
    book_id: int,
    data: BookMeta,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """更新书信息（书名/作者）"""
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书不存在")
    if data.title:
        book.title = data.title
    book.author = data.author
    db.commit()
    return {"ok": True, "title": book.title, "author": book.author}


@router.delete("/{book_id}")
def delete_book(
    book_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """删除书籍（连同章节和文件）"""
    book = db.query(Book).filter(Book.id == book_id, Book.user_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="书不存在")
    # 删文件
    if book.file_path and os.path.exists(book.file_path):
        os.remove(book.file_path)
    # 删章节
    db.query(BookChapter).filter(BookChapter.book_id == book_id).delete()
    db.delete(book)
    db.commit()
    return {"ok": True}
