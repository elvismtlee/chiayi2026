"""
社群平台爬蟲 — PTT (Atom) + Dcard + Mobile01
爬取嘉義市相關市政議題貼文，匯入儀表板「市民社群聲音」區塊
"""
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests
from bs4 import BeautifulSoup

try:
    import cloudscraper
    _CLOUDSCRAPER = True
except ImportError:
    _CLOUDSCRAPER = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}
TIMEOUT = 12

CITY_KEYWORDS = [
    "嘉義市", "西區", "東區", "1999", "市議會",
    "路燈", "坑洞", "違停", "淹水", "垃圾",
    "市政", "市長", "議員", "陳情", "嘉義",
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


def _cf_get(url: str, **kwargs) -> requests.Response:
    """嘗試 cloudscraper，若未安裝則回退 requests"""
    if _CLOUDSCRAPER:
        scraper = cloudscraper.create_scraper()
        return scraper.get(url, **kwargs)
    return requests.get(url, headers=HEADERS, **kwargs)


# ─── PTT (Atom Feed) ─────────────────────────────────────────────────────────

PTT_BASE = "https://www.ptt.cc"
PTT_COOKIES = {"over18": "1"}
# PTT 官方 Atom Feed，不需登入，無 anti-bot
PTT_FEEDS = [
    ("Gossiping", f"{PTT_BASE}/atom/Gossiping.xml"),
    ("Chiayi", f"{PTT_BASE}/atom/Chiayi.xml"),        # 嘉義地方版
    ("PublicIssue", f"{PTT_BASE}/atom/PublicIssue.xml"),  # 公共議題
]
# 若 Atom 沒結果，再嘗試 web search
PTT_SEARCH_BOARDS_QUERIES = [
    ("Gossiping", "嘉義市"),
    ("Gossiping", "嘉義 市政"),
    ("Chiayi", "嘉義"),
]


def _parse_ptt_atom(board: str, xml_text: str) -> list[dict]:
    posts = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return posts
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    # 嘉義地方版所有貼文都相關，其他版需過濾
    local_boards = {"Chiayi", "ChiayiCity"}
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        link_el = entry.find("atom:link", ns)
        updated_el = entry.find("atom:updated", ns)
        if title_el is None or link_el is None:
            continue
        title = title_el.text or ""
        if board not in local_boards and not _is_relevant(title):
            continue
        href = link_el.get("href", "")
        date_str = ""
        if updated_el is not None and updated_el.text:
            try:
                dt = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
                date_str = dt.strftime("%m/%d")
            except Exception:
                date_str = updated_el.text[:10]
        posts.append({
            "id": f"ptt-{re.sub(r'[^a-zA-Z0-9]', '', href)}",
            "platform": "PTT",
            "platform_color": "#00b300",
            "board": board,
            "date": date_str,
            "author": "PTT 鄉民",
            "title": title,
            "url": href,
            "reactions": 0,
            "comments": 0,
            "category": _classify(title),
            "source": "ptt",
        })
    return posts


def _ptt_search(board: str, query: str, max_posts: int = 6) -> list[dict]:
    session = requests.Session()
    try:
        session.get(f"{PTT_BASE}/bbs/{board}/index.html",
                    headers=HEADERS, cookies=PTT_COOKIES, timeout=TIMEOUT)
    except Exception:
        pass
    try:
        resp = session.get(
            f"{PTT_BASE}/bbs/{board}/search",
            params={"q": query},
            headers=HEADERS, cookies=PTT_COOKIES, timeout=TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:
        err = str(e)
        if "404" not in err:
            print(f"  [ptt] {board}/{query} 搜尋失敗: {err[:70]}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    posts = []
    for ent in soup.select("div.r-ent")[:max_posts]:
        title_a = ent.select_one("div.title a")
        if not title_a:
            continue
        title = title_a.get_text(strip=True)
        href = title_a.get("href", "")
        if not href or not _is_relevant(title):
            continue
        date_el = ent.select_one("div.date")
        date_str = date_el.get_text(strip=True) if date_el else ""
        push_el = ent.select_one("div.nrec span")
        reactions = 0
        if push_el:
            raw = push_el.get_text(strip=True)
            try:
                reactions = int(raw)
            except Exception:
                reactions = 99 if raw == "爆" else 0
        posts.append({
            "id": f"ptt-{re.sub(r'[^a-zA-Z0-9]', '', href)}",
            "platform": "PTT",
            "platform_color": "#00b300",
            "board": board,
            "date": date_str,
            "author": "PTT 鄉民",
            "title": title,
            "url": PTT_BASE + href,
            "reactions": reactions,
            "comments": 0,
            "category": _classify(title),
            "source": "ptt",
        })
    return posts


def fetch_ptt(max_items: int = 12) -> list[dict]:
    all_posts: list[dict] = []
    seen: set[str] = set()

    # 優先嘗試 Atom Feed
    for board, feed_url in PTT_FEEDS:
        try:
            resp = requests.get(feed_url, headers=HEADERS, cookies=PTT_COOKIES, timeout=TIMEOUT)
            if resp.status_code == 404:
                continue  # 版面不存在，跳過
            resp.raise_for_status()
            for p in _parse_ptt_atom(board, resp.text):
                if p["id"] not in seen:
                    seen.add(p["id"])
                    all_posts.append(p)
        except Exception as e:
            print(f"  [ptt] {board} Atom feed 失敗: {str(e)[:60]}")

    # 若 Atom 結果不足，補充 web search
    if len(all_posts) < 5:
        for board, query in PTT_SEARCH_BOARDS_QUERIES:
            for p in _ptt_search(board, query, 6):
                if p["id"] not in seen:
                    seen.add(p["id"])
                    all_posts.append(p)
            time.sleep(0.8)

    result = all_posts[:max_items]
    print(f"  [ptt] 共 {len(result)} 篇相關貼文")
    return result


# ─── Dcard ──────────────────────────────────────────────────────────────────

DCARD_API = "https://www.dcard.tw/service/api/v2/search/posts"
DCARD_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.dcard.tw",
    "Referer": "https://www.dcard.tw/search?query=%E5%98%89%E7%BE%A9%E5%B8%82%E6%94%BF&tab=post",
    "x-dcard-client-type": "web",
    "x-dcard-app-version": "0.0.0",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}
DCARD_QUERIES = ["嘉義市政", "嘉義市議員", "嘉義 道路 問題", "嘉義 路燈 坑洞"]


def fetch_dcard(max_per_query: int = 6) -> list[dict]:
    all_posts: list[dict] = []
    seen: set[str] = set()

    session = requests.Session()
    csrf_token = ""
    try:
        home = session.get("https://www.dcard.tw/", headers=HEADERS, timeout=TIMEOUT)
        csrf_token = session.cookies.get("csrf-token", "")
        if not csrf_token:
            m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', home.text)
            if m:
                csrf_token = m.group(1)
    except Exception as e:
        print(f"  [dcard] 主頁取得失敗: {str(e)[:60]}")

    req_headers = {**DCARD_HEADERS}
    if csrf_token:
        req_headers["x-csrf-token"] = csrf_token

    for query in DCARD_QUERIES:
        try:
            resp = session.get(
                DCARD_API,
                params={"query": query, "limit": max_per_query, "type": "post"},
                headers=req_headers,
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            items = resp.json()
            if not isinstance(items, list):
                items = items.get("data", [])
        except Exception as e:
            print(f"  [dcard] 查詢「{query}」失敗: {str(e)[:60]}")
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
            date_str = ""
            if created:
                try:
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    date_str = dt.astimezone().strftime("%m/%d")
                except Exception:
                    date_str = created[:10]
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
                "reactions": item.get("likeCount", 0) or 0,
                "comments": item.get("commentCount", 0) or 0,
                "category": _classify(combined),
                "source": "dcard",
            })
        time.sleep(0.5)

    print(f"  [dcard] 共 {len(all_posts)} 篇相關貼文")
    return all_posts


# ─── Mobile01 ────────────────────────────────────────────────────────────────

MOBILE01_SEARCH = "https://www.mobile01.com/search.php"
MOBILE01_QUERIES = ["嘉義市政", "嘉義 道路", "嘉義 議員"]


def fetch_mobile01(max_per_query: int = 5) -> list[dict]:
    all_posts: list[dict] = []
    seen: set[str] = set()

    for query in MOBILE01_QUERIES:
        try:
            resp = _cf_get(
                MOBILE01_SEARCH,
                params={"q": query, "type": "topic"},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"  [mobile01] 查詢「{query}」失敗: {str(e)[:60]}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for item in soup.select("article.l-listItem, div.l-listItem, li.search-result")[:max_per_query]:
            a = item.select_one("a[href*='/topicdetail']") or item.select_one("h2 a, h3 a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not href or not _is_relevant(title):
                continue
            pid = re.sub(r"[^0-9]", "", href)[:12]
            uid = f"m01-{pid or re.sub(r'[^a-z0-9]', '', title[:20])}"
            if uid in seen:
                continue
            seen.add(uid)
            date_el = item.select_one("time, span.date, span.time")
            date_str = date_el.get("datetime", date_el.get_text(strip=True))[:10] if date_el else ""
            full_url = href if href.startswith("http") else f"https://www.mobile01.com{href}"
            all_posts.append({
                "id": uid,
                "platform": "Mobile01",
                "platform_color": "#e07b00",
                "board": "論壇",
                "date": date_str,
                "author": "Mobile01 用戶",
                "title": title,
                "url": full_url,
                "reactions": 0,
                "comments": 0,
                "category": _classify(title),
                "source": "mobile01",
            })
        time.sleep(0.6)

    print(f"  [mobile01] 共 {len(all_posts)} 篇相關貼文")
    return all_posts


# ─── 整合入口 ────────────────────────────────────────────────────────────────

def fetch_all_social(max_items: int = 30) -> list[dict]:
    """爬取全平台社群聲音，回傳合併排序後清單"""
    buckets = {
        "ptt": fetch_ptt(),
        "dcard": fetch_dcard(),
        "mobile01": fetch_mobile01(),
    }

    # 三平台交錯合併，確保多樣性
    merged: list[dict] = []
    sources = [list(v) for v in buckets.values() if v]
    while len(merged) < max_items and any(sources):
        for src in list(sources):
            if src and len(merged) < max_items:
                merged.append(src.pop(0))
        sources = [s for s in sources if s]

    return merged[:max_items]
