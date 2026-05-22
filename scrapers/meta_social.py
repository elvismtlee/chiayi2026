"""
Meta 社群爬蟲 — Threads (User Token) + Facebook 公開粉絲頁
環境變數：
  THREADS_USER_TOKEN  — Graph API Explorer 產生的長效 User Access Token
  META_APP_ID         — App ID（用於 Facebook Graph API）
  META_APP_SECRET     — App Secret
  META_IG_USER_ID     — IG 商業帳號 ID（選用）
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

# 已知嘉義市相關公開 Threads 帳號（補充即生效）
CHIAYI_THREADS_ACCOUNTS = [
    # "chiayi_city_gov",   # 嘉義市政府 Threads 帳號（若有）
    # "chiayi_council",    # 嘉義市議會
]


def _classify(text: str) -> str:
    for cat, kws in ISSUE_KEYWORDS.items():
        if any(k in text for k in kws):
            return cat
    return "市政議題"


def _is_relevant(text: str) -> bool:
    return any(k in text for k in CITY_KEYWORDS)


def _fmt_date(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%m/%d")
    except Exception:
        return ts[:10] if ts else ""


def _get_app_token() -> str | None:
    app_id = os.environ.get("META_APP_ID", "")
    app_secret = os.environ.get("META_APP_SECRET", "")
    if app_id and app_secret:
        return f"{app_id}|{app_secret}"
    return None


# ─── Threads ─────────────────────────────────────────────────────────────────

def _threads_get(path: str, token: str, **params) -> dict:
    r = requests.get(
        f"{THREADS_BASE}/{path.lstrip('/')}",
        params={"access_token": token, **params},
        timeout=TIMEOUT,
    )
    return r.json() if r.status_code == 200 else {"error": r.text[:200], "status": r.status_code}


def _parse_thread_item(item: dict, username: str = "") -> dict | None:
    tid = str(item.get("id", ""))
    text = item.get("text", "") or ""
    media_type = item.get("media_type", "TEXT")
    if not tid:
        return None
    return {
        "id": f"threads-{tid}",
        "platform": "Threads",
        "platform_color": "#000000",
        "board": f"@{username}" if username else "",
        "date": _fmt_date(item.get("timestamp", "")),
        "author": f"@{username}" if username else "Threads",
        "title": text[:100].replace("\n", " ") if text else f"[{media_type}]",
        "excerpt": text[100:200].replace("\n", " ") if len(text) > 100 else "",
        "url": item.get("permalink", f"https://www.threads.net/t/{tid}"),
        "reactions": item.get("like_count", 0) or 0,
        "comments": item.get("replies_count", 0) or 0,
        "category": _classify(text),
        "source": "threads",
    }


def fetch_threads(max_posts: int = 20) -> list[dict]:
    token = os.environ.get("THREADS_USER_TOKEN", "")
    if not token:
        print("  [threads] 未設定 THREADS_USER_TOKEN，跳過")
        return []

    posts: list[dict] = []
    seen: set[str] = set()

    # 取自己帳號資訊
    me_info = _threads_get("me", token, fields="id,username,name")
    me_username = me_info.get("username", "")
    me_id = me_info.get("id", "")
    if not me_username:
        print(f"  [threads] 無法取得帳號資訊: {me_info}")
        return []

    # 抓所有貼文，過濾嘉義相關
    d = _threads_get("me/threads", token,
                     fields="id,text,timestamp,permalink,media_type,like_count,replies_count",
                     limit=50)
    if "data" not in d:
        print(f"  [threads] 貼文取得失敗: {d.get('error','')[:80]}")
        return []

    chiayi_posts = []
    all_posts_count = len(d["data"])
    for item in d["data"]:
        text = item.get("text", "") or ""
        p = _parse_thread_item(item, me_username)
        if not p:
            continue
        if _is_relevant(text):
            p["board"] = "嘉義市政"
            chiayi_posts.append(p)
        if p["id"] not in seen:
            seen.add(p["id"])

    # 嘉義相關貼文優先；若不足 5 篇則補充最新貼文
    result = chiayi_posts[:max_posts]
    if len(result) < 5:
        for item in d["data"][:max_posts]:
            p = _parse_thread_item(item, me_username)
            if p and p["id"] not in [r["id"] for r in result]:
                result.append(p)
            if len(result) >= max_posts:
                break

    print(f"  [threads] @{me_username}: {all_posts_count} 篇中 {len(chiayi_posts)} 篇嘉義相關，顯示 {len(result)} 篇")
    return result[:max_posts]


# ─── Facebook 粉絲頁 ──────────────────────────────────────────────────────────

# 嘉義市官方 / 相關粉絲頁 Page ID
# 用 Graph API Explorer 查詢：GET /{page-username}?fields=id,name
FB_PAGES = [
    "116818208341413",   # 嘉義市政府（官方，需確認）
    "ChiayiCity",
    "chiayi.city.gov",
]


def fetch_facebook(max_per_page: int = 10) -> list[dict]:
    token = _get_app_token()
    if not token:
        print("  [facebook] 缺少 META_APP_ID/META_APP_SECRET，跳過")
        return []

    # 嘗試用 User Token（若有）替代 App Token，權限更多
    user_token = os.environ.get("THREADS_USER_TOKEN", "")

    posts: list[dict] = []
    seen: set[str] = set()

    for page in FB_PAGES:
        use_token = user_token or token
        try:
            r = requests.get(
                f"{GRAPH_BASE}/{page}/posts",
                params={
                    "access_token": use_token,
                    "fields": "id,message,story,created_time,permalink_url,reactions.summary(true)",
                    "limit": max_per_page,
                },
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                print(f"  [fb] {page} → {r.status_code}: {r.json().get('error',{}).get('message','')[:60]}")
                continue
            for item in r.json().get("data", []):
                fid = str(item.get("id", ""))
                text = (item.get("message") or item.get("story") or "").strip()
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
                    "title": text[:100].replace("\n", " "),
                    "excerpt": text[100:200].replace("\n", " ") if len(text) > 100 else "",
                    "url": item.get("permalink_url", ""),
                    "reactions": reactions,
                    "comments": 0,
                    "category": _classify(text),
                    "source": "facebook",
                })
        except Exception as e:
            print(f"  [fb] {page} 失敗: {str(e)[:60]}")
        time.sleep(0.4)

    print(f"  [facebook] 共 {len(posts)} 篇")
    return posts


# ─── Instagram 標籤 ──────────────────────────────────────────────────────────

def fetch_instagram(max_per_tag: int = 8) -> list[dict]:
    token = _get_app_token() or os.environ.get("THREADS_USER_TOKEN", "")
    ig_user_id = os.environ.get("META_IG_USER_ID", "")
    if not token or not ig_user_id:
        print("  [ig] 缺少 token 或 META_IG_USER_ID，跳過")
        return []

    posts: list[dict] = []
    seen: set[str] = set()

    for tag in ["嘉義市政", "嘉義市議員", "嘉義市"]:
        try:
            r1 = requests.get(f"{GRAPH_BASE}/ig_hashtag_search",
                              params={"access_token": token, "user_id": ig_user_id, "q": tag},
                              timeout=TIMEOUT)
            if r1.status_code != 200:
                continue
            tag_id = (r1.json().get("data") or [{}])[0].get("id", "")
            if not tag_id:
                continue
            r2 = requests.get(f"{GRAPH_BASE}/{tag_id}/recent_media",
                              params={"access_token": token, "user_id": ig_user_id,
                                      "fields": "id,caption,permalink,timestamp,like_count,comments_count",
                                      "limit": max_per_tag},
                              timeout=TIMEOUT)
            if r2.status_code != 200:
                continue
            for item in r2.json().get("data", []):
                iid = str(item.get("id", ""))
                caption = (item.get("caption") or "").strip()
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
                    "title": (caption[:100].replace("\n", " ") if caption else f"#{tag} 貼文"),
                    "excerpt": caption[100:200] if len(caption) > 100 else "",
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
    has_threads = bool(os.environ.get("THREADS_USER_TOKEN"))
    has_app = bool(os.environ.get("META_APP_ID"))

    if not has_threads and not has_app:
        print("  [meta] 無任何 Meta 憑證，跳過")
        return []

    buckets = {
        "threads": fetch_threads() if has_threads else [],
        "facebook": fetch_facebook() if has_app else [],
        "instagram": fetch_instagram() if has_app and os.environ.get("META_IG_USER_ID") else [],
    }

    merged: list[dict] = []
    sources = [list(v) for v in buckets.values() if v]
    while len(merged) < max_items and any(sources):
        for src in list(sources):
            if src and len(merged) < max_items:
                merged.append(src.pop(0))
        sources = [s for s in sources if s]

    return merged[:max_items]
