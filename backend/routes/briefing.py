"""Aeon 早报解析：HTML → 结构化 JSON，前端用 Aeon 风格渲染"""
import os
import glob
import re
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException

from config import BRIEFING_DIR

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


def latest_briefing_path() -> str | None:
    files = glob.glob(os.path.join(BRIEFING_DIR, "早报_*.html"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def parse_briefing(html: str) -> dict:
    """把早报 HTML 解析成结构化 JSON"""
    soup = BeautifulSoup(html, "html.parser")

    # 标题 + 日期
    h1 = soup.select_one(".header h1")
    date_sub = soup.select_one(".date-sub")
    title = h1.get_text(strip=True) if h1 else "早报"
    date = date_sub.get_text(strip=True) if date_sub else ""

    # 引言（名言）
    quote_el = soup.select_one(".quote")
    quote = ""
    quote_src = ""
    if quote_el:
        quote = quote_el.get_text("\n", strip=True).split("\n")[0] if quote_el else ""
        src = quote_el.select_one(".src")
        quote_src = src.get_text(strip=True) if src else ""

    # 卡片：识别类型
    cards = []
    for card in soup.select(".card"):
        h2 = card.select_one("h2")
        if not h2:
            continue
        card_title = h2.get_text(" ", strip=True)
        icon = ""
        icon_el = h2.select_one(".icon")
        if icon_el:
            icon = icon_el.get_text(strip=True)
            # 去掉 icon 后的标题
            icon_el.decompose()
            card_title = h2.get_text(" ", strip=True).strip()

        card_data = {"icon": icon, "title": card_title, "type": "text", "body": []}

        # 天气卡
        if card.select_one(".weather-top"):
            temp = card.select_one(".weather-temp")
            desc = card.select_one(".weather-desc")
            card_data["type"] = "weather"
            card_data["temp"] = temp.get_text(" ", strip=True) if temp else ""
            card_data["desc"] = desc.get_text("<br>", strip=True) if desc else ""
            grid = []
            for item in card.select(".weather-grid .w-item"):
                label = item.select_one(".label")
                value = item.select_one(".value")
                grid.append({"label": label.get_text(strip=True) if label else "",
                             "value": value.get_text(strip=True) if value else ""})
            card_data["grid"] = grid
            cards.append(card_data)
            continue

        # 苏菲卡
        sophie = card.select_one(".sophie-text")
        if sophie:
            card_data["type"] = "sophie"
            card_data["text"] = sophie.get_text("\n", strip=True)
            end = card.select_one(".sophie-end")
            card_data["end"] = end.get_text(strip=True) if end else ""
            cards.append(card_data)
            continue

        # 新闻卡
        news_cats = []
        current_cat = None
        for el in card.children:
            if el.name == "div" and "news-cat" in el.get("class", []):
                if current_cat:
                    news_cats.append(current_cat)
                current_cat = {"name": el.get_text(strip=True).lstrip("▎ ").strip(), "items": []}
            elif el.name == "div" and "news-item" in el.get("class", []):
                n_title = el.select_one(".n-title")
                n_body = el.select_one(".n-body")
                n_src = el.select_one(".n-src")
                # 专有名词解释（details 折叠块）
                n_explain = None
                det = el.select_one("details")
                if det:
                    summary = det.select_one("summary")
                    d_body = det.select_one(".d-body")
                    n_explain = {
                        "label": summary.get_text(strip=True) if summary else "",
                        "body": d_body.get_text(" ", strip=True) if d_body else "",
                    }
                if current_cat is None:
                    current_cat = {"name": "新闻", "items": []}
                current_cat["items"].append({
                    "title": n_title.get_text(strip=True) if n_title else "",
                    "body": n_body.get_text(strip=True) if n_body else "",
                    "src": n_src.get_text(" ", strip=True) if n_src else "",
                    "explain": n_explain,
                })
        if current_cat:
            news_cats.append(current_cat)

        if news_cats:
            card_data["type"] = "news"
            card_data["categories"] = news_cats
            cards.append(card_data)
            continue

        # 通用文本卡（token/提醒/牙齿等）：保留纯文本
        texts = []
        for p in card.select("p, li, .token-row, .remind-item, .teeth-steps, .token-total, .teeth-warn"):
            t = p.get_text(" ", strip=True)
            if t:
                texts.append(t)
        if texts:
            card_data["type"] = "text"
            card_data["body"] = texts
            cards.append(card_data)

    # 收尾
    footer = soup.select_one(".footer")
    footer_text = footer.get_text("\n", strip=True) if footer else ""

    return {
        "title": title,
        "date": date,
        "quote": quote,
        "quote_src": quote_src,
        "cards": cards,
        "footer": footer_text,
    }


@router.get("")
def get_briefing():
    """返回解析后的早报结构化数据"""
    path = latest_briefing_path()
    if not path:
        raise HTTPException(status_code=404, detail="暂无早报")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    try:
        data = parse_briefing(html)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"早报解析失败：{str(e)}")
    data["file"] = os.path.basename(path)
    return data


@router.get("/raw")
def get_briefing_raw():
    """返回最新早报 HTML 原文（兼容旧版）"""
    path = latest_briefing_path()
    if not path:
        raise HTTPException(status_code=404, detail="暂无早报")
    with open(path, encoding="utf-8") as f:
        return {"file": os.path.basename(path), "html": f.read()}


@router.get("/dates")
def list_briefing_dates():
    """列出所有早报日期"""
    files = sorted(glob.glob(os.path.join(BRIEFING_DIR, "早报_*.html")), reverse=True)
    return [{"file": os.path.basename(f), "date": os.path.basename(f).replace("早报_", "").replace(".html", "")} for f in files]
