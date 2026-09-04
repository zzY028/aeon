"""Aeon 云端文件浏览：管理员查看服务器文件"""
import os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from db import get_db
from models import User
from services.auth import get_current_user

router = APIRouter(prefix="/api/files", tags=["files"])

# 允许浏览的根目录（安全边界）
ALLOWED_ROOTS = ["/root"]

# 黑名单目录（不显示，避免刷屏/敏感）
BLACKLIST_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".hermes", ".cache", "spec-kit"}
BLACKLIST_EXT = {".pyc", ".db-wal", ".db-shm", ".pyo"}


def _safe_path(rel_path: str) -> str:
    """把相对路径安全解析到 /root 下"""
    # 规范化，防路径穿越
    full = os.path.realpath(os.path.join("/root", rel_path))
    if not full.startswith("/root"):
        raise HTTPException(status_code=403, detail="路径越界")
    return full


@router.get("")
def list_files(
    path: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出指定目录下的文件和文件夹"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可浏览文件")

    full = _safe_path(path)
    if not os.path.isdir(full):
        raise HTTPException(status_code=404, detail="目录不存在")

    dirs, files = [], []
    try:
        for entry in os.scandir(full):
            name = entry.name
            if entry.is_dir():
                if name not in BLACKLIST_DIRS and not name.startswith("."):
                    dirs.append({"name": name, "type": "dir", "size": None})
            elif entry.is_file():
                if not name.endswith(tuple(BLACKLIST_EXT)):
                    try:
                        size = entry.stat().st_size
                    except OSError:
                        size = 0
                    files.append({"name": name, "type": "file", "size": size})
    except PermissionError:
        raise HTTPException(status_code=403, detail="无权限访问")

    dirs.sort(key=lambda x: x["name"])
    files.sort(key=lambda x: x["name"])
    return {
        "path": path or "/",
        "parent": os.path.dirname(path.rstrip("/")) if path else None,
        "dirs": dirs,
        "files": files,
    }


@router.post("/upload")
async def upload_file(
    path: str = "",
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """上传文件到指定目录"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可上传")
    full = _safe_path(path)
    if not os.path.isdir(full):
        raise HTTPException(status_code=404, detail="目录不存在")
    fname = os.path.basename(file.filename or "file")
    dest = os.path.join(full, fname)
    # 防覆盖：重名加后缀
    if os.path.exists(dest):
        base, ext = os.path.splitext(fname)
        i = 1
        while os.path.exists(os.path.join(full, f"{base}_{i}{ext}")):
            i += 1
        dest = os.path.join(full, f"{base}_{i}{ext}")
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return {"ok": True, "name": os.path.basename(dest), "size": len(content)}


@router.get("/download")
def download_file(
    path: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """下载文件"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可下载")
    full = _safe_path(path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    from fastapi.responses import FileResponse
    return FileResponse(full, filename=os.path.basename(full))


@router.get("/preview")
def preview_file(
    path: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """预览文本类文件（md/txt/html/json/py 等）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可预览")
    full = _safe_path(path)
    if not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="文件不存在")
    ext = os.path.splitext(full)[1].lower()
    text_exts = {".md", ".txt", ".html", ".htm", ".json", ".py", ".js", ".css", ".yaml", ".yml", ".toml", ".csv", ".log", ".xml", ".sh", ".svg"}
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        # 图片：返回 base64 或 URL
        from fastapi.responses import FileResponse
        return FileResponse(full, media_type="image/png" if ext == ".png" else "image/jpeg")
    if ext not in text_exts:
        raise HTTPException(status_code=415, detail="该类型暂不支持预览")
    # 限制大小：只预览前 200KB
    size = os.path.getsize(full)
    with open(full, encoding="utf-8", errors="replace") as f:
        content = f.read(200000)
    return {"name": os.path.basename(full), "ext": ext, "size": size, "content": content}
