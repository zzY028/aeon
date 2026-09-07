"""Aeon 运行时配置

所有目录型路径集中在这里，全部支持环境变量覆盖。
之前 files/wiki/briefing 各自硬编码 /root，一旦服务跑在 /home/ubuntu
（或任何非 root 用户）下，这些模块就会全部 404 —— 这是「知识库/文件打不开」
的根因。现在统一改为：环境变量优先，回落到用户主目录。
"""
import os
import logging
from pathlib import Path

log = logging.getLogger("aeon.config")


def _home() -> Path:
    """用户主目录：Linux 下通常是 /home/ubuntu 或 /root，Windows 下是 C:\\Users\\xxx"""
    return Path(os.path.expanduser("~")).resolve()


def _pick(env_key: str, *fallbacks) -> Path:
    """环境变量优先，否则用第一个存在的回退目录，都不存在就用第一个回退路径"""
    v = os.getenv(env_key)
    if v:
        return Path(v).expanduser().resolve()
    for c in fallbacks:
        p = Path(c).expanduser()
        if p.exists():
            return p.resolve()
    return Path(fallbacks[0]).expanduser().resolve()


# ─── 文件浏览根目录（/api/files）──────────────────────────
# 默认用户主目录；生产环境建议显式设置成一个受控目录，如 /home/ubuntu/aeon-files
FILES_ROOT = _pick("AEON_FILES_ROOT", _home())

# ─── Wiki 根目录（/api/wiki）─────────────────────────────
WIKI_ROOT = _pick("AEON_WIKI_ROOT", _home() / "Wiki")
PAGES_DIR = WIKI_ROOT / "pages"
WIKI_CATS = ["concepts", "entities", "summaries", "comparisons"]

# ─── 早报目录（/api/briefing）────────────────────────────
BRIEFING_DIR = _pick("AEON_BRIEFING_DIR", _home() / "Daily")


def ensure_wiki_dirs(create: bool = True) -> bool:
    """确保 Wiki 目录结构存在。返回 Wiki 是否已就绪（有 pages 目录）"""
    if PAGES_DIR.is_dir():
        return True
    if not create:
        return False
    try:
        for cat in WIKI_CATS:
            (PAGES_DIR / cat).mkdir(parents=True, exist_ok=True)
        log.info("已初始化 Wiki 目录结构：%s", PAGES_DIR)
        return True
    except OSError as e:
        log.warning("无法创建 Wiki 目录 %s：%s", PAGES_DIR, e)
        return False


def describe() -> dict:
    """供 /health 或排障时查看当前生效路径"""
    return {
        "files_root": str(FILES_ROOT),
        "files_root_exists": FILES_ROOT.is_dir(),
        "wiki_root": str(WIKI_ROOT),
        "pages_dir": str(PAGES_DIR),
        "pages_dir_exists": PAGES_DIR.is_dir(),
        "briefing_dir": str(BRIEFING_DIR),
        "briefing_dir_exists": BRIEFING_DIR.is_dir(),
    }
