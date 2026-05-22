"""Google News RSS 爬蟲 — 嘉義市政、議員質詢相關新聞"""
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta


QUERIES = [
    "嘉義市 議員 質詢",
    "嘉義市議會 會議",
    "嘉義市 1999 陳情",
    "嘉義市西區 市政",
    "嘉義市 交通事故",
    "嘉義市 建設 工程",
    "嘉義市 道路 施工",
    "嘉義市 市民 問題",
]


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
    print("[news] 抓取 Google News RSS...")
    seen_headlines = set()
    results = []
    for q in QUERIES:
        for item in _fetch_rss(q, max_per_query):
            if item["headline"] not in seen_headlines:
                seen_headlines.add(item["headline"])
                results.append(item)
    results.sort(key=lambda x: x["date"], reverse=True)
    print(f"  [news] 共取得 {len(results)} 則新聞")
    return results
