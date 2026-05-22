"""嘉義市議會爬蟲 — 議員質詢紀錄 + 會議記錄"""
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser


# 嘉義市議會網站（主要）
COUNCIL_BASE = "https://www.chiayi-city-council.gov.tw"

# 備用：立法院地方議會會議資料（若有整合）
BACKUP_URLS = [
    "https://www.chiayi-city-council.gov.tw/PublicInfo/MeetingMinutes",
    "https://www.chiayi-city-council.gov.tw/PublicInfo/Councilor",
    "https://www.chiayi-city-council.gov.tw/PublicInfo/Question",
]

# 現任嘉義市議員名單（第 9 屆，用於比對爬到的資料）
COUNCILORS = [
    "蕭淑玲", "陳怡岳", "蔡明儀", "林建豐", "柳宗廷", "吳竟銓",
    "徐欣瑩", "謝明匡", "許明財", "劉蓁蓁", "蕭貫譽", "王美惠",
    "廖怡琛", "郭明賓", "李明進", "陳靜思", "唐美玲",
]


def _http_get(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (research bot)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        return urllib.request.urlopen(req, timeout=timeout).read()
    except Exception as e:
        print(f"  [council] HTTP 失敗 {url}: {e}")
        return None


class MeetingListParser(HTMLParser):
    """解析議會網站會議紀錄列表頁"""

    def __init__(self):
        super().__init__()
        self.meetings = []
        self._in_row = False
        self._current = {}
        self._col = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "tr":
            self._in_row = True
            self._current = {}
            self._col = 0
        if tag == "td" and self._in_row:
            self._col += 1
        if tag == "a" and self._in_row:
            href = attrs_dict.get("href", "")
            if href:
                self._current["url"] = (
                    COUNCIL_BASE + href if not href.startswith("http") else href
                )

    def handle_data(self, data):
        data = data.strip()
        if not data or not self._in_row:
            return
        if self._col == 1:
            self._current["term"] = data        # 屆別
        elif self._col == 2:
            self._current["session"] = data     # 會期
        elif self._col == 3:
            self._current["type"] = data        # 類型（定期會/臨時會）
        elif self._col == 4:
            self._current["date"] = data        # 日期

    def handle_endtag(self, tag):
        if tag == "tr" and self._in_row and self._current.get("date"):
            self.meetings.append(self._current.copy())
            self._in_row = False
            self._current = {}
            self._col = 0


def fetch_meeting_list(page: int = 1, per_page: int = 50) -> list[dict]:
    """抓取議會會議紀錄列表"""
    print(f"  [council] 抓取會議紀錄列表 (第 {page} 頁)...")
    url = f"{COUNCIL_BASE}/PublicInfo/MeetingMinutes?page={page}&pageSize={per_page}"
    raw = _http_get(url)
    if not raw:
        return []
    parser = MeetingListParser()
    try:
        parser.feed(raw.decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f"  [council] 解析失敗: {e}")
    return parser.meetings


def fetch_councilor_list() -> list[dict]:
    """抓取現任議員清單"""
    print("  [council] 抓取議員清單...")
    url = f"{COUNCIL_BASE}/PublicInfo/Councilor"
    raw = _http_get(url)
    if not raw:
        # 回傳已知名單
        return [{"name": name, "source": "known"} for name in COUNCILORS]

    html = raw.decode("utf-8", errors="ignore")
    councilors = []
    seen = set()
    for name in COUNCILORS:
        if name in html and name not in seen:
            seen.add(name)
            councilors.append({"name": name, "source": "scraped"})

    name_pattern = re.compile(r"([一-鿿]{2,4})議員")
    for match in name_pattern.finditer(html):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            councilors.append({"name": name, "source": "scraped"})

    return councilors if councilors else [{"name": n, "source": "fallback"} for n in COUNCILORS]


def fetch_question_records(year_start: int = 2013, year_end: int = 2026) -> list[dict]:
    """嘗試抓取歷年質詢紀錄（HTML 頁面）"""
    print(f"  [council] 抓取質詢紀錄 ({year_start}–{year_end})...")
    records = []

    for year in range(year_start, year_end + 1):
        url = f"{COUNCIL_BASE}/PublicInfo/Question?year={year}"
        raw = _http_get(url)
        if not raw:
            continue
        html = raw.decode("utf-8", errors="ignore")

        # 用 councillor 名字在 HTML 中找質詢關鍵詞
        for name in COUNCILORS:
            if name in html:
                idx = html.find(name)
                snippet = html[max(0, idx - 50): idx + 200]
                snippet_clean = re.sub(r"<[^>]+>", "", snippet).strip()
                if len(snippet_clean) > 10:
                    records.append({
                        "councilor": name,
                        "year": year,
                        "snippet": snippet_clean,
                        "source_url": url,
                    })

    print(f"  [council] 找到 {len(records)} 筆質詢片段")
    return records


def fetch_all_council_data() -> dict:
    """主函式：抓取所有議會資料，回傳結構化字典"""
    meetings = fetch_meeting_list(page=1)
    councilors = fetch_councilor_list()
    questions = fetch_question_records()

    return {
        "meetings": meetings,
        "councilors": councilors,
        "question_records": questions,
        "councilor_names": COUNCILORS,
        "updated_at": datetime.now().isoformat(),
    }
