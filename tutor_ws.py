"""
Aeon Tutor — 飞书 WebSocket 高数家教
"""

import os, json, time, httpx, logging
from lark_oapi.ws import Client as WSClient
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi import Client

APP_ID = os.getenv("TUTOR_APP_ID", "")
APP_SECRET = os.getenv("TUTOR_APP_SECRET", "")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger("tutor")


def ask_deepseek(question: str) -> str:
    resp = httpx.post(
        "https://api.deepseek.com/v1/chat/completions",
        json={
            "model": "deepseek-v4-pro",
            "messages": [
                {"role": "system", "content": "你是高等数学家教。用苏格拉底式提问引导，不直接给答案。用中文，简洁。参考教材：同济八版高等数学。"},
                {"role": "user", "content": question}
            ],
            "temperature": 0.3, "max_tokens": 2048
        },
        headers={"Authorization": f"Bearer {DEEPSEEK_KEY}"},
        timeout=60
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"] if "choices" in data else "抱歉。"


def on_message(event):
    msg = event.event.message
    content = msg.content
    try:
        text = json.loads(content).get("text", "")
    except:
        text = content
    if not text.strip():
        return

    log.info(f"收到: {text[:60]}")
    answer = ask_deepseek(text)
    log.info(f"回答: {answer[:60]}")

    # 用 HTTP API 回复（不依赖 lark_oapi Client）
    reply_via_http(msg.message_id, answer)


def reply_via_http(msg_id: str, text: str):
    """直接调飞书 HTTP API 回复消息"""
    # 获取 tenant token
    resp = httpx.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={"app_id": APP_ID, "app_secret": APP_SECRET},
        timeout=10
    )
    token = resp.json().get("tenant_access_token", "")
    
    # 回复
    httpx.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"content": json.dumps({"text": text}), "msg_type": "text"},
        timeout=10
    )


# 构建事件处理器
handler = (
    EventDispatcherHandler
    .builder("", "")
    .register_p2_im_message_receive_v1(on_message)
    .build()
)

log.info("Aeon Tutor WebSocket 启动...")
ws = WSClient(
    app_id=APP_ID,
    app_secret=APP_SECRET,
    event_handler=handler,
    domain="https://open.feishu.cn",
    auto_reconnect=True
)
ws.start()
