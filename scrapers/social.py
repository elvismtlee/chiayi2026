"""
社群平台爬蟲 — PTT + Dcard
爬取嘉義市相關市政議題貼文，匯入儀表板「市民社群聲音」區塊
"""
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 10

CITY_KEYWORDS = [
    "嘉義市", "西區", "東區", "1999", "市議會",
    "路燈", "坑洞", "違停", "淹水", "垃圾",
    "市政", "市長", "議員", "陳情",
]

ISSUE_KEYWORDS = {
    "道路工程": ["坑洞", "路面", "柏油", "施工", "道路", "路段"],
    "停車亂象": ["違停", "停車", "佔用", "騎樓", "人行道"],
    "路燈照明": ["路燈", "燈", "照明", "黑暗"],
    "水溝排水": ["淹水", "水溝", "排水", "溝渠"],
    "環境衛生": ["垃圾", "清潔", "廢棄物", "蚊蟲", "臭味"],
    "噪音管制": ["噪音", "吵鬧", "擾民"],
    "綠化景觀": ["公園", "樹木", "草皮"],
}


def _classify(text: str) -> str:
    for cat, kws in ISSUE_KEYWORDS.items():
        if any(k in text for k in kws):
            return cat
    return "市政議題"


def _is_relevant(text: str) -> bool:
    return any(k in text for k in CITY_KEYWORDS)


# ─── PTT ────────────────────────────────────────────────────────────────────

PTT_BOARDS = ["Gossiping", "C_Chiayi"]
PTT_QUERIES = ["嘉義市", "嘉義 議員", "嘉義 道路", "嘉義 市政"]
PTT_BASE = "https://www.ptt.cc"
PTT_COOKIES = {"over18": "1"}


def _ptt_search_board(board: str, query: str, max_posts: int = 6) -> list[dict]:
    url = f"{PTT_BASE}/bbs/{board}/search"
    try:
        resp = requests.get(
            url, params={"q": query},
            headers=HEADERS, cookies=PTT_COOKIES, timeout=TIMEOUT
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  [ptt] {board} 搜尋失敗: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = []
    for ent in soup.select("div.r-ent")[:max_posts]:
        title_a = ent.select_one("div.title a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        href = title_a.get("href", "")
        # skip deleted posts
        if not href or "deleted" in title.lower():
            continue

        date_el = ent.select_one("div.date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        author_el = ent.select_one("div.author")
        author = author_el.get_text(strip=True) if author_el else "匿名"
        push_el = ent.select_one("div.nrec span")
        reactions = 0
        if push_el:
            try:
                reactions = int(push_el.get_text(strip=True))
            except Exception:
                reactions = 99 if push_el.get_text(strip=True) == "爆" else 0

        full_url = PTT_BASE + href
        posts.append({
            "id": f"ptt-{re.sub(r'[^a-zA-Z0-9]', '', href)}",
            "platform": "PTT",
            "platform_color": "#00b300",
            "board": board,
            "date": date_str,
            "author": author,
            "title": title,
            "url": full_url,
            "reactions": reactions,
            "comments": 0,
            "category": _classify(title),
            "source": "ptt",
        })
    return posts


def fetch_ptt(max_per_board: int = 8) -> list[dict]:
    all_posts: list[dict] = []
    seen: set[str] = set()

    for board in PTT_BOARDS:
        for query in PTT_QUERIES[:2]:  # 每板爬 2 個 query
            posts = _ptt_search_board(board, query, max_per_board)
            for p in posts:
                if p["id"] not in seen and _is_relevant(p["title"]):
                    seen.add(p["id"])
                    all_posts.append(p)
            time.sleep(0.5)

    print(f"  [ptt] 共 {len(all_posts)} 篇相關貼文")
    return all_posts


# ─── Dcard ──────────────────────────────────────────────────────────────────

DCARD_API = "https://www.dcard.tw/service/api/v2/search/posts"
DCARD_QUERIES = ["嘉義市政", "嘉義市議員", "嘉義 道路 問題", "嘉義 路燈 坑洞"]


def fetch_dcard(max_per_query: int = 6) -> list[dict]:
    all_posts: list[dict] = []
    seen: set[str] = set()

    for query in DCARD_QUERIES:
        try:
            resp = requests.get(
                DCARD_API,
                params={"query": query, "limit": max_per_query},
                headers={**HEADERS, "Referer": "https://www.dcard.tw/"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            items = resp.json()
            if not isinstance(items, list):
                items = items.get("data", [])
        except Exception as e:
            print(f"  [dcard] 查詢「{query}」失敗: {e}")
            continue

        for item in items:
            pid = str(item.get("id", ""))
            if not pid or pid in seen:
                continue

            title = item.get("title", "")
            excerpt = item.get("excerpt", "") or ""
            combined = title + " " + excerpt

            if not _is_relevant(combined):
                continue

            seen.add(pid)
            forum = item.get("forumName", item.get("school", ""))
            created = item.get("createdAt", "")
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    date_str = dt.astimezone().strftime("%m/%d")
                except Exception:
                    date_str = created[:10]
            else:
                date_str = ""

            like = item.get("likeCount", 0) or 0
            cmt = item.get("commentCount", 0) or 0

            all_posts.append({
                "id": f"dcard-{pid}",
                "platform": "Dcard",
                "platform_color": "#ff6b6b",
                "board": forum,
                "date": date_str,
                "author": "Dcard 用戶",
                "title": title,
                "excerpt": excerpt[:80],
                "url": f"https://www.dcard.tw/f/talk/p/{pid}",
                "reactions": like,
                "comments": cmt,
                "category": _classify(combined),
                "source": "dcard",
            })
        time.sleep(0.4)

    print(f"  [dcard] 共 {len(all_posts)} 篇相關貼文")
    return all_posts


# ─── 整合入口 ────────────────────────────────────────────────────────────────

def fetch_all_social(max_items: int = 30) -> list[dict]:
    """爬取全平台社群聲音，回傳合併排序後清單"""
    posts: list[dict] = []
    posts.extend(fetch_ptt())
    posts.extend(fetch_dcard())

    # 依平台交錯排列（避免一個平台佔滿），最後截斷
    ptt = [p for p in posts if p["source"] == "ptt"]
    dcard = [p for p in posts if p["source"] == "dcard"]
    merged: list[dict] = []
    for a, b in zip(ptt, dcard):
        merged.extend([a, b])
    merged += ptt[len(dcard):] + dcard[len(ptt):]

    return merged[:max_items]
