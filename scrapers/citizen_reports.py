"""市民自主通報整合 — Google Sheet 讀取 (report.html 表單來源)"""
import json
import os
from datetime import datetime

try:
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


SHEET_NAME = "西區市政通報"
WORKSHEET_NAME = "通報記錄"

CATEGORY_KEYWORDS = {
    "道路工程": ["道路", "路面", "坑洞", "柏油", "施工", "工程"],
    "停車亂象": ["停車", "違停", "佔用", "騎樓", "人行道"],
    "路燈照明": ["路燈", "照明", "燈", "黑暗", "光線"],
    "水溝排水": ["水溝", "排水", "淹水", "溝渠", "雨水"],
    "環境衛生": ["垃圾", "清潔", "廢棄物", "蚊蟲", "鼠患", "臭味"],
    "噪音管制": ["噪音", "聲音", "吵鬧", "擾民"],
    "綠化景觀": ["樹木", "草皮", "綠化", "公園"],
    "其他": [],
}


def classify_report(description: str) -> str:
    """根據描述文字自動分類市政議題"""
    for cat, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in description for kw in keywords):
            return cat
    return "其他"


def fetch_from_sheet() -> list[dict]:
    """從 Google Sheet 讀取市民通報（需要 GCP_SERVICE_ACCOUNT_KEY 環境變數）"""
    if not GSPREAD_AVAILABLE:
        print("  [citizen] gspread 未安裝，跳過 Google Sheet")
        return []

    secret = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not secret or not sheet_id:
        print("  [citizen] 缺少 GCP 憑證環境變數，跳過 Google Sheet")
        return []

    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(secret), scope)
        client = gspread.authorize(creds)
        worksheet = client.open_by_key(sheet_id).worksheet(WORKSHEET_NAME)
        records = worksheet.get_all_records()

        result = []
        for i, r in enumerate(records):
            desc = str(r.get("現場狀況描述", "") or r.get("原始描述", ""))
            result.append({
                "id": f"CR-{1000 + i}",
                "date": str(r.get("時間戳記", "") or r.get("通報日期", "")),
                "location": str(r.get("發生路段地點", "") or r.get("發生地點", "")),
                "category": str(r.get("市政議題分類", "") or r.get("議題分類", ""))
                           or classify_report(desc),
                "description": desc,
                "status": str(r.get("處理狀態", "已收件")),
                "source": "citizen_report",
            })
        print(f"  [citizen] 從 Google Sheet 讀取 {len(result)} 筆通報")
        return result
    except Exception as e:
        print(f"  [citizen] Google Sheet 讀取失敗: {e}")
        return []


def build_stats(records: list[dict]) -> dict:
    """建立通報統計摘要"""
    category_counts: dict[str, int] = {}
    road_counts: dict[str, int] = {}

    for r in records:
        cat = r.get("category", "其他")
        category_counts[cat] = category_counts.get(cat, 0) + 1

        loc = r.get("location", "")
        if loc:
            road_counts[loc] = road_counts.get(loc, 0) + 1

    top_roads = sorted(road_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    return {
        "total": len(records),
        "category_counts": category_counts,
        "top_roads": [{"road": r, "count": c} for r, c in top_roads],
        "updated_at": datetime.now().isoformat(),
    }
