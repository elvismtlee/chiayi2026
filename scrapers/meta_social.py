"""
Meta 社群爬蟲 — Threads + Facebook 公開貼文
需要環境變數：META_APP_ID, META_APP_SECRET
Meta Graph API App Access Token = {APP_ID}|{APP_SECRET}
"""
import os
import re
import time
from datetime import datetime

import requests

TIMEOUT = 12
GRAPH_BASE = "https://graph.facebook.com/v19.0"
THREADS_BASE = "https://graph.threads.net/v1.0"

CITY_KEYWORDS = [
    "嘉義市", "西區", "東區", "市議會", "1999",
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


def _get_app_token() -> str | None:
    """App Access Token = APP_ID|APP_SECRET（不需要用戶授權）"""
    app_id = os.environ.get("META_APP_ID", "")
    app_secret = os.environ.get("META_APP_SECRET", "")
    if not app_id or not app_secret:
        return None
    return f"{app_id}|{app_secret}"


def _fmt_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%m/%d")
    except Exception:
        return ts[:10] if ts else ""


# ─── Threads ─────────────────────────────────────────────────────────────────

THREADS_SEARCH_QUERIES = ["嘉義市政", "嘉義市議員", "嘉義 道路 坑洞", "嘉義 路燈"]

# 已知嘉義市相關公開 Threads 帳號（可持續補充）
THREADS_PUBLIC_ACCOUNTS = [
    "chiayi_city_gov",     # 嘉義市政府（若有帳號）
    "chiayi2026",          # 候選人帳號
]


def fetch_threads(token: str, max_per_query: int = 8) -> list[dict]:
    posts: list[dict] = []
    seen: set[str] = set()

    headers = {"Authorization": f"Bearer {token}"} if not "|" in token else {}
    params_base = {"access_token": token} if "|" in token else {}

    # 嘗試 Threads 公開搜尋 API
    for query in THREADS_SEARCH_QUERIES:
        try:
            resp = requests.get(
                f"{THREADS_BASE}/threads/search",
                params={**params_base, "q": query, "fields": "id,text,username,timestamp,permalink", "limit": max_per_query},
                headers=headers,
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"  [threads] search '{query}' → {resp.status_code}: {resp.text[:100]}")
                continue
            data = resp.json().get("data", [])
            for item in data:
                tid = str(item.get("id", ""))
                text = item.get("text", "") or ""
                if tid in seen or not _is_relevant(text):
                    continue
                seen.add(tid)
                posts.append({
                    "id": f"threads-{tid}",
                    "platform": "Threads",
                    "platform_color": "#000000",
                    "board": item.get("username", ""),
                    "date": _fmt_date(item.get("timestamp", "")),
                    "author": f"@{item.get('username', '')}",
                    "title": text[:80].replace("\n", " "),
                    "excerpt": text[:120] if len(text) > 80 else "",
                    "url": item.get("permalink", f"https://www.threads.net/t/{tid}"),
                    "reactions": 0,
                    "comments": 0,
                    "category": _classify(text),
                    "source": "threads",
                })
        except Exception as e:
            print(f"  [threads] search 失敗: {str(e)[:80]}")
        time.sleep(0.3)

    print(f"  [threads] 共 {len(posts)} 篇")
    return posts


# ─── Facebook 公開粉絲頁 ──────────────────────────────────────────────────────

# 嘉義市相關公開 FB 粉絲頁 Page ID（可用頁面名稱或數字 ID）
FB_PAGES = [
    "chiayicitygov",        # 嘉義市政府
    "ChiayiCityCouncil",    # 嘉義市議會（若有）
    "100067049234879",      # 嘉義市政府官方 (數字 ID 備用)
]

FB_SEARCH_QUERIES = ["嘉義市政", "嘉義市 道路", "嘉義市 議員"]


def fetch_facebook(token: str, max_per_page: int = 10) -> list[dict]:
    posts: list[dict] = []
    seen: set[str] = set()

    # 方法 A：從已知粉絲頁抓最新貼文
    for page in FB_PAGES:
        try:
            resp = requests.get(
                f"{GRAPH_BASE}/{page}/posts",
                params={
                    "access_token": token,
                    "fields": "id,message,story,created_time,permalink_url,reactions.summary(true)",
                    "limit": max_per_page,
                },
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                print(f"  [fb] page '{page}' → {resp.status_code}")
                continue
            for item in resp.json().get("data", []):
                fid = str(item.get("id", ""))
                text = (item.get("message") or item.get("story") or "")
                if fid in seen or not text:
                    continue
                seen.add(fid)
                reactions = item.get("reactions", {}).get("summary", {}).get("total_count", 0)
                posts.append({
                    "id": f"fb-{fid}",
                    "platform": "Facebook",
                    "platform_color": "#1877F2",
                    "board": page,
                    "date": _fmt_date(item.get("created_time", "")),
                    "author": page,
                    "title": text[:80].replace("\n", " "),
                    "excerpt": text[80:160] if len(text) > 80 else "",
                    "url": item.get("permalink_url", f"https://www.facebook.com/{fid}"),
                    "reactions": reactions,
                    "comments": 0,
                    "category": _classify(text),
                    "source": "facebook",
                })
        except Exception as e:
            print(f"  [fb] page {page} 失敗: {str(e)[:80]}")
        time.sleep(0.4)

    # 方法 B：關鍵字搜尋公開貼文（需要 pages_read_engagement 權限）
    for query in FB_SEARCH_QUERIES[:2]:
        try:
            resp = requests.get(
                f"{GRAPH_BASE}/search",
                params={"access_token": token, "q": query, "type": "post",
                        "fields": "id,message,created_time,permalink_url", "limit": 8},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                continue
            for item in resp.json().get("data", []):
                fid = str(item.get("id", ""))
                text = item.get("message", "") or ""
                if fid in seen or not _is_relevant(text):
                    continue
                seen.add(fid)
                posts.append({
                    "id": f"fb-{fid}",
                    "platform": "Facebook",
                    "platform_color": "#1877F2",
                    "board": "公開貼文",
                    "date": _fmt_date(item.get("created_time", "")),
                    "author": "Facebook 用戶",
                    "title": text[:80].replace("\n", " "),
                    "url": item.get("permalink_url", ""),
                    "reactions": 0,
                    "comments": 0,
                    "category": _classify(text),
                    "source": "facebook",
                })
        except Exception as e:
            print(f"  [fb] search 失敗: {str(e)[:60]}")
        time.sleep(0.4)

    print(f"  [facebook] 共 {len(posts)} 篇")
    return posts


# ─── Instagram 公開標籤 ──────────────────────────────────────────────────────

IG_HASHTAGS = ["嘉義市政", "嘉義市議員", "嘉義市"]

# 需要 Instagram Business 帳號 ID（你的 IG 商業帳號）
# 設定環境變數 META_IG_USER_ID 為你的 IG 商業帳號 ID
def fetch_instagram(token: str, max_per_tag: int = 8) -> list[dict]:
    ig_user_id = os.environ.get("META_IG_USER_ID", "")
    if not ig_user_id:
        print("  [ig] 未設定 META_IG_USER_ID，跳過")
        return []

    posts: list[dict] = []
    seen: set[str] = set()

    for tag in IG_HASHTAGS:
        try:
            # Step 1: 搜尋 hashtag ID
            r1 = requests.get(
                f"{GRAPH_BASE}/ig_hashtag_search",
                params={"access_token": token, "user_id": ig_user_id, "q": tag},
                timeout=TIMEOUT,
            )
            if r1.status_code != 200:
                continue
            tag_id = r1.json().get("data", [{}])[0].get("id", "")
            if not tag_id:
                continue

            # Step 2: 取最新貼文
            r2 = requests.get(
                f"{GRAPH_BASE}/{tag_id}/recent_media",
                params={
                    "access_token": token, "user_id": ig_user_id,
                    "fields": "id,caption,permalink,timestamp,like_count,comments_count",
                    "limit": max_per_tag,
                },
                timeout=TIMEOUT,
            )
            if r2.status_code != 200:
                continue
            for item in r2.json().get("data", []):
                iid = str(item.get("id", ""))
                caption = item.get("caption", "") or ""
                if iid in seen:
                    continue
                seen.add(iid)
                posts.append({
                    "id": f"ig-{iid}",
                    "platform": "Instagram",
                    "platform_color": "#E1306C",
                    "board": f"#{tag}",
                    "date": _fmt_date(item.get("timestamp", "")),
                    "author": f"#{tag}",
                    "title": caption[:80].replace("\n", " ") if caption else f"#{tag} 相關貼文",
                    "excerpt": caption[80:160] if len(caption) > 80 else "",
                    "url": item.get("permalink", ""),
                    "reactions": item.get("like_count", 0),
                    "comments": item.get("comments_count", 0),
                    "category": _classify(caption),
                    "source": "instagram",
                })
        except Exception as e:
            print(f"  [ig] #{tag} 失敗: {str(e)[:60]}")
        time.sleep(0.4)

    print(f"  [instagram] 共 {len(posts)} 篇")
    return posts


# ─── 整合入口 ────────────────────────────────────────────────────────────────

def fetch_all_meta(max_items: int = 30) -> list[dict]:
    """爬取全 Meta 平台公開社群聲音"""
    token = _get_app_token()
    if not token:
        print("  [meta] 缺少 META_APP_ID / META_APP_SECRET，跳過")
        return []

    print(f"  [meta] 使用 App Token（App ID: {os.environ.get('META_APP_ID','?')[:6]}...）")

    buckets = {
        "threads": fetch_threads(token),
        "facebook": fetch_facebook(token),
        "instagram": fetch_instagram(token),
    }

    # 三平台交錯合併
    merged: list[dict] = []
    sources = [list(v) for v in buckets.values() if v]
    while len(merged) < max_items and any(sources):
        for src in list(sources):
            if src and len(merged) < max_items:
                merged.append(src.pop(0))
        sources = [s for s in sources if s]

    return merged[:max_items]
