"""Aeon tus 断点续传上传模块

基于 tuspyserver（tus 协议 FastAPI 实现）：
- 分块上传 + 断线续传（tus 核心）
- 支持并行分块（concatenation 扩展，本地存储）
- 支持多端口多片并行（大文件切成 N 片 → 各片走不同端口上传 → 合并）
- JWT 鉴权复用 Aeon 现有 get_current_user
"""
import json
import os
import shutil
import uuid as uuid_lib

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from tuspyserver import create_tus_router

from models import User
from services.auth import get_current_user
from routes.files import ROOT, _safe_path

# 上传暂存目录（uid 命名），完成后 rename 到目标目录
TUS_TMP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tus_tmp")
# 多片上传的临时分片目录
PARTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "tus_parts")
# 单文件上限 20GB
MAX_SIZE = 20 * 1024 ** 3


def _tus_auth(user: User = Depends(get_current_user)):
    """鉴权：仅管理员可上传（tus 每个请求都会过）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可上传")


def _on_complete(file_path: str, metadata: dict):
    """上传完成回调：分片模式存临时区，单文件模式直接落位

    注意：tus 协议并行上传（parallelUploads）会产生 partial 分片，
    这些分片完成后【不能落位】——它们要留在暂存区等 final 拼接，
    或由 tuspyserver 的过期机制（5 天）自动清理。这里通过读 sidecar
    的 is_partial 标记识别并跳过。
    """
    # 读 sidecar 判断是不是 tus 并行分片（partial）
    try:
        with open(file_path + ".info", "r", encoding="utf-8") as f:
            info = json.load(f)
        if info.get("is_partial"):
            return  # partial 不落位，留在暂存区
    except Exception:
        pass

    md = metadata or {}
    part_total = md.get("part_total")
    part_index = md.get("part_index")
    session = md.get("session")

    # 多片上传：分片先存到临时区，等全部到齐后由 /api/files/merge 合并
    if part_total and part_total != "1" and session and part_index is not None:
        try:
            dest_dir = os.path.join(PARTS_DIR, session)
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, f"{int(part_index):04d}")
            # 清掉可能存在的旧分片（重传场景）
            if os.path.exists(dest):
                os.remove(dest)
            os.rename(file_path, dest)
            try:
                os.remove(file_path + ".info")
            except OSError:
                pass
        except Exception:
            pass
        return

    # 单文件（或 part_total=1）：直接落位到目标目录
    rel = md.get("path", "")
    fname = os.path.basename(md.get("filename", "") or "upload.bin")
    try:
        dest_dir = _safe_path(rel)
    except HTTPException:
        dest_dir = ROOT
    if not os.path.isdir(dest_dir):
        dest_dir = ROOT

    dest = os.path.join(dest_dir, fname)
    if os.path.exists(dest):
        base, ext = os.path.splitext(fname)
        i = 1
        while os.path.exists(os.path.join(dest_dir, f"{base}_{i}{ext}")):
            i += 1
        dest = os.path.join(dest_dir, f"{base}_{i}{ext}")

    os.rename(file_path, dest)
    try:
        os.remove(file_path + ".info")
    except OSError:
        pass


tus_router = create_tus_router(
    prefix="api/tus",
    files_dir=TUS_TMP,
    max_size=MAX_SIZE,
    auth=_tus_auth,
    on_upload_complete=_on_complete,
    days_to_keep=5,
)

# ─── 多片合并 ─────────────────────────────
merge_router = APIRouter(prefix="/api/files", tags=["files"])


class MergeRequest(BaseModel):
    session: str
    filename: str
    path: str = ""
    total: int


@merge_router.post("/merge")
def merge_parts(req: MergeRequest, user: User = Depends(get_current_user)):
    """把多片上传的分片按序合并成完整文件，落位到目标目录"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可合并")

    # session 必须是我们生成的 uuid 格式，防路径穿越
    try:
        uuid_obj = uuid_lib.UUID(req.session)
        session = str(uuid_obj)
    except ValueError:
        raise HTTPException(status_code=400, detail="非法的 session")
    if req.total < 1 or req.total > 256:
        raise HTTPException(status_code=400, detail="分片数非法")

    parts_dir = os.path.join(PARTS_DIR, session)
    if not os.path.isdir(parts_dir):
        raise HTTPException(status_code=404, detail="分片不存在")

    # 校验分片齐全
    missing = []
    for i in range(req.total):
        if not os.path.isfile(os.path.join(parts_dir, f"{i:04d}")):
            missing.append(i)
    if missing:
        raise HTTPException(status_code=409, detail=f"分片缺失: {missing[:10]}")

    # 目标路径（防穿越）
    try:
        dest_dir = _safe_path(req.path)
    except HTTPException:
        dest_dir = ROOT
    if not os.path.isdir(dest_dir):
        dest_dir = ROOT

    fname = os.path.basename(req.filename or "merged.bin")
    dest = os.path.join(dest_dir, fname)
    if os.path.exists(dest):
        base, ext = os.path.splitext(fname)
        i = 1
        while os.path.exists(os.path.join(dest_dir, f"{base}_{i}{ext}")):
            i += 1
        dest = os.path.join(dest_dir, f"{base}_{i}{ext}")

    # 按序拼接（流式，不占内存）
    size = 0
    try:
        with open(dest, "wb") as out:
            for i in range(req.total):
                part_path = os.path.join(parts_dir, f"{i:04d}")
                with open(part_path, "rb") as pf:
                    shutil.copyfileobj(pf, out, 1024 * 1024)
                    size += os.path.getsize(part_path)
    except Exception as e:
        try:
            os.remove(dest)
        except OSError:
            pass
        raise HTTPException(status_code=500, detail=f"合并失败: {e}")

    # 清理分片目录
    shutil.rmtree(parts_dir, ignore_errors=True)

    return {"ok": True, "name": os.path.basename(dest), "size": size}
