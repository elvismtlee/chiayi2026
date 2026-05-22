"""
嘉義市政府開放資料平台爬蟲（真實 API 版）
使用反向工程的 Oracle JET 內部 JSON API：
  dataset/dataset_json    — 搜尋資料集
  dataset/resource_json   — 取得資料集的資源清單
  api/getResource/download — 下載 CSV/XML 資源

已知資料集（自 data.chiayi.gov.tw 確認）：
  - 道路交通事故統計（主計處）：2014 年起月度統計
  - 管線挖掘資訊（工務處）：即時路段施工
  - 環境及交通噪音監測（環境保護局）：多年噪音數據
  - 路燈清冊（工務處）：全市路燈 GPS 清單
  - 建設處承辦工程統計（建設處）：工程案件統計
  - 嘉義市陳情管道（企劃處）：各機關陳情管道
"""
import csv
import io
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

TIMEOUT = 25
HEADERS = {"User-Agent": "Mozilla/5.0 (chiayi2026-bot/1.0)"}
CHIAYI_BASE = "https://data.chiayi.gov.tw/opendata/"

# ── 已知資料集（OID + RID 直接寫死，避免每次搜尋）─────────────────────────
DATASETS = {
    "traffic_accident": {
        "oid": "1829dd8c-33cc-45bb-a3f1-89d3b2e2f453",
        "rid": "cc1bdee9-a253-4c7d-b6c4-4858328f95aa",
        "title": "嘉義市道路交通事故統計",
        "category": "道路交通",
    },
    "pipeline_dig": {
        "oid": "2cf1aa4f-3cdd-46a0-be84-b6f161cd892d",
        "rid": "ca4c025d-1856-4200-81b7-a401aa653da3",
        "title": "嘉義市管線挖掘資訊",
        "category": "道路工程",
        "fmt": "xml",
    },
    "streetlight": {
        "oid": "672349d8-cb63-4e26-b077-d4c35d6eef23",
        "rid": "665d755b-f35e-4c0d-9b86-05ee4a6f5bfe",
        "title": "嘉義市路燈清冊",
        "category": "路燈照明",
    },
    "noise_monitor": {
        "oid": "0f0f0e47-6ebe-41b5-9363-fcb787c3e01c",
        "rid": "93e40c00-b975-4d1b-965a-dcae2d278557",
        "title": "嘉義市環境及交通噪音監測",
        "category": "噪音管制",
    },
    "complaint_channels": {
        "oid": "d03a1418-f3e1-4e58-bbc1-c6a7361d470a",
        "rid": "ca826f03-9fcf-43b5-b781-8cdf3a3b7772",
        "title": "嘉義市政府暨所屬機關陳情管道",
        "category": "市政服務",
    },
}

# ── 搜尋關鍵字（用於動態發現新資料集）──────────────────────────────────────
SEARCH_KEYWORDS = ["陳情", "道路", "交通", "工程", "噪音", "路燈", "環境"]


# ── 底層 HTTP ────────────────────────────────────────────────────────────────

def _get(url: str, timeout: int = TIMEOUT) -> requests.Response | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  [opendata] GET 失敗 {url[:60]}: {e}")
        return None


def _decode_csv(content: bytes) -> str:
    """嘗試多種編碼解碼 CSV"""
    for enc in ("utf-8-sig", "utf-8", "big5", "cp950"):
        try:
            return content.decode(enc)
        except Exception:
            pass
    return content.decode("utf-8", errors="replace")


# ── Chiayi 開放資料 API ───────────────────────────────────────────────────────

def search_datasets(keyword: str) -> list[dict]:
    """使用真實 dataset/dataset_json API 搜尋資料集"""
    import urllib.parse
    url = CHIAYI_BASE + "dataset/dataset_json?qAll=" + urllib.parse.quote(keyword)
    r = _get(url)
    if not r:
        return []
    try:
        data = r.json()
        seen = set()
        results = []
        for d in data:
            if d.get("oid") and d["oid"] not in seen:
                seen.add(d["oid"])
                results.append(d)
        return results
    except Exception as e:
        print(f"  [opendata] JSON 解析失敗: {e}")
        return []


def get_resource_id(oid: str) -> str | None:
    """取得資料集的第一個資源 rid"""
    url = CHIAYI_BASE + f"dataset/resource_json?oid={oid}"
    r = _get(url)
    if not r:
        return None
    try:
        data = r.json()
        return data[0]["rid"] if data else None
    except Exception:
        return None


