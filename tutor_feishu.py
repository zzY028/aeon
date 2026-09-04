"""
Aeon Tutor — 飞书高数家教 (纯 HTTP API)
"""

import os, json, time, hashlib, hmac
import httpx
from flask import Flask, request, jsonify

APP_ID = os.getenv("TUTOR_APP_ID", "")
APP_SECRET = os.getenv("TUTOR_APP_SECRET", "")
ds_key = os.getenv("DEEPSEEK_API_KEY", "")

app = Flask(__name__)
token_cache = {"token": "", "expires": 0}


def get_tenant_token():
    """获取飞书 tenant_access_token"""
    now = time.time()
    if token_cache["token"] and token_cache["expires"] > now + 60:
        return token_cache["token"]

    resp = httpx.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                      json={"app_id": APP_ID, "app_secret": APP_SECRET}, timeout=10)
    data = resp.json()
    token = data.get("tenant_access_token", "")
    expires = now + data.get("expire", 7200)
    token_cache["token"] = token
    token_cache["expires"] = expires
    return token


def reply_message(msg_id: str, text: str):
    """回复飞书消息"""
    token = get_tenant_token()
    httpx.post(
        f"https://open.feishu.cn/open-apis/im/v1/messages/{msg_id}/reply",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"content": json.dumps({"text": text})},
        timeout=10
    )


def ask_deepseek(question: str) -> str:
    """调用 DeepSeek 高数家教"""
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
        headers={"Authorization": f"Bearer {ds_key}", "Content-Type": "application/json"},
        timeout=60
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"] if "choices" in data else "抱歉，暂时无法回答。"


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/event", methods=["POST"])
def event():
    body = request.json or {}

    # URL 验证
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})

    # 消息事件
    header = body.get("header", {})
    if header.get("event_type") == "im.message.receive_v1":
        msg = body.get("event", {}).get("message", {})
        content = msg.get("content", "{}")
        try:
            text = json.loads(content).get("text", "")
        except:
            text = content

        if text.strip():
            answer = ask_deepseek(text)
            reply_message(msg.get("message_id", ""), answer)

    return jsonify({"code": 0})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002)
