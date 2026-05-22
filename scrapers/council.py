"""嘉義市議會爬蟲 — 議員質詢紀錄 + 會議記錄
官方網站：https://www.cycc.gov.tw/Default.aspx（ASP.NET WebForms，SSL 憑證無效）
"""
import json
import re
import warnings
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)

# 嘉義市議會正確網址（舊址 chiayi-city-council.gov.tw 已失效）
COUNCIL_BASE = "https://www.cycc.gov.tw"
COUNCIL_DEFAULT = f"{COUNCIL_BASE}/Default.aspx"

# 現任嘉義市議員名單（第 9 屆，用於比對爬到的資料）
COUNCILORS = [
    "蕭淑玲", "陳怡岳", "蔡明儀", "林建豐", "柳宗廷", "吳竟銓",
    "徐欣瑩", "謝明匡", "許明財", "劉蓁蓁", "蕭貫譽", "王美惠",
    "廖怡琛", "郭明賓", "李明進", "陳靜思", "唐美玲",
]


def _http_get(url: str, timeout: int = 20) -> bytes | None:
    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 (research bot)",
                     "Accept": "text/html,application/xhtml+xml"},
            timeout=timeout,
            verify=False,  # cycc.gov.tw SSL 憑證無效，略過驗證
        )
        return r.content if r.status_code == 200 else None
    except Exception as e:
        print(f"  [council] HTTP 失敗 {url}: {e}")
        return None


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "big5", "cp950"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


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


COUNCIL_ANNOUNCE_URL = f"{COUNCIL_BASE}/web/AnnF/listAnnounce.aspx?c0=4769"
COUNCIL_SCHEDULE_URL = f"{COUNCIL_BASE}/web/schedule/listschedule.aspx?c0=3673"


def fetch_meeting_list(page: int = 1, per_page: int = 50) -> list[dict]:
    """抓取議會會議紀錄（從公報公告頁面解析）"""
    print(f"  [council] 抓取會議紀錄列表...")
    meetings = []

    # 1. 首先嘗試公報公告頁面（效果最好）
    raw = _http_get(COUNCIL_ANNOUNCE_URL)
    if raw:
        html = _decode(raw)
        # 解析表格行：「嘉義市議會第11屆第6次定期會」格式
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.DOTALL)
        for row in rows:
            text = re.sub(r"<[^>]+>", " ", row)
            text = re.sub(r"\s+", " ", text).strip()
            # 找「嘉義市議會第XX屆第X次」格式
            m = re.search(r"(嘉義市議會第\d+屆第\d+次[^，\s<]{2,20})", text)
            date_m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", text)
            if m and date_m:
                y, mo, d = date_m.groups()
                meetings.append({
                    "date": f"{y}/{mo}/{d}",
                    "type": m.group(1).strip(),
                    "source": "council_announce",
                })

    if meetings:
        print(f"  [council] 從公報頁面找到 {len(meetings)} 筆會議記錄")

    # 2. 補充：嘗試行程頁面
    raw2 = _http_get(COUNCIL_SCHEDULE_URL)
    if raw2:
        html2 = _decode(raw2)
        rows2 = re.findall(r"<tr[^>]*>(.*?)</tr>", html2, re.DOTALL)
        for row in rows2:
            text = re.sub(r"<[^>]+>", " ", row)
            text = re.sub(r"\s+", " ", text).strip()
            date_m = re.search(r"(\d{4})\.(\d{2})\.(\d{2})", text)
            if date_m:
                y, mo, d = date_m.groups()
                title_parts = re.findall(r"[一-鿿]{4,}", text)
                if title_parts:
                    meetings.append({
                        "date": f"{y}/{mo}/{d}",
                        "type": title_parts[0][:20],
                        "source": "council_schedule",
                    })

    # 3. 若仍空，嘗試首頁
    if not meetings:
        raw3 = _http_get(COUNCIL_DEFAULT)
        if raw3:
            html3 = _decode(raw3)
            m_dates = re.findall(r"(\d{3,4})[年/\-](\d{1,2})[月/\-](\d{1,2})[日]?\s*[，,]?\s*([^<\n]{5,40}(?:會|議|定期|臨時))", html3)
            for y, mo, d, title in m_dates[:20]:
                meetings.append({
                    "date": f"{y}/{mo}/{d}",
                    "type": title.strip()[:30],
                    "source": "scraped",
                })

    print(f"  [council] 共找到 {len(meetings)} 筆會議記錄")
    return meetings


def fetch_councilor_list() -> list[dict]:
    """回傳現任嘉義市議員名單（第九屆）"""
    print("  [council] 使用已知議員名單（第九屆）...")
    raw = _http_get(COUNCIL_DEFAULT)
    if not raw:
        return [{"name": name, "party": "", "source": "static"} for name in COUNCILORS]

    html = _decode(raw)
    councilors = []
    seen = set()

    # 嘗試從網頁中找議員名字
    name_pattern = re.compile(r"([一-鿿]{2,4})(?:議員|市議員)")
    for match in name_pattern.finditer(html):
        name = match.group(1)
        if name not in seen and len(name) >= 2:
            seen.add(name)
            councilors.append({"name": name, "source": "scraped"})

    # 確保已知議員都在清單中
    for name in COUNCILORS:
        if name not in seen:
            seen.add(name)
            councilors.append({"name": name, "source": "static"})

    print(f"  [council] 共 {len(councilors)} 位議員")
    return councilors


def fetch_question_records(year_start: int = 2013, year_end: int = 2026) -> list[dict]:
    """從議會首頁搜尋質詢或施政相關關鍵詞"""
    print(f"  [council] 掃描質詢記錄...")
    raw = _http_get(COUNCIL_DEFAULT)
    if not raw:
        return []

    html = _decode(raw)
    records = []

    # 在 HTML 中找議員名字配合質詢關鍵詞
    keywords = ["質詢", "市政", "建設", "工程", "道路", "環境", "提案", "陳情"]
    for name in COUNCILORS:
        if name in html:
            idx = html.find(name)
            snippet = html[max(0, idx - 80): idx + 300]
            snippet_clean = re.sub(r"<[^>]+>", " ", snippet)
            snippet_clean = re.sub(r"\s+", " ", snippet_clean).strip()
            if any(kw in snippet_clean for kw in keywords):
                records.append({
                    "councilor": name,
                    "year": datetime.now().year,
                    "snippet": snippet_clean[:150],
                    "source_url": COUNCIL_DEFAULT,
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
