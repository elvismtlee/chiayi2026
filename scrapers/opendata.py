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
        "category": "交通停車",
    },
    "pipeline_dig": {
        "oid": "2cf1aa4f-3cdd-46a0-be84-b6f161cd892d",
        "rid": "ca4c025d-1856-4200-81b7-a401aa653da3",
        "title": "嘉義市管線挖掘資訊",
        "category": "道路路平",
        "fmt": "xml",
    },
    "streetlight": {
        "oid": "672349d8-cb63-4e26-b077-d4c35d6eef23",
        "rid": "665d755b-f35e-4c0d-9b86-05ee4a6f5bfe",
        "title": "嘉義市路燈清冊",
        "category": "公共安全",
    },
    "noise_monitor": {
        "oid": "0f0f0e47-6ebe-41b5-9363-fcb787c3e01c",
        "rid": "93e40c00-b975-4d1b-965a-dcae2d278557",
        "title": "嘉義市環境及交通噪音監測",
        "category": "環境衛生",
    },
    "complaint_channels": {
        "oid": "d03a1418-f3e1-4e58-bbc1-c6a7361d470a",
        "rid": "ca826f03-9fcf-43b5-b781-8cdf3a3b7772",
        "title": "嘉義市政府暨所屬機關陳情管道",
        "category": "行政服務",
    },
    # ── 新增：西區選民資料 + 基礎建設 ─────────────────────────────────────
    "west_population_2026": {
        "oid": "0837b8c6-39ea-4bac-955d-3b661040fdf9",
        "rid": "9ab9cdb9-c83d-4d85-855d-ffeee023ef3b",
        "title": "嘉義市西區115年各里人口統計",
        "category": "西區人口",
    },
    "west_population_2025": {
        "oid": "65172716-1265-4744-87bb-4c859241ab7a",
        "rid": "8df6956a-5f1b-490d-940c-114db73d166c",
        "title": "嘉義市西區114年各里人口統計",
        "category": "西區人口",
    },
    "bridge_info": {
        "oid": "ab402b9d-5cc8-476c-bc16-8b21d77a9695",
        "rid": "b4d1ef31-bc22-4b97-ba6d-9c0773d430df",
        "title": "嘉義市政府橋梁資訊",
        "category": "道路路平",
    },
    "drowning_cases": {
        "oid": "e36659bb-b7aa-4a53-8c08-b2c97f580ae7",
        "rid": "e7c9aa48-3c64-44a5-8930-27a850eab3e8",
        "title": "嘉義市歷年溺水案件",
        "category": "公共安全",
    },
    "public_parking": {
        "oid": "d206db33-3ae7-489e-b709-5555222fb767",
        "rid": "4e0c8e01-9844-4da6-991b-a3382b51b71b",
        "title": "嘉義市公有路外停車場",
        "category": "交通停車",
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
            death_n = int(dead) if dead.isdigit() else 0
            injury_n = int(injured) if injured.isdigit() else 0
            # 細分：有死亡 → 公共安全；純傷亡 → 交通停車
            sub_cat = "公共安全" if death_n > 0 else "交通停車"
            records.append({
                "date": f"{year}/{month}",
                "year": year,
                "month": month,
                "category": sub_cat,
                "subcategory": "交通事故",
                "location": "嘉義市",
                "count": int(count) if count.isdigit() else 0,
                "deaths": death_n,
                "injuries": injury_n,
                "source": "data.chiayi.gov.tw",
                "title": f"道路交通事故（{year}/{month}）",
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

        # 申請單位細分 subcategory
        sub = "道路施工"
        if un_na:
            if "電力" in un_na or "台電" in un_na:
                sub = "電力管線"
            elif "電信" in un_na or "中華" in un_na or "台灣大" in un_na or "遠傳" in un_na:
                sub = "電信管線"
            elif "自來水" in un_na:
                sub = "自來水管線"
            elif "瓦斯" in un_na or "天然氣" in un_na:
                sub = "瓦斯管線"
            elif "市政府" in un_na or "嘉義市" in un_na:
                sub = "市府工程"

        records.append({
            "date": start[:7].replace("-", "/") if start else "",
            "year": start[:4] if start else "",
            "category": "道路路平",
            "subcategory": sub,
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
    return [{"category": "公共安全", "subcategory": "路燈照明",
             "location": k, "count": v, "title": f"{k}路燈",
             "source": "data.chiayi.gov.tw"}
            for k, v in sorted(area_counts.items(), key=lambda x: -x[1])[:20]]


def _parse_noise_monitor_csv(content: bytes) -> list[dict]:
    """解析環境及交通噪音監測 CSV
    欄位：監測站名, 監測站編號, 緊鄰道路寬度, 管制區, 年(民國), 月, 日, 0-1時...23-24時(dB)
    聚合為月平均，避免逐日資料量過大（每站×每日 → 每站×每月）
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    # 聚合：(station, ce_year, month) → list of avg_db
    monthly: dict[tuple, list] = {}
    station_zone: dict[str, str] = {}
    hour_cols = [f"{h}-{h+1}時" for h in range(24)]
    for row in reader:
        station = row.get("監測站名", "").strip()
        roc_year = row.get("年", "").strip()
        month = row.get("月", "").strip()
        day = row.get("日", "").strip()
        zone = row.get("管制區", "").strip()
        if not station or not roc_year:
            continue
        # 民國年轉西元
        try:
            ce_year = str(int(roc_year) + 1911)
        except Exception:
            ce_year = roc_year
        station_zone[station] = zone
        # 計算當日平均噪音分貝
        vals = []
        for col in hour_cols:
            v = row.get(col, "").strip()
            try:
                vals.append(float(v))
            except Exception:
                pass
        avg_db = round(sum(vals) / len(vals), 1) if vals else 0
        key = (station, ce_year, month.zfill(2) if month else "00")
        if key not in monthly:
            monthly[key] = []
        if avg_db > 0:
            monthly[key].append(avg_db)

    # 轉換為月平均記錄（每站每月一筆）
    records = []
    for (station, ce_year, month), db_list in sorted(monthly.items()):
        avg_db = round(sum(db_list) / len(db_list), 1) if db_list else 0
        zone = station_zone.get(station, "")
        records.append({
            "date": f"{ce_year}/{month}",
            "year": ce_year,
            "category": "環境衛生",
            "subcategory": "噪音管制",
            "location": station,
            "title": f"{station}噪音監測",
            "description": f"管制區{zone}，月均{avg_db}dB",
            "count": 1,
            "avg_db": avg_db,
            "source": "data.chiayi.gov.tw",
        })
    print(f"  [opendata] 噪音監測：{len(records)} 筆（月平均）")
    return records


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
                "category": "行政服務",
                "subcategory": "陳情管道",
                "title": name,
                "url": url,
                "phone": phone,
                "source": "data.chiayi.gov.tw",
            })
    print(f"  [opendata] 陳情管道：{len(records)} 個機關")
    return records


def _parse_population_csv(content: bytes, year: str = "") -> list[dict]:
    """解析西區各里人口統計 CSV
    欄位：區域別, 鄰數, 戶數, 男, 女, 合計
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        keys = list(row.keys())
        area = row.get(keys[0], "").strip() if keys else ""
        neighbors = row.get(keys[1], "0").strip() if len(keys) > 1 else "0"
        households = row.get(keys[2], "0").strip() if len(keys) > 2 else "0"
        male = row.get(keys[3], "0").strip() if len(keys) > 3 else "0"
        female = row.get(keys[4], "0").strip() if len(keys) > 4 else "0"
        total = row.get(keys[5], "0").strip() if len(keys) > 5 else "0"

        if area and area not in ("合計", "小計", "總計", "區域別"):
            try:
                total_int = int(total.replace(",", ""))
            except Exception:
                total_int = 0
            records.append({
                "date": f"{year}/04" if year else "",
                "year": year,
                "category": "西區人口",
                "location": f"嘉義市西區{area}",
                "title": f"{area}人口",
                "count": total_int,
                "male": int(male.replace(",", "")) if male.replace(",", "").isdigit() else 0,
                "female": int(female.replace(",", "")) if female.replace(",", "").isdigit() else 0,
                "households": int(households.replace(",", "")) if households.replace(",", "").isdigit() else 0,
                "neighbors": int(neighbors.replace(",", "")) if neighbors.replace(",", "").isdigit() else 0,
                "source": "data.chiayi.gov.tw",
            })
    return records


def _parse_bridge_csv(content: bytes) -> list[dict]:
    """解析橋梁資訊 CSV
    欄位：橋梁名稱, 英譯橋名, 管理機關, 道路等級, 橋梁總長
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        keys = list(row.keys())
        name = row.get(keys[0], "").strip() if keys else ""
        agency = row.get(keys[2], "").strip() if len(keys) > 2 else ""
        road_class = row.get(keys[3], "").strip() if len(keys) > 3 else ""
        length = row.get(keys[4], "0").strip() if len(keys) > 4 else "0"
        if name:
            try:
                length_f = float(length) if length else 0
            except Exception:
                length_f = 0
            records.append({
                "category": "道路路平",
                "subcategory": "橋梁設施",
                "location": "嘉義市",
                "title": name,
                "description": f"{road_class}，管理：{agency}",
                "count": 1,
                "length_m": length_f,
                "source": "data.chiayi.gov.tw",
            })
    print(f"  [opendata] 橋梁資訊：{len(records)} 座橋梁")
    return records


def _parse_drowning_csv(content: bytes) -> list[dict]:
    """解析歷年溺水案件 CSV
    欄位：編號, 縣市別, 年, 月, 日, 時, 分, 溺水地點, 水域種類, 溺水原因, 溺水結果, 性別, 年齡, ...
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        keys = list(row.keys())
        year = row.get(keys[2], "").strip() if len(keys) > 2 else ""
        month = row.get(keys[3], "").strip() if len(keys) > 3 else ""
        location = row.get(keys[7], "").strip() if len(keys) > 7 else ""
        water_type = row.get(keys[8], "").strip() if len(keys) > 8 else ""
        cause = row.get(keys[9], "").strip() if len(keys) > 9 else ""
        result = row.get(keys[10], "").strip() if len(keys) > 10 else ""

        if year and year.isdigit():
            records.append({
                "date": f"{year}/{month.zfill(2)}" if month else year,
                "year": year,
                "category": "公共安全",
                "subcategory": "水域安全",
                "location": location[:20] if location else "嘉義市",
                "title": f"溺水事故（{water_type}）",
                "description": f"原因：{cause}，結果：{result}",
                "count": 1,
                "source": "data.chiayi.gov.tw",
            })
    print(f"  [opendata] 歷年溺水案件：{len(records)} 件")
    return records


def _parse_parking_csv(content: bytes) -> list[dict]:
    """解析公有路外停車場 CSV
    欄位：項次, 停車場名稱, 收費方式, 月租費用, 型式, 大型車, 小型車, 身障, 婦幼, 機車, ...
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    records = []
    for row in reader:
        keys = list(row.keys())
        name = row.get(keys[1], "").strip() if len(keys) > 1 else ""
        parking_type = row.get(keys[4], "").strip() if len(keys) > 4 else ""
        small_car = row.get(keys[6], "0").strip() if len(keys) > 6 else "0"
        address = row.get("地址", row.get(keys[-2] if len(keys) > 2 else keys[0], "")).strip()
        if name:
            try:
                capacity = int(small_car) if small_car.isdigit() else 0
            except Exception:
                capacity = 0
            # 清理多行文字中的控制字符
            clean_addr = address.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
            records.append({
                "category": "交通停車",
                "subcategory": "公有停車場",
                "location": clean_addr[:20] if clean_addr else "嘉義市",
                "title": name.replace("\r\n", " ").replace("\r", " ").strip(),
                "description": f"{parking_type}停車場，小型車 {capacity} 格",
                "count": capacity or 1,
                "source": "data.chiayi.gov.tw",
            })
    print(f"  [opendata] 公有停車場：{len(records)} 處")
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


def fetch_west_district_population() -> list[dict]:
    """專門抓取西區各里人口資料（最新年度），回傳里別人口清單"""
    print("  [opendata] 抓取西區各里人口統計...")
    ds = DATASETS["west_population_2026"]
    content = download_resource(ds["oid"], ds["rid"])
    if not content:
        # 嘗試2025年資料
        ds = DATASETS["west_population_2025"]
        content = download_resource(ds["oid"], ds["rid"])
    if not content:
        return []
    records = _parse_population_csv(content, year="2026")
    # 過濾掉合計列，只保留里別
    records = [r for r in records if "里" in r.get("title", "")]
    print(f"  [opendata] 西區共 {len(records)} 個里")
    return records


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


def _cache_path(key: str):
    """各資料集獨立快取檔案路徑"""
    from pathlib import Path
    cache_dir = Path(__file__).parent.parent / "data" / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / f"opendata_{key}.json"


def _load_cache(key: str) -> list[dict]:
    p = _cache_path(key)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_cache(key: str, records: list[dict]):
    p = _cache_path(key)
    p.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def fetch_all_opendata_records() -> list[dict]:
    """主入口：下載所有已知資料集，失敗時自動使用上次快取，回傳合併記錄列表"""
    all_records: list[dict] = []
    dataset_url = "https://data.chiayi.gov.tw/opendata/"

    for key, ds in DATASETS.items():
        oid = ds["oid"]
        rid = ds["rid"]
        title = ds["title"]
        fmt = ds.get("fmt", "csv")

        print(f"  [opendata] 下載 {title} ...")
        content = download_resource(oid, rid)

        if not content:
            # ── 下載失敗：使用快取 ────────────────────────────
            cached = _load_cache(key)
            if cached:
                print(f"  [opendata] {title} 下載失敗，使用快取（{len(cached)} 筆）")
                all_records.extend(cached)
            else:
                print(f"  [opendata] {title} 下載失敗，無快取，跳過")
            time.sleep(1)
            continue

        # ── 解析 ────────────────────────────────────────────
        if fmt == "xml":
            records = _parse_pipeline_xml(content)
        elif key == "traffic_accident":
            records = _parse_traffic_accident_csv(content)
        elif key == "streetlight":
            records = _parse_streetlight_csv(content)
        elif key == "noise_monitor":
            records = _parse_noise_monitor_csv(content)
        elif key == "complaint_channels":
            records = _parse_complaint_channels_csv(content)
        elif key == "west_population_2026":
            records = _parse_population_csv(content, year="2026")
        elif key == "west_population_2025":
            records = _parse_population_csv(content, year="2025")
        elif key == "bridge_info":
            records = _parse_bridge_csv(content)
        elif key == "drowning_cases":
            records = _parse_drowning_csv(content)
        elif key == "public_parking":
            records = _parse_parking_csv(content)
        else:
            text = _decode_csv(content)
            try:
                reader = csv.DictReader(io.StringIO(text))
                records = [dict(row) for row in reader]
            except Exception as e:
                print(f"  [opendata] {title} CSV 解析失敗: {e}")
                records = []

        if not records:
            # 解析失敗也回退快取
            cached = _load_cache(key)
            if cached:
                print(f"  [opendata] {title} 解析為空，使用快取（{len(cached)} 筆）")
                all_records.extend(cached)
            time.sleep(0.5)
            continue

        # 注入 source_url
        for rec in records:
            if not rec.get("source_url"):
                rec["source_url"] = dataset_url

        # ── 下載成功：更新快取 ────────────────────────────────
        _save_cache(key, records)
        print(f"  [opendata] {title}: {len(records)} 筆 ✓（快取已更新）")
        all_records.extend(records)
        time.sleep(0.5)

    return all_records


def build_complaint_stats(records: list[dict]) -> dict:
    """從原始記錄建立統計摘要，供儀表板圖表使用。
    分類統計使用 count 欄位加總（反映實際件數/數量），
    例如交通事故每月有件數欄位，加總後顯示12年真實事故總數。
    """
    category_counts: dict[str, int] = {}
    subcategory_counts: dict[str, dict] = {}  # {category: {sub: count}}
    road_counts: dict[str, int] = {}
    year_counts: dict[str, int] = {}

    for r in records:
        cat = r.get("category") or r.get("議題分類") or r.get("類別") or "其他"
        # 使用 count 欄位加總（交通事故為月度件數，路燈為該區燈數，橋梁/管線為1）
        n = r.get("count", 1)
        if not isinstance(n, (int, float)) or n <= 0:
            n = 1
        category_counts[cat] = category_counts.get(cat, 0) + int(n)

        # 子類別統計（同樣用 count 加總）
        sub = r.get("subcategory", "")
        if sub:
            if cat not in subcategory_counts:
                subcategory_counts[cat] = {}
            subcategory_counts[cat][sub] = subcategory_counts[cat].get(sub, 0) + int(n)

        loc = r.get("location") or r.get("發生路段") or r.get("地點") or ""
        if loc and len(loc) > 2 and loc not in ("嘉義市",):
            key = loc[:10]
            road_counts[key] = road_counts.get(key, 0) + 1

        year = r.get("year") or ""
        if not year:
            date_str = r.get("date") or r.get("通報日期") or ""
            year = date_str[:4] if len(date_str) >= 4 else ""
        if year and year.isdigit() and 2010 <= int(year) <= 2030:
            # 年度用 count 加總（反映實際事故量趨勢）
            year_counts[year] = year_counts.get(year, 0) + r.get("count", 1)

    top_roads = sorted(road_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_cats = sorted(category_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "total": sum(r.get("count", 1) for r in records),
        "record_count": len(records),
        "category_counts": category_counts,
        "subcategory_counts": subcategory_counts,
        "top_roads": [{"road": r, "count": c} for r, c in top_roads],
        "top_categories": [{"category": c, "count": n} for c, n in top_cats],
        "year_counts": year_counts,
        "updated_at": datetime.now().isoformat(),
        "source": "data.chiayi.gov.tw",
    }