def download_resource(oid: str, rid: str) -> bytes | None:
    """下載資源檔案"""
    url = CHIAYI_BASE + f"api/getResource/download?oid={oid}&rid={rid}"
    r = _get(url, timeout=45)
    return r.content if r else None


# ── 資料處理 ─────────────────────────────────────────────────────────────────

def _parse_traffic_accident_csv(content: bytes) -> list[dict]:
    """解析道路交通事故統計 CSV
    欄位：統計_年月, 縣市, A1+A2類道路交通事故件數, 道路交通事故死亡人數, 道路交通事故受傷人數
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        ym = (list(row.values())[0] if row else "").strip()  # 統計_年月 key encoding varies
        # 找年月欄位（因編碼問題 key 可能不同）
        keys = list(row.keys())
        if not keys:
            continue
        ym_val = row.get(keys[0], "").strip()
        city = row.get(keys[1], "").strip() if len(keys) > 1 else ""
        count = row.get(keys[2], "0").strip() if len(keys) > 2 else "0"
        dead  = row.get(keys[3], "0").strip() if len(keys) > 3 else "0"
        injured = row.get(keys[4], "0").strip() if len(keys) > 4 else "0"

        if len(ym_val) == 6 and ym_val.isdigit():
            year = ym_val[:4]
            month = ym_val[4:]
            records.append({
                "date": f"{year}/{month}",
                "year": year,
                "month": month,
                "category": "道路交通",
                "location": "嘉義市",
                "count": int(count) if count.isdigit() else 0,
                "deaths": int(dead) if dead.isdigit() else 0,
                "injuries": int(injured) if injured.isdigit() else 0,
                "source": "data.chiayi.gov.tw",
                "title": "道路交通事故",
            })
    return records


def _parse_pipeline_xml(content: bytes) -> list[dict]:
    """解析管線挖掘資訊 XML，回傳目前施工路段列表"""
    try:
        root = ET.fromstring(content)
    except Exception as e:
        print(f"  [opendata] XML 解析失敗: {e}")
        return []

    records = []
    for case in root.findall(".//CASE_DETAIL"):
        def txt(tag):
            el = case.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        location = txt("LOCATION")
        const_name = txt("CONST_NAME")
        town = txt("TOWN_NAME")
        start = txt("ABE_DA")
        end = txt("AEN_DA")
        status = txt("DG_STATUS")
        un_na = txt("UN_NA")   # 申請單位

        # 判斷狀態
        status_txt = {"0": "申請中", "1": "施工中", "2": "已完工"}.get(status, "未知")

        records.append({
            "date": start[:7].replace("-", "/") if start else "",
            "year": start[:4] if start else "",
            "category": "道路工程",
            "location": f"{town}{location}" if town else location,
            "title": const_name or "管線挖掘",
            "end_date": end,
            "status": status_txt,
            "applicant": un_na,
            "source": "data.chiayi.gov.tw",
            "count": 1,
        })
    print(f"  [opendata] 管線挖掘：{len(records)} 筆施工路段")
    return records


def _parse_streetlight_csv(content: bytes) -> list[dict]:
    """解析路燈清冊 CSV，統計各地區路燈數量"""
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    area_counts: dict[str, int] = {}
    total = 0

    for row in reader:
        keys = list(row.keys())
        # 裝設地點通常是第二欄
        loc = row.get(keys[1], "").strip() if len(keys) > 1 else ""
        if loc:
            # 取地址前6字元當區域
            area = loc[:6] if len(loc) >= 6 else loc
            area_counts[area] = area_counts.get(area, 0) + 1
            total += 1

    print(f"  [opendata] 路燈清冊：共 {total} 盞路燈")
    return [{"category": "路燈照明", "location": k, "count": v, "source": "data.chiayi.gov.tw"}
            for k, v in sorted(area_counts.items(), key=lambda x: -x[1])[:20]]


def _parse_complaint_channels_csv(content: bytes) -> list[dict]:
    """解析陳情管道 CSV，回傳各機關陳情資訊"""
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        keys = list(row.keys())
        name = row.get(keys[0], "").strip() if keys else ""
        url  = row.get(keys[1], "").strip() if len(keys) > 1 else ""
        phone = row.get(keys[2], "").strip() if len(keys) > 2 else ""
        if name:
            records.append({
                "category": "市政服務",
                "title": name,
                "url": url,
                "phone": phone,
                "source": "data.chiayi.gov.tw",
            })
    print(f"  [opendata] 陳情管道：{len(records)} 個機關")
    return records


# ── 對外介面 ─────────────────────────────────────────────────────────────────

def fetch_opendata_datasets() -> list[dict]:
    """回傳已知資料集清單（供 scraper.py 使用）"""
    print("  [opendata] 使用已知資料集清單（OID 直接寫死）")
    result = []
    for key, ds in DATASETS.items():
        result.append({
            "title": ds["title"],
            "oid": ds["oid"],
            "rid": ds.get("rid", ""),
            "category": ds["category"],
            "format": ds.get("fmt", "csv").upper(),
            "source": "data.chiayi.gov.tw",
            "resources": [{"format": ds.get("fmt", "CSV").upper(),
                           "url": CHIAYI_BASE + f"api/getResource/download?oid={ds['oid']}&rid={ds.get('rid','')}"}],
        })
    print(f"  [opendata] {len(result)} 個已知資料集")
    return result


def fetch_opendata_records(resource_url: str) -> list[dict]:
    """下載並解析資源 URL（供 scraper.py 舊版介面使用）"""
    if not resource_url:
        return []
    r = _get(resource_url, timeout=45)
    if not r:
        return []

    content = r.content
    if "xml" in resource_url.lower() or content[:5] == b"<?xml":
        return _parse_pipeline_xml(content)

    # CSV
    text = _decode_csv(content)
    try:
        reader = csv.DictReader(io.StringIO(text))
        return [dict(row) for row in reader]
    except Exception:
        return []


def fetch_all_opendata_records() -> list[dict]:
    """主入口：下載所有已知資料集，回傳合併記錄列表"""
    all_records: list[dict] = []

    for key, ds in DATASETS.items():
        oid = ds["oid"]
        rid = ds["rid"]
        title = ds["title"]
        fmt = ds.get("fmt", "csv")

        print(f"  [opendata] 下載 {title} ...")
        content = download_resource(oid, rid)
        if not content:
            print(f"  [opendata] {title} 下載失敗，跳過")
            time.sleep(1)
            continue

        if fmt == "xml":
            records = _parse_pipeline_xml(content)
        elif key == "traffic_accident":
            records = _parse_traffic_accident_csv(content)
        elif key == "streetlight":
            records = _parse_streetlight_csv(content)
        elif key == "complaint_channels":
            records = _parse_complaint_channels_csv(content)
        else:
            # 通用 CSV 解析
            text = _decode_csv(content)
            try:
                reader = csv.DictReader(io.StringIO(text))
                records = [dict(row) for row in reader]
            except Exception as e:
                print(f"  [opendata] {title} CSV 解析失敗: {e}")
                records = []

        print(f"  [opendata] {title}: {len(records)} 筆")
        all_records.extend(records)
        time.sleep(0.5)

    return all_records


def build_complaint_stats(records: list[dict]) -> dict:
    """從原始記錄建立統計摘要，供儀表板圖表使用"""
    category_counts: dict[str, int] = {}
    road_counts: dict[str, int] = {}
    year_counts: dict[str, int] = {}

    for r in records:
        cat = r.get("category") or r.get("議題分類") or r.get("類別") or "其他"
        category_counts[cat] = category_counts.get(cat, 0) + r.get("count", 1)

        loc = r.get("location") or r.get("發生路段") or r.get("地點") or ""
        if loc and len(loc) > 2:
            key = loc[:8]
            road_counts[key] = road_counts.get(key, 0) + r.get("count", 1)

        year = r.get("year") or ""
        if not year:
            date_str = r.get("date") or r.get("通報日期") or ""
            year = date_str[:4] if len(date_str) >= 4 else ""
        if year and year.isdigit() and 2010 <= int(year) <= 2030:
            year_counts[year] = year_counts.get(year, 0) + r.get("count", 1)

    top_roads = sorted(road_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total": sum(r.get("count", 1) for r in records),
        "category_counts": category_counts,
        "top_roads": [{"road": r, "count": c} for r, c in top_roads],
        "top_categories": [{"category": c, "count": n} for c, n in top_cats],
        "year_counts": year_counts,
        "updated_at": datetime.now().isoformat(),
        "source": "data.chiayi.gov.tw",
    }
