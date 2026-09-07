"""WorkBuddy 交付端点：接收上传 → 落盘 → 触发 Hermes 验收。

POST /api/wb/deliver  (multipart/form-data)
  - task_id: str        任务标识
  - report: str         交付报告（做了什么/测试/变更）
  - file:   file        产物文件（zip/patch/代码）
  - Authorization: Bearer <WB_DELIVER_TOKEN>

收到后文件落盘到 WB_DELIVER_DIR，然后内部调用 Hermes webhook
(127.0.0.1:8644/webhooks/wb-deliver) 即时触发验收。
"""
import hashlib
import hmac
import json
import os
import time
import urllib.request
import uuid

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile

router = APIRouter(prefix="/api/wb", tags=["wb"])

WB_DELIVER_DIR = os.environ.get("WB_DELIVER_DIR", "/home/ubuntu/wb-deliver")
WB_TOKEN = os.environ.get("WB_DELIVER_TOKEN", "")
WEBHOOK_URL = os.environ.get("WB_WEBHOOK_URL", "http://127.0.0.1:8644/webhooks/wb-deliver")
WEBHOOK_SECRET = os.environ.get("WB_WEBHOOK_SECRET", "")

_MAX_FILE = 100 * 1024 * 1024  # 100MB


def _trigger_hermes(task_id: str, fname: str, size: int) -> None:
    """内部触发 Hermes webhook（带 HMAC 签名）。失败不阻塞上传响应——cron 轮询兜底。"""
    if not WEBHOOK_URL or not WEBHOOK_SECRET:
        return
    body = json.dumps({
        "type": "wb.delivery",
        "task_id": task_id,
        "file": fname,
        "size": size,
        "ts": int(time.time()),
    }).encode()
    ts = str(int(time.time()))
    sig = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.{body.decode()}".encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        WEBHOOK_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Webhook-Timestamp": ts,
            "X-Webhook-Signature-V2": sig,
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"[wb_deliver] webhook 触发失败: {e!r}", flush=True)
        pass  # 触发失败由 cron 轮询兜底


@router.post("/deliver")
async def wb_deliver(
    task_id: str = Form(...),
    report: str = Form(""),
    file: UploadFile = File(None),
    authorization: str = Header(None),
):
    # 1) 认证：Bearer token
    if not WB_TOKEN or authorization != f"Bearer {WB_TOKEN}":
        raise HTTPException(status_code=401, detail="token 无效")
    # 2) task_id 防穿越 + 防空
    task_id = os.path.basename(task_id.strip())[:64]
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id 缺失")
    # 3) 落盘目录
    os.makedirs(WB_DELIVER_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    try:
        # 产物文件
        saved_name = None
        if file is not None:
            data = await file.read()
            if len(data) > _MAX_FILE:
                raise HTTPException(status_code=413, detail="文件过大(>100MB)")
            orig = os.path.basename(file.filename or "deliver.bin")
            saved_name = f"{task_id}_{ts}_{orig}"
            with open(os.path.join(WB_DELIVER_DIR, saved_name), "wb") as f:
                f.write(data)
        # 报告
        if report.strip():
            rep_name = f"{task_id}_{ts}_report.md"
            with open(os.path.join(WB_DELIVER_DIR, rep_name), "w", encoding="utf-8") as f:
                f.write(report)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"落盘失败: {e}")
    # 4) 触发 Hermes（即时；失败 cron 兜底）
    _trigger_hermes(task_id, saved_name or "(report only)", len(report))
    return {"status": "ok", "task_id": task_id, "file": saved_name, "note": "已接收，Hermes 将验收"}
