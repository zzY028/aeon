"""Aeon 模型余额查询：DeepSeek 优先，provider 化预留"""
import os
import urllib.request
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/balance", tags=["balance"])

# DeepSeek API key：从环境变量读（不硬编码）
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# provider 化配置（后续加模型只加这里）
PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "balance_api": "https://api.deepseek.com/user/balance",
        "auth": "Bearer",
        "key": DEEPSEEK_KEY,
    },
    # 预留（暂不实现）：
    # "minimax": {...},
    # "qwen": {...},
}


class BalanceRequest(BaseModel):
    provider: str = "deepseek"


@router.post("")
def query_balance(req: BalanceRequest):
    """查询指定 provider 的账户余额"""
    provider = PROVIDERS.get(req.provider)
    if not provider:
        raise HTTPException(status_code=404, detail=f"不支持的 provider: {req.provider}")
    if not provider["key"]:
        raise HTTPException(status_code=503, detail=f"{provider['name']} 未配置 API Key")

    try:
        request = urllib.request.Request(
            provider["balance_api"],
            headers={"Authorization": f"{provider['auth']} {provider['key']}"},
        )
        with urllib.request.urlopen(request, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"余额查询失败：{str(e)}")

    # DeepSeek 返回格式: {"is_available": true, "balance_infos": [{"currency": "CNY", "total_balance": "6.52", ...}]}
    if req.provider == "deepseek" and "balance_infos" in data:
        infos = data["balance_infos"]
        total = sum(float(i.get("total_balance", 0)) for i in infos)
        currency = infos[0].get("currency", "CNY") if infos else "CNY"
        return {
            "provider": req.provider,
            "name": provider["name"],
            "balance": round(total, 2),
            "currency": currency,
            "is_available": data.get("is_available", True),
            "raw": data,
        }

    return {"provider": req.provider, "name": provider["name"], "raw": data}


@router.get("/providers")
def list_providers():
    """列出已配置的 provider（含是否已配 key）"""
    return [
        {
            "id": pid,
            "name": p["name"],
            "configured": bool(p["key"]),
        }
        for pid, p in PROVIDERS.items()
    ]
