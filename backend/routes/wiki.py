"""Aeon Wiki 入口：浏览知识库结构 + 读页面内容"""
import os
import glob
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

from db import get_db
from models import User
from services.auth import get_current_user
from config import WIKI_ROOT, PAGES_DIR, WIKI_CATS, ensure_wiki_dirs

log = logging.getLogger("aeon.wiki")

router = APIRouter(prefix="/api/wiki", tags=["wiki"])

# 目录来源集中到 config（可用 AEON_WIKI_ROOT 覆盖），启动时确保结构存在
WIKI_READY = ensure_wiki_dirs()


def _safe_page(rel: str) -> str:
    """安全解析页面相对路径（pages/ 下）"""
    full = os.path.realpath(os.path.join(str(PAGES_DIR), rel or ""))
    try:
        if os.path.commonpath([full, str(PAGES_DIR)]) != str(PAGES_DIR):
            raise HTTPException(status_code=403, detail="路径越界")
    except ValueError:
        raise HTTPException(status_code=403, detail="路径越界")
    return full


@router.get("/overview")
def wiki_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Wiki 概览：各分类页面数 + 最近更新"""
    ensure_wiki_dirs()
    stats = {}
    for cat in WIKI_CATS:
        d = PAGES_DIR / cat
        if d.is_dir():
            stats[cat] = len([f for f in os.listdir(d) if f.endswith(".md")])
        else:
            stats[cat] = 0

    # 最近更新的 10 个页面
    recent = []
    for f in glob.glob(str(PAGES_DIR / "**" / "*.md"), recursive=True):
        try:
            recent.append({"name": os.path.basename(f)[:-3], "path": os.path.relpath(f, PAGES_DIR),
                           "mtime": os.path.getmtime(f)})
        except OSError:
            pass
    recent.sort(key=lambda x: -x["mtime"])
    for r in recent:
        r.pop("mtime", None)

    return {
        "stats": stats,
        "recent": recent[:10],
        "root": str(WIKI_ROOT),
        "pages_dir": str(PAGES_DIR),
        "ready": PAGES_DIR.is_dir(),
        "total": sum(stats.values()),
    }


@router.get("/graph")
def wiki_graph(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """知识图谱数据：所有页面 + 关联边（用于 Obsidian 式图谱）"""
    import re as _re
    nodes = []
    edges = []
    seen = set()
    # 扫描概念页 + 实体页
    for cat in ["concepts", "entities", "summaries"]:
        d = PAGES_DIR / cat
        if not d.is_dir():
            continue
        for f in sorted(glob.glob(os.path.join(d, "*.md"))):
            name = os.path.basename(f)[:-3]
            title = name
            related = []
            try:
                with open(f, encoding="utf-8") as fh:
                    head = fh.read(2000)
                    for line in head.split("\n")[:20]:
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if line.startswith("related:"):
                            # 解析 related 列表里的路径
                            for m in _re.finditer(r"\.\./(\w+)/([\w-]+)\.md", line):
                                related.append((m.group(1), m.group(2)))
            except OSError:
                continue
            nid = f"{cat}/{name}"
            nodes.append({"id": nid, "label": title, "cat": cat})
            seen.add(nid)
            for rcat, rname in related:
                rid = f"{rcat}/{rname}"
                if rid in seen or True:  # 边只要源节点在就行
                    edges.append({"source": nid, "target": rid})
    return {"nodes": nodes[:200], "edges": edges[:400]}


@router.get("/list")
def wiki_list(
    cat: str = "concepts",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出某分类下的所有页面"""
    if cat not in WIKI_CATS:
        raise HTTPException(status_code=400, detail="分类无效")
    ensure_wiki_dirs()
    d = PAGES_DIR / cat
    files = sorted(glob.glob(str(d / "*.md")))
    result = []
    for f in files:
        name = os.path.basename(f)[:-3]
        title = name
        # 尝试读 frontmatter title
        try:
            with open(f, encoding="utf-8") as fh:
                head = fh.read(600)
                if "title:" in head:
                    for line in head.split("\n")[:15]:
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"').strip("'")
                            break
        except OSError:
            pass
        result.append({"name": name, "title": title})
    return result


@router.get("/page")
def wiki_page(
    path: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """读取页面内容（markdown 原文）"""
    full = _safe_page(path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="页面不存在")
    with open(full, encoding="utf-8") as f:
        content = f.read()
    return {"path": path, "content": content[:20000]}


@router.get("/meta")
def wiki_meta(user: User = Depends(get_current_user)):
    """当前 Wiki 的生效目录（排障用）。之前硬编码 /root/Wiki，非 root 部署时必然为空。"""
    ok = ensure_wiki_dirs()
    counts = {}
    for c in WIKI_CATS:
        d = PAGES_DIR / c
        counts[c] = len(list(d.glob("*.md"))) if d.is_dir() else 0
    return {
        "wiki_root": str(WIKI_ROOT),
        "pages_dir": str(PAGES_DIR),
        "exists": PAGES_DIR.is_dir(),
        "ready": ok,
        "categories": WIKI_CATS,
        "counts": counts,
        "hint": "把 .md 文件放进 pages/<分类>/ 即可显示；可用 AEON_WIKI_ROOT 改目录",
    }
