"""Aeon 模型中心：provider 注册表 + 当前模型切换

给 Aeon 的 AI 功能（生活簿字幕、家教等）一个统一出口：
- 每个 provider 只需 base_url + key_env + 若干模型名
- 「当前模型」存 JSON（data/model_config.json），谁调用谁读
- 新增渠道只改 PROVIDERS 表，不动调用方
"""
import os
import json
import urllib.request
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/model", tags=["model"])

# data 目录：backend/data（routes 的上一级，与 db 同级）
DATA_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data"
DATA_DIR.mkdir(exist_ok=True)
CONFIG_FILE = DATA_DIR / "model_config.json"

# ─── Provider 注册表（加渠道只改这里）──────────────────
# key_env 指向环境变量（.env 里配），key 从环境变量实时读
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
        "models": [
            {"id": "deepseek-v4-flash", "label": "V4 Flash（快/便宜）"},
            {"id": "deepseek-v4-pro", "label": "V4 Pro（强）"},
        ],
    },
    "dashscope": {
        "name": "阿里百炼 DashScope",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": "DASHSCOPE_API_KEY",
        "models": [
            {"id": "qwen-turbo", "label": "Qwen Turbo（快/便宜）"},
            {"id": "qwen-plus", "label": "Qwen Plus"},
            {"id": "qwen3-235b-a22b", "label": "Qwen3 235B MoE（强）"},
        ],
    },
    "kimi-k3": {
        "name": "Kimi K3（百炼）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "key_env": "KIMI_K3_API_KEY",
        "models": [
            {"id": "kimi-k3", "label": "Kimi K3"},
            {"id": "kimi-k2.7-code", "label": "Kimi K2.7 Code"},
        ],
    },
}

DEFAULT_CONFIG = {"provider": "deepseek", "model": "deepseek-v4-pro"}


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def _save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def get_current_config() -> dict:
    """当前生效的 provider+model 配置（调用方入口）"""
    return _load_config()


def resolve() -> dict:
    """解析当前配置 → (base_url, key, model)。key 缺失时返回 None 由调用方降级"""
    cfg = _load_config()
    p = PROVIDERS.get(cfg.get("provider"))
    if not p:
        return None
    key = os.getenv(p["key_env"], "")
    return {
        "provider": p["name"],
        "provider_id": cfg["provider"],
        "base_url": p["base_url"],
        "api_key": key,
        "model": cfg.get("model", p["models"][0]["id"]),
        "configured": bool(key),
    }


class SwitchRequest(BaseModel):
    provider: str
    model: str | None = None


@router.get("/providers")
def list_providers():
    """列出所有 provider 及其模型，标注 key 是否已配"""
    out = []
    for pid, p in PROVIDERS.items():
        key = os.getenv(p["key_env"], "")
        out.append({
            "id": pid,
            "name": p["name"],
            "configured": bool(key),
            "models": p["models"],
        })
    return out


@router.get("/current")
def current():
    cfg = _load_config()
    r = resolve()
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "resolved": r,
    }


@router.post("/switch")
def switch(req: SwitchRequest):
    """切换当前模型。model 可省略（用该 provider 第一个模型）"""
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"不支持的 provider: {req.provider}")
    p = PROVIDERS[req.provider]
    valid_ids = [m["id"] for m in p["models"]]
    model = req.model or valid_ids[0]
    if model not in valid_ids:
        raise HTTPException(status_code=400, detail=f"模型 {model} 不在 {p['name']} 列表中")
    cfg = {"provider": req.provider, "model": model}
    _save_config(cfg)
    return {"ok": True, "config": cfg}


@router.post("/test")
def test_switch(req: SwitchRequest):
    """先测试连通再切换：用目标 provider+model 发一句请求，成功才保存"""
    if req.provider not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"不支持的 provider: {req.provider}")
    p = PROVIDERS[req.provider]
    valid_ids = [m["id"] for m in p["models"]]
    model = req.model or valid_ids[0]
    if model not in valid_ids:
        raise HTTPException(status_code=400, detail=f"模型 {model} 不在 {p['name']} 列表中")

    key = os.getenv(p["key_env"], "")
    if not key:
        raise HTTPException(status_code=503, detail=f"{p['name']} 未配置 API Key（.env 里加 {p['key_env']}）")

    url = p["base_url"].rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "回复OK两个字"}],
        "max_tokens": 10,
    }).encode()
    req_http = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req_http, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        reply = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"测试失败：{str(e)[:120]}")

    # 成功 → 保存
    cfg = {"provider": req.provider, "model": model}
    _save_config(cfg)
    return {"ok": True, "reply": reply, "config": cfg}
