#!/usr/bin/env python3
"""高数间隔复习提醒 —— 每日检查到期复习项"""

import os, json, time
from pathlib import Path

PROGRESS_FILE = Path("/root/.hermes/skills/math-tutor/references/progress.json")
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")

# 复习间隔（天）：掌握后 1→3→7→30
REVIEW_INTERVALS = [1, 3, 7, 30]

def check_reviews():
    if not PROGRESS_FILE.exists():
        return None
    
    with open(PROGRESS_FILE) as f:
        data = json.load(f)
    
    today = time.strftime("%Y-%m-%d")
    due = []
    
    for item in data.get("mastered", []):
        next_review = item.get("next_review", "")
        if next_review and next_review <= today:
            due.append(item)
    
    if not due:
        return None
    
    lines = ["📐 **到期复习提醒**\n"]
    for item in due:
        lines.append(f"• {item['name']}（上次掌握：{item.get('mastered_date', '?')}）")
    lines.append(f"\n共 {len(due)} 个知识点需要复习。跟家教说「复习」即可开始。")
    
    return "\n".join(lines)

if __name__ == "__main__":
    msg = check_reviews()
    if msg:
        print(msg)
    # 如果无消息，不输出（cron 静默）
