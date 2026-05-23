"""Google News RSS 爬蟲 + 嘉義市政府開放資料新聞 — 嘉義市政、議員質詢相關新聞"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


QUERIES = [
    # 行政服務 / 議會
    "嘉義市 議員 質詢",
    "嘉義市議會 會議",
    "嘉義市 1999 陳情",
    "嘉義市西區 市政",
    # 交通停車
    "嘉義市 交通事故",
    "嘉義市 停車 違規",
    # 道路路平
    "嘉義市 道路 施工",
    "嘉義市 建設 工程",
    # 環境衛生
    "嘉義市 環境衛生 垃圾",
    "嘉義市 噪音 污染",
    # 排水水利
    "嘉義市 積水 淹水",
    "嘉義市 排水 水溝",
    # 公共安全
    "嘉義市 路燈 安全",
    "嘉義市 消防 事故",
    # 人行步道
    "嘉義市 人行道 步道",
    # 通學安全
    "嘉義市 通學 學童 安全",
    # 社福高齡
    "嘉義市 長照 高齡 社福",
    # 文化觀光
    "嘉義市 觀光 文化 活動",
    # 公園綠地
    "嘉義市 公園 綠地",
    # 市場商圈
    "嘉義市 夜市 市場",
    # 市民問題（兜底）
    "嘉義市 市民 問題",
]

# 嘉義市政府新聞開放資料
CHIAYI_GOV_NEWS_URL = (
    "https://data.chiayi.gov.tw/opendata/api/getResource/download"
    "?oid=6dcaf207-e99b-4846-bd72-c334ce0d4b59"
    "&rid=87d4b27c-07c3-4546-815d-1e733dfd9497"
)


def _fetch_chiayi_gov_news(max_items: int = 15) -> list[dict]:
    """抓取嘉義市政府開放資料平台新聞（官方發布）"""
    if not _HAS_REQUESTS:
        return []
    try:
        r = _requests.get(CHIAYI_GOV_NEWS_URL,
                          headers={"User-Agent": "Mozilla/5.0"},
                          timeout=20)
        if r.status_code != 200:
            return []
        items = r.json()
        news = []
        for item in items[:max_items]:
            title = item.get("title", "").strip()
            source_url = item.get("Source", "").strip()
            post_unit = item.get("PostUnit", "").strip()
            post_date = item.get("PostDate", "").strip()
            if not title:
                continue
            # 日期格式 2026/05/22 → 標準化
            date_str = post_date if post_date else ""
            news.append({
                "headline": title,
                "source": f"嘉義市政府/{post_unit}" if post_unit else "嘉義市政府",
                "link": source_url or "https://www.chiayi.gov.tw",
                "date": date_str,
                "query": "市府新聞",
            })
        print(f"  [news] 嘉義市政府新聞：{len(news)} 則")
        return news
    except Exception as e:
        print(f"  [news] 市府新聞抓取失敗: {e}")
        return []


def _fetch_rss(query: str, max_items: int = 8) -> list[dict]:
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        xml_data = urllib.request.urlopen(req, timeout=15).read()
        root = ET.fromstring(xml_data)
        items = []
        for item in root.findall("./channel/item")[:max_items]:
            title_full = item.find("title").text or ""
            headline, source = (
                title_full.rsplit(" - ", 1) if " - " in title_full else (title_full, "新聞")
            )
            pub_date = item.find("pubDate").text or ""
            try:
                dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z") + timedelta(hours=8)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                date_str = pub_date[:16]
            items.append({
                "headline": headline.strip(),
                "source": source.strip(),
                "link": item.find("link").text or "",
                "date": date_str,
                "query": query,
            })
        return items
    except Exception as e:
        print(f"  [news] 新聞爬蟲失敗 ({query}): {e}")
        return []


def fetch_all_news(max_per_query: int = 6) -> list[dict]:
    print("[news] 抓取新聞...")
    seen_headlines = set()
    results = []

    # 1. 嘉義市政府官方新聞（開放資料）
    for item in _fetch_chiayi_gov_news(15):
        if item["headline"] not in seen_headlines:
            seen_headlines.add(item["headline"])
            results.append(item)

    # 2. Google News RSS
    print("  [news] 抓取 Google News RSS...")
    for q in QUERIES:
        for item in _fetch_rss(q, max_per_query):
            if item["headline"] not in seen_headlines:
                seen_headlines.add(item["headline"])
                results.append(item)

    results.sort(key=lambda x: x["date"], reverse=True)
    print(f"  [news] 共取得 {len(results)} 則新聞")
    return results
