"""嘉義市政府開放資料平台爬蟲 + 中央 data.gov.tw 補充"""
import json
import urllib.request
import urllib.parse
from datetime import datetime


# 嘉義市開放資料平台 (自訂系統，非標準 CKAN)
CHIAYI_OPENDATA_BASE = "https://data.chiayi.gov.tw"

# 中央政府開放資料平台 CKAN API
GOV_TW_API = "https://data.gov.tw/api/v2/rest/dataset"

SEARCH_KEYWORDS = ["1999", "陳情", "投訴", "市民服務", "便民", "申訴"]
COUNCIL_KEYWORDS = ["議員", "質詢", "議會", "市政報告"]


def _http_get(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (research bot)",
                "Accept": "application/json, text/html",
            },
        )
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception as e:
        print(f"  [opendata] HTTP 失敗 {url}: {e}")
        return None


def _try_ckan_search(base: str, keyword: str, rows: int = 50) -> list[dict]:
    """嘗試標準 CKAN package_search API"""
    url = f"{base}/api/action/package_search?q={urllib.parse.quote(keyword)}&rows={rows}"
    raw = _http_get(url)
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if data.get("success") and data.get("result", {}).get("results"):
            return data["result"]["results"]
    except Exception:
        pass
    return []


def _try_chiayi_opendata_html(keyword: str) -> list[dict]:
    """爬嘉義市開放資料平台 HTML 搜尋頁，解析資料集列表"""
    from html.parser import HTMLParser

    url = f"{CHIAYI_OPENDATA_BASE}/datasets?q={urllib.parse.quote(keyword)}"
    raw = _http_get(url)
    if not raw:
        return []

    class DatasetParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.datasets = []
            self._in_title = False
            self._current = {}

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            cls = attrs_dict.get("class", "")
            href = attrs_dict.get("href", "")
            if tag == "a" and "/datasets/" in href and "edit" not in href:
                self._current = {"url": CHIAYI_OPENDATA_BASE + href}
                self._in_title = True

        def handle_data(self, data):
            if self._in_title and data.strip():
                self._current["title"] = data.strip()
                self._in_title = False
                if self._current.get("title") and self._current.get("url"):
                    self.datasets.append(self._current.copy())

    parser = DatasetParser()
    try:
        parser.feed(raw.decode("utf-8", errors="ignore"))
    except Exception:
        pass
    return parser.datasets


def fetch_opendata_datasets() -> list[dict]:
    """搜尋並回傳所有與 1999/陳情/市民服務相關的開放資料集"""
    print("[opendata] 搜尋嘉義市開放資料平台...")
    all_datasets = []
    seen_titles = set()

    for kw in SEARCH_KEYWORDS + COUNCIL_KEYWORDS:
        # 方法1: CKAN API
        results = _try_ckan_search(CHIAYI_OPENDATA_BASE, kw)
        for r in results:
            title = r.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_datasets.append({
                    "title": title,
                    "notes": r.get("notes", ""),
                    "url": f"{CHIAYI_OPENDATA_BASE}/datasets/{r.get('name', '')}",
                    "resources": [
                        {
                            "format": res.get("format", ""),
                            "url": res.get("url", ""),
                        }
                        for res in r.get("resources", [])
                    ],
                    "source": "data.chiayi.gov.tw",
                    "keyword": kw,
                })

        # 方法2: HTML 爬蟲
        for ds in _try_chiayi_opendata_html(kw):
            title = ds.get("title", "")
            if title and title not in seen_titles:
                seen_titles.add(title)
                all_datasets.append({
                    "title": title,
                    "url": ds.get("url", ""),
                    "source": "data.chiayi.gov.tw",
                    "keyword": kw,
                })

    print(f"  [opendata] 找到 {len(all_datasets)} 個資料集")
    return all_datasets


def fetch_opendata_records(resource_url: str) -> list[dict]:
    """下載單一資料集的 CSV/JSON 資料，回傳記錄列表"""
    if not resource_url:
        return []
    raw = _http_get(resource_url)
    if not raw:
        return []

    if resource_url.lower().endswith(".json"):
        try:
            return json.loads(raw)
        except Exception:
            return []

    if resource_url.lower().endswith(".csv"):
        import csv, io
        try:
            text = raw.decode("utf-8-sig", errors="ignore")
            reader = csv.DictReader(io.StringIO(text))
            return [dict(row) for row in reader]
        except Exception:
            return []

    return []


def build_complaint_stats(records: list[dict]) -> dict:
    """從原始記錄建立統計摘要，供儀表板圖表使用"""
    category_counts: dict[str, int] = {}
    road_counts: dict[str, int] = {}
    year_counts: dict[str, int] = {}

    for r in records:
        cat = r.get("議題分類") or r.get("類別") or r.get("category") or "其他"
        category_counts[cat] = category_counts.get(cat, 0) + 1

        road = r.get("發生路段") or r.get("地點") or r.get("location") or ""
        if road:
            key = road[:6]
            road_counts[key] = road_counts.get(key, 0) + 1

        date_str = r.get("通報日期") or r.get("date") or ""
        if len(date_str) >= 4:
            year = date_str[:4]
            year_counts[year] = year_counts.get(year, 0) + 1

    top_roads = sorted(road_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total": len(records),
        "category_counts": category_counts,
        "top_roads": [{"road": r, "count": c} for r, c in top_roads],
        "top_categories": [{"category": c, "count": n} for c, n in top_cats],
        "year_counts": year_counts,
        "updated_at": datetime.now().isoformat(),
    }
