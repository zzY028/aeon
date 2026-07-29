"""
Aeon Tutor — 轻量高数家教
无需数据库、无需 embedding、无需教材索引
直接用 DeepSeek V4 Pro 回答高数问题
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

SYSTEM_PROMPT = """你是高等数学家教。教学风格：

1. 先确认学生卡在哪里，不要直接给答案
2. 用苏格拉底式提问引导思考
3. 讲到关键定理时说明为什么这定理重要
4. 每道题讲完问"要不要做一道类似的题巩固"
5. 遇到 ε-N 语言或极限证明，分步骤展示推理过程
6. 用中文回答，语言简洁，不要堆砌术语

参考教材：同济八版《高等数学》"""

app = FastAPI(title="Aeon Tutor")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Question(BaseModel):
    message: str
    history: list[dict] = []  # [{"role":"user/assistant","content":"..."}]

@app.post("/ask")
async def ask(q: Question):
    if not DEEPSEEK_KEY:
        raise HTTPException(500, "API Key 未配置")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in q.history[-10:]:  # 最近 10 轮对话
        messages.append(h)
    messages.append({"role": "user", "content": q.message})

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(DEEPSEEK_URL, json={
            "model": "deepseek-v4-pro",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2048
        }, headers={
            "Authorization": f"Bearer {DEEPSEEK_KEY}",
            "Content-Type": "application/json"
        })
        data = resp.json()

    if "choices" not in data:
        raise HTTPException(500, f"API 错误: {data}")

    answer = data["choices"][0]["message"]["content"]
    tokens = data.get("usage", {})

    return {
        "answer": answer,
        "tokens": {
            "input": tokens.get("prompt_tokens", 0),
            "output": tokens.get("completion_tokens", 0)
        }
    }

@app.get("/health")
def health():
    return {"status": "ok", "service": "Aeon Tutor"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
