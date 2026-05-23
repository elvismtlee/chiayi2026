"""
城市綜合數據爬蟲 — 嘉義市多元資料來源整合
Sources:
  - 環境部 AQI 歷史統計 (data.moenv.gov.tw)
  - 中央氣象局地震資訊 RSS (www.cwa.gov.tw)
  - 中央氣象局氣象觀測 (opendata.cwa.gov.tw)
  - 疾管署 登革熱統計 (data.cdc.gov.tw)
  - 政府電子採購網 嘉義市採購 (web.pcc.gov.tw)
  - 嘉義市政府 RSS 公告 (www.chiayi.gov.tw)
  - 交通部公路局 公車路線 (oba.motc.gov.tw)
  - 內政部 人口統計 (data.moi.gov.tw)
  - 消防署 嘉義火災救護統計 (data.nfa.gov.tw)
"""
import json
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

try:
    import requests as _req
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

TIMEOUT = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (chiayi2026-dashboard/1.0; +https://elvismtlee.github.io/chiayi2026/)"
}


def _get(url, headers=None, timeout=None):
    """通用 GET，優先用 requests，fallback urllib"""
    h = {**HEADERS, **(headers or {})}
    t = timeout or TIMEOUT
    if _HAS_REQUESTS:
        r = _req.get(url, headers=h, timeout=t)
        r.raise_for_status()
        return r.content
    with urllib.request.urlopen(
        urllib.request.Request(url, headers=h), timeout=t
    ) as resp:
        return resp.read()


def _get_json(url, headers=None, timeout=None):
    return json.loads(_get(url, headers, timeout))


# ── 1. AQI 歷史月均統計（環境部） ───────────────────────────────────────────
def fetch_aqi_history():
    """近 12 個月嘉義市 AQI 月均統計（server-side，存為圖表資料）"""
    # 環境部 AQI 歷史: aqx_p_07 = 月平均 AQI（不帶 filter，Python 篩選）
    url = (
        "https://data.moenv.gov.tw/api/v2/aqx_p_07"
        "?api_key=e8dd42e6-9b8b-43f8-991e-b3dee723a52d"
        "&limit=200&format=json"
    )
    try:
        data = _get_json(url)
        records = data.get("records", [])
        monthly = []
        for r in records:
            site = r.get("sitename", "") or ""
            if "嘉義" not in site:
                continue
            monthly.append({
                "month": r.get("monitordate", "")[:7],
                "aqi": float(r.get("aqi", 0) or 0),
                "pm25": float(r.get("pm25_avg", 0) or 0),
                "station": site,
            })
        monthly.sort(key=lambda x: x["month"], reverse=True)
        print(f"  [aqi_history] 取得 {len(monthly[:12])} 個月歷史 AQI")
        return monthly[:12]
    except Exception as e:
        print(f"  [aqi_history] 失敗: {e}")
        return []


# ── 2. 即時 AQI 讀值（環境部優先，Open-Meteo 備援）────────────────────────
def fetch_aqi_realtime():
    """即時嘉義市 AQI（環境部 API 優先，失敗時用 Open-Meteo）"""

    # 方法 1: 環境部 API（若恢復即可取得精確測站數據）
    MOENV_ENDPOINTS = [
        "https://data.moenv.gov.tw/api/v2/aqx_p_02?api_key=e8dd42e6-9b8b-43f8-991e-b3dee723a52d&limit=100&format=json",
        "https://data.moenv.gov.tw/api/v2/aqx_p_432?api_key=e8dd42e6-9b8b-43f8-991e-b3dee723a52d&limit=100&format=json",
    ]
    for url in MOENV_ENDPOINTS:
        try:
            data = _get_json(url, timeout=12)
            records = data.get("records", [])
            if not records:
                continue
            stations = []
            for r in records:
                county = r.get("county", r.get("County", ""))
                if "嘉義" not in county:
                    continue
                aqi_val = int(r.get("aqi", r.get("AQI", 0)) or 0)
                stations.append({
                    "station": r.get("sitename", r.get("SiteName", "")),
                    "aqi": aqi_val,
                    "pm25": float(r.get("pm2.5", r.get("PM2.5", 0)) or 0),
                    "pm10": float(r.get("pm10", r.get("PM10", 0)) or 0),
                    "o3": float(r.get("o3", r.get("O3", 0)) or 0),
                    "no2": float(r.get("no2", r.get("NO2", 0)) or 0),
                    "status": r.get("status", r.get("Status", "")),
                    "pollutant": r.get("pollutant", r.get("Pollutant", "")),
                    "time": r.get("datacreationdate", r.get("DataCreationDate", "")),
                    "source": "環境部",
                })
            if stations:
                print(f"  [aqi_realtime] 環境部 取得 {len(stations)} 個嘉義測站")
                return sorted(stations, key=lambda x: x["aqi"], reverse=True)
        except Exception as e:
            print(f"  [aqi_realtime] 環境部 {url[:50]}... 失敗: {e}")

    # 方法 2: Open-Meteo 空氣品質 API（免費，無需 key，根據坐標計算）
    try:
        url = (
            "https://air-quality-api.open-meteo.com/v1/air-quality"
            "?latitude=23.48&longitude=120.45"
            "&current=pm10,pm2_5,nitrogen_dioxide,ozone"
            "&timezone=Asia%2FTaipei"
        )
        data = _get_json(url, timeout=12)
        current = data.get("current", {})
        pm25 = float(current.get("pm2_5", 0) or 0)
        pm10 = float(current.get("pm10", 0) or 0)
        no2 = float(current.get("nitrogen_dioxide", 0) or 0)
        o3 = float(current.get("ozone", 0) or 0)
        # 用 PM2.5 換算 AQI（台灣標準：0-35=良好, 36-53=普通, 54-70=不敏感, 71-150=不健康, 151+=非常不健康）
        if pm25 <= 35.4:
            aqi = int(pm25 * 50 / 35.4)
        elif pm25 <= 53.4:
            aqi = 50 + int((pm25 - 35.4) * 50 / 18)
        elif pm25 <= 70.4:
            aqi = 100 + int((pm25 - 53.4) * 50 / 17)
        else:
            aqi = 150 + int((pm25 - 70.4) * 50 / 79.6)
        aqi = min(aqi, 300)
        station = [{
            "station": "嘉義市（Open-Meteo 模型）",
            "aqi": aqi,
            "pm25": round(pm25, 1),
            "pm10": round(pm10, 1),
            "o3": round(o3, 1),
            "no2": round(no2, 1),
            "status": _aqi_status(aqi),
            "pollutant": "PM2.5",
            "time": current.get("time", ""),
            "source": "Open-Meteo",
        }]
        print(f"  [aqi_openmeteo] PM2.5={pm25}μg/m³ → AQI≈{aqi} ({_aqi_status(aqi)})")
        return station
    except Exception as e:
        print(f"  [aqi_openmeteo] 失敗: {e}")

    print("  [aqi_realtime] 所有端點失敗，回傳空清單")
    return []


def _aqi_status(aqi: int) -> str:
    if aqi <= 50: return "良好"
    if aqi <= 100: return "普通"
    if aqi <= 150: return "對敏感族群不健康"
    if aqi <= 200: return "對所有族群不健康"
    if aqi <= 300: return "非常不健康"
    return "危害"


# ── 3. 地震資訊（多來源：USGS + CWA API） ───────────────────────────────────
def fetch_earthquake():
    """最近台灣地震資料（USGS GeoJSON + CWA 開放資料）"""

    # 方法 1: USGS 最近 7 天規模 ≥ 2.5 地震（可靠，有台灣資料）
    usgs_url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.geojson"
    try:
        data = _get_json(usgs_url, timeout=20)
        features = data.get("features", [])
        tw_quakes = []
        for f in features:
            props = f.get("properties", {})
            place = props.get("place", "")
            mag = props.get("mag", 0) or 0
            coords = (f.get("geometry") or {}).get("coordinates", [0, 0, 0])
            lat = coords[1] if len(coords) > 1 else 0
            lng = coords[0] if len(coords) > 0 else 0
            depth = coords[2] if len(coords) > 2 else 0
            # 嚴格篩選台灣地區：地名含 Taiwan/嘉義，或座標落在台灣範圍內（21-26N, 119-123E）
            is_taiwan = (
                "Taiwan" in place
                or "嘉義" in place
                or (21.0 <= lat <= 26.0 and 119.0 <= lng <= 123.5)
            )
            if not is_taiwan:
                continue
            ts = props.get("time", 0)
            dt = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M") if ts else ""
            tw_quakes.append({
                "title": f"規模 {mag:.1f}・{place}",
                "desc": f"深度 {depth:.0f} km",
                "date": dt,
                "link": props.get("url", ""),
                "mag": mag,
            })
        # 排序：嘉義優先，再依時間（最新優先）
        tw_quakes.sort(key=lambda x: (0 if "嘉義" in x["title"] else 1, x["date"]), reverse=True)
        tw_quakes.sort(key=lambda x: 0 if "嘉義" in x["title"] else 1)
        result = tw_quakes[:8]
        print(f"  [earthquake] USGS 取得 {len(result)} 筆台灣地震（篩選自 {len(features)} 筆全球）")
        if result:
            return result
    except Exception as e:
        print(f"  [earthquake_usgs] 失敗: {e}")

    # 方法 2: CWA 開放資料 API（需 key）
    CWA_KEY = "CWA-9A6AF8D4-6014-44A4-B66E-AC9FE54CC8CB"
    for dataset_id in ["E-A0015-001", "E-A0016-001"]:
        url = (
            f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/{dataset_id}"
            f"?Authorization={CWA_KEY}&format=JSON&limit=10"
        )
        try:
            data = _get_json(url, timeout=15)
            records = data.get("records", {})
            eq_list = records.get("Earthquake", records.get("earthquake", []))
            items = []
            for eq in eq_list[:6]:
                info = eq.get("EarthquakeInfo", {})
                epicenter = info.get("Epicenter", {})
                mag = info.get("EarthquakeMagnitude", {}).get("MagnitudeValue", "")
                loc = epicenter.get("Location", "")
                depth = info.get("FocalDepth", "")
                origin_time = info.get("OriginTime", "")
                items.append({
                    "title": f"規模 {mag}・{loc}",
                    "desc": f"深度 {depth} km",
                    "date": str(origin_time)[:16],
                    "link": eq.get("Web", ""),
                    "mag": float(mag) if mag else 0,
                })
            if items:
                print(f"  [earthquake_cwa] 取得 {len(items)} 筆地震")
                return items
        except Exception as e:
            print(f"  [earthquake_cwa_{dataset_id}] 失敗: {e}")

    return []


# ── 4. 氣象觀測（Open-Meteo 免費 API，無需 key） ────────────────────────────
def fetch_weather():
    """嘉義市目前氣象觀測資料（Open-Meteo + CWA 備援）"""
    # 嘉義市中心座標
    LAT, LNG = 23.4800, 120.4483

    # 方法 1: Open-Meteo（完全免費，無需 key）
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={LAT}&longitude={LNG}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation"
            f",apparent_temperature,wind_speed_10m,wind_direction_10m"
            f",weather_code,cloud_cover"
            f"&timezone=Asia%2FTaipei&forecast_days=1"
        )
        data = _get_json(url, timeout=15)
        cur = data.get("current", {})
        cu = data.get("current_units", {})
        # 天氣描述代碼對照
        wmo = {0:"晴",1:"多雲",2:"多雲",3:"陰天",
               45:"霧",48:"霧",51:"毛雨",53:"細雨",55:"毛雨",
               61:"小雨",63:"中雨",65:"大雨",71:"小雪",80:"陣雨",
               81:"陣雨",82:"暴雨",95:"雷雨",96:"雷暴",99:"強雷暴"}
        wcode = int(cur.get("weather_code", 0) or 0)
        desc = wmo.get(wcode, f"WMO{wcode}")
        obs = [{
            "station": "嘉義市（Open-Meteo）",
            "temp": str(cur.get("temperature_2m", "")),
            "apparent_temp": str(cur.get("apparent_temperature", "")),
            "humidity": str(cur.get("relative_humidity_2m", "")),
            "rainfall": str(cur.get("precipitation", 0)),
            "wind_speed": str(cur.get("wind_speed_10m", "")),
            "wind_dir": str(cur.get("wind_direction_10m", "")),
            "cloud": str(cur.get("cloud_cover", "")),
            "weather": desc,
            "time": str(cur.get("time", "")).replace("T", " "),
            "source": "Open-Meteo",
        }]
        print(f"  [weather] Open-Meteo: {obs[0]['temp']}°C, {desc}, {obs[0]['wind_speed']}km/h")
        return obs
    except Exception as e:
        print(f"  [weather_openmeteo] 失敗: {e}")

    # 方法 2: CWA（需有效 API key）
    CWA_KEY = "CWA-9A6AF8D4-6014-44A4-B66E-AC9FE54CC8CB"
    url2 = (
        f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001"
        f"?Authorization={CWA_KEY}&format=JSON&StationName=嘉義"
    )
    try:
        data2 = _get_json(url2, timeout=15)
        stations = (
            data2.get("records", {}).get("location", []) or
            data2.get("records", {}).get("Station", [])
        )
        obs2 = []
        for s in stations:
            we = s.get("weatherElement", s.get("WeatherElement", {}))
            if isinstance(we, list):
                we_map = {e.get("elementName"): e.get("elementValue") for e in we}
                obs2.append({
                    "station": s.get("locationName", s.get("StationName", "")),
                    "temp": str(we_map.get("TEMP", we_map.get("AirTemperature", ""))),
                    "humidity": str(we_map.get("HUMD", we_map.get("RelativeHumidity", ""))),
                    "rainfall": str(we_map.get("RAIN", "")),
                    "wind_speed": str(we_map.get("WDSD", "")),
                    "time": str(s.get("time", {}).get("obsTime", "") or ""),
                    "source": "CWA",
                })
            elif isinstance(we, dict):
                obs2.append({
                    "station": s.get("StationName", ""),
                    "temp": str(we.get("AirTemperature", "")),
                    "humidity": str(we.get("RelativeHumidity", "")),
                    "rainfall": str((we.get("Now") or {}).get("Precipitation", "")),
                    "wind_speed": str(we.get("WindSpeed", "")),
                    "time": str((s.get("ObsTime") or {}).get("DateTime", "")),
                    "source": "CWA",
                })
        if obs2:
            print(f"  [weather_cwa] 取得 {len(obs2)} 筆氣象觀測")
            return obs2
    except Exception as e:
        print(f"  [weather_cwa] 失敗: {e}")

    return []


# ── 5. 嘉義市政府官方公告（多來源） ─────────────────────────────────────────
def fetch_city_announcements():
    """嘉義市政府最新施政公告（RSS + Google News 備援）"""
    items = []
    seen = set()

    # 方法 1: 嘉義市政府 RSS（XML 可能包含非標準字符，使用 lxml/容錯解析）
    FEEDS = [
        "https://www.chiayi.gov.tw/RSS/GetRss.aspx?node=7025",
        "https://www.chiayi.gov.tw/RSS/GetRss.aspx?node=7126",
    ]
    for url in FEEDS:
        try:
            raw = _get(url, timeout=15)
            # 清理非法 XML 字符
            raw_str = raw.decode("utf-8", errors="replace")
            import re as _re
            raw_str = _re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw_str)
            root = ET.fromstring(raw_str.encode("utf-8"))
            for item in root.findall(".//item")[:8]:
                title = (item.findtext("title", "") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                pub = (item.findtext("pubDate", "") or "")
                link = (item.findtext("link", "") or "")
                cdata = (item.findtext("description", "") or "").strip()
                # 清理 HTML tags
                desc = _re.sub(r'<[^>]+>', '', cdata)[:100]
                items.append({
                    "title": title[:80],
                    "date": pub[:16],
                    "link": link,
                    "desc": desc,
                    "source": "嘉義市政府",
                })
        except Exception as e:
            print(f"  [city_ann_rss] {url} 失敗: {e}")

    # 方法 2: Google News RSS 備援（搜尋嘉義市政府最新消息）
    if len(items) < 3:
        try:
            q = urllib.parse.quote("嘉義市政府")
            gn_url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            raw2 = _get(gn_url, timeout=15)
            root2 = ET.fromstring(raw2)
            for item in root2.findall(".//item")[:6]:
                title = (item.findtext("title", "") or "").strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                items.append({
                    "title": title[:80],
                    "date": (item.findtext("pubDate", "") or "")[:16],
                    "link": item.findtext("link", "") or "",
                    "desc": "",
                    "source": "Google新聞",
                })
        except Exception as e:
            print(f"  [city_ann_gn] 失敗: {e}")

    print(f"  [city_ann] 取得 {len(items)} 則市府公告")
    return items[:15]


# ── 6. 政府工程採購（嘉義市相關） ───────────────────────────────────────────
def fetch_procurement():
    """嘉義市近期政府工程採購與工程資料"""
    items = []

    # 方法 1: 嘉義市政府開放資料平台（建設、工程類）
    try:
        _CHIAYI_BASE = "https://data.chiayi.gov.tw/opendata/"
        for keyword in ["建設", "工程", "採購", "設施"]:
            try:
                params = {"page": 1, "rows": 8, "orgids": "", "q": keyword}
                if _HAS_REQUESTS:
                    r = _req.post(
                        f"{_CHIAYI_BASE}dataset/dataset_json",
                        data=params,
                        headers=HEADERS,
                        timeout=15,
                    )
                    ds_data = r.json()
                else:
                    encoded = urllib.parse.urlencode(params).encode()
                    req = urllib.request.Request(
                        f"{_CHIAYI_BASE}dataset/dataset_json",
                        data=encoded, headers=HEADERS, method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        ds_data = json.loads(resp.read())
                for d in ds_data.get("rows", []):
                    title = d.get("name", "")
                    if not title:
                        continue
                    org = d.get("org", {})
                    org_name = org.get("name", "") if isinstance(org, dict) else str(org)
                    items.append({
                        "title": title[:80],
                        "date": d.get("modified", "")[:10],
                        "link": f"{_CHIAYI_BASE}Datasets/Details/{d.get('id','')}",
                        "org": org_name[:40],
                        "source": "嘉義市開放資料",
                    })
                if len(items) >= 8:
                    break
            except Exception as e:
                print(f"  [procurement_chiayi_{keyword}] 失敗: {type(e).__name__}")
        if items:
            print(f"  [procurement] 嘉義市開放資料取得 {len(items)} 筆")
    except Exception as e:
        print(f"  [procurement_chiayi] 失敗: {e}")

    # 方法 2: Google News（採購/工程關鍵字）
    if len(items) < 3:
        try:
            q = urllib.parse.quote("嘉義市 工程 採購 OR 建設")
            gn_url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            raw2 = _get(gn_url, timeout=15)
            root2 = ET.fromstring(raw2)
            seen_titles = {i["title"] for i in items}
            for item in root2.findall(".//item")[:8]:
                title = (item.findtext("title", "") or "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                items.append({
                    "title": title[:80],
                    "date": (item.findtext("pubDate", "") or "")[:16],
                    "link": item.findtext("link", "") or "",
                    "org": "新聞資訊",
                    "source": "Google新聞",
                })
        except Exception as e:
            print(f"  [procurement_news] 失敗: {e}")

    print(f"  [procurement] 取得 {len(items)} 筆採購/工程資料")
    return items[:10]


# ── 7. 登革熱及腸病毒統計（疾管署 CDC） ────────────────────────────────────
def fetch_disease_stats():
    """嘉義市疾病統計（登革熱、腸病毒）"""
    results = {"dengue": [], "enterovirus": [], "updated": datetime.now().strftime("%Y-%m-%d")}

    # ── 登革熱縣市統計 ──
    DENGUE_URLS = [
        "https://data.cdc.gov.tw/api/v2/stats/dengue/county",
        "https://data.cdc.gov.tw/api/v1/disease/dengue01_06",    # 舊版 API
        "https://data.gov.tw/api/v1/rest/dataset?q=登革熱+嘉義&size=5",
    ]
    for url in DENGUE_URLS:
        try:
            if _HAS_REQUESTS:
                r = _req.get(url, headers=HEADERS, timeout=15, verify=False)
                r.raise_for_status()
                data = r.json()
            else:
                import ssl
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(
                    urllib.request.Request(url, headers=HEADERS), timeout=15, context=ctx
                ) as resp:
                    data = json.loads(resp.read())

            records = data.get("records") or data.get("result", {}).get("results") or (data if isinstance(data, list) else [])
            chiayi = [r for r in records
                      if "嘉義" in str(r.get("縣市") or r.get("縣市別") or r.get("city") or r.get("title") or "")]
            if chiayi:
                results["dengue"] = chiayi[:12]
                print(f"  [disease_dengue] {len(results['dengue'])} 筆")
                break
        except Exception as e:
            print(f"  [disease_dengue] {url[:50]}... 失敗: {type(e).__name__}")

    # ── 腸病毒週統計 ──
    ENTERO_URLS = [
        "https://data.cdc.gov.tw/api/v2/stats/enterovirus/county",
    ]
    for url2 in ENTERO_URLS:
        try:
            if _HAS_REQUESTS:
                r2 = _req.get(url2, headers=HEADERS, timeout=15, verify=False)
                r2.raise_for_status()
                data2 = r2.json()
            else:
                data2 = _get_json(url2, timeout=15)
            records2 = data2.get("records") or (data2 if isinstance(data2, list) else [])
            chiayi2 = [r for r in records2
                       if "嘉義" in str(r.get("縣市") or r.get("city") or "")]
            if chiayi2:
                results["enterovirus"] = chiayi2[:12]
                print(f"  [disease_entero] {len(results['enterovirus'])} 筆")
                break
        except Exception as e:
            print(f"  [disease_entero] 失敗: {type(e).__name__}")

    return results


# ── 8. 消防救護統計（消防署 / 嘉義市消防局） ────────────────────────────────
def fetch_fire_stats():
    """嘉義市消防火災救護統計"""
    results = {}

    # 消防署開放資料搜尋
    FIRE_URLS = [
        "https://data.nfa.gov.tw/api/v2/dataset?keyword=嘉義&limit=10",
        "https://data.gov.tw/api/v1/rest/dataset?q=嘉義市+消防+火災&size=10",
    ]
    for url in FIRE_URLS:
        try:
            data = _get_json(url, timeout=15)
            # data.nfa.gov.tw 格式
            if "result" in data:
                items = data.get("result", {}).get("results", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
            fire_items = []
            for d in items[:5]:
                fire_items.append({
                    "title": d.get("title", d.get("name", ""))[:60],
                    "org": (d.get("organization") or {}).get("title", d.get("author", ""))[:30],
                    "date": d.get("modified", d.get("updateFrequency", ""))[:10],
                    "url": (d.get("resources") or [{}])[0].get("url", "") if d.get("resources") else "",
                })
            if fire_items:
                results["datasets"] = fire_items
                print(f"  [fire] 取得 {len(fire_items)} 筆消防資料集")
                break
        except Exception as e:
            print(f"  [fire] {url} 失敗: {e}")

    # 嘉義市政府消防局開放資料（data.chiayi.gov.tw）
    try:
        _CHIAYI_BASE2 = "https://data.chiayi.gov.tw/opendata/"
        search_url = f"{_CHIAYI_BASE2}dataset/dataset_json"
        params = {"page": 1, "rows": 10, "orgids": "", "q": "消防"}
        if _HAS_REQUESTS:
            r = _req.post(search_url, data=params, headers=HEADERS, timeout=TIMEOUT)
            ds_data = r.json()
        else:
            encoded = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(search_url, data=encoded, headers=HEADERS, method="POST")
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                ds_data = json.loads(resp.read())
        # API 回傳格式可能是 dict (含 "rows") 或 list
        if isinstance(ds_data, dict):
            fire_ds = ds_data.get("rows", [])[:5]
        elif isinstance(ds_data, list):
            fire_ds = ds_data[:5]
        else:
            fire_ds = []
        results["chiayi_datasets"] = [
            {"title": (d.get("name", "") if isinstance(d, dict) else ""),
             "date": (d.get("modified", "")[:10] if isinstance(d, dict) else "")}
            for d in fire_ds if isinstance(d, dict)
        ]
        print(f"  [fire_chiayi] 取得 {len(results['chiayi_datasets'])} 筆嘉義消防資料集")
    except Exception as e:
        print(f"  [fire_chiayi] 失敗: {type(e).__name__}: {e}")

    return results


# ── 9. 人口趨勢（內政部戶政司） ─────────────────────────────────────────────
def fetch_population_trend():
    """嘉義市近年人口異動趨勢（出生、死亡、遷入、遷出）"""
    # 內政部戶政司開放資料
    URLS = [
        # 各縣市人口統計（月）
        "https://data.moi.gov.tw/MoiOD/Data/DataContent?oid=408DCD52-3821-4785-8D13-B6A06D16E6F5",
        # 全國人口統計摘要
        "https://ws.moi.gov.tw/001/Upload/OldFile/社會指標統計表/1/1-01.csv",
    ]
    for url in URLS:
        try:
            raw = _get(url, timeout=20)
            # JSON 格式
            data = json.loads(raw)
            records = data if isinstance(data, list) else data.get("records", data.get("result", []))
            chiayi = [r for r in records
                      if "嘉義市" in str(r.get("縣市別") or r.get("區域別") or r.get("site_id") or "")]
            if chiayi:
                print(f"  [population] 取得 {len(chiayi)} 筆人口統計")
                return chiayi[:24]
        except json.JSONDecodeError:
            pass  # CSV 格式，跳過
        except Exception as e:
            print(f"  [population] {url} 失敗: {e}")
    return []


# ── 10. 嘉義市公車路線（TDX / PTX 交通部）──────────────────────────────────
def fetch_bus_routes():
    """嘉義市市區公車路線資料"""
    # TDX API（交通部運輸資料流通服務平臺，2023年後取代 PTX）
    # 嘉義市公車路線
    URLS = [
        # TDX v2 API（不需 token 的公開端點）
        "https://tdx.transportdata.tw/api/basic/v2/Bus/Route/City/Chiayi?%24top=30&%24format=JSON",
        # 嘉義縣
        "https://tdx.transportdata.tw/api/basic/v2/Bus/Route/City/ChiayiCounty?%24top=20&%24format=JSON",
        # 全國公路客運（含嘉義）
        "https://tdx.transportdata.tw/api/basic/v2/Bus/Route/Intercity?%24filter=DestinationStopNameZh+eq+%27嘉義%27+or+DepartureStopNameZh+eq+%27嘉義%27&%24top=20&%24format=JSON",
    ]
    for url in URLS:
        try:
            if _HAS_REQUESTS:
                # TDX 接受無 token 的有限次數存取
                r = _req.get(url, headers={
                    **HEADERS,
                    "Accept": "application/json",
                }, timeout=15)
                if r.status_code == 403:
                    continue  # 需要 token，跳過
                r.raise_for_status()
                data = r.json()
            else:
                data = _get_json(url, timeout=15)

            routes = data if isinstance(data, list) else data.get("BusRoutes", [])
            if not routes:
                continue
            result = []
            for route in routes[:25]:
                rn = route.get("RouteName", {})
                name = rn.get("Zh_tw", str(rn)) if isinstance(rn, dict) else str(rn)
                result.append({
                    "id": route.get("RouteUID", route.get("RouteID", "")),
                    "name": name,
                    "from": route.get("DepartureStopNameZh", ""),
                    "to": route.get("DestinationStopNameZh", ""),
                })
            if result:
                print(f"  [bus] {url[:50]}... 取得 {len(result)} 條公車路線")
                return result
        except Exception as e:
            print(f"  [bus] {url[:50]}... 失敗: {type(e).__name__}: {e}")

    # 靜態備援（嘉義市公車主要路線）
    print("  [bus] 使用靜態備援資料")
    return [
        {"id": "7", "name": "7路（市區環線）", "from": "火車站", "to": "東門圓環", "static": True},
        {"id": "8", "name": "8路（嘉義大學線）", "from": "火車站", "to": "嘉大蘭潭校區", "static": True},
        {"id": "13", "name": "13路（竹崎線）", "from": "嘉義", "to": "竹崎", "static": True},
        {"id": "22", "name": "22路（朴子線）", "from": "嘉義", "to": "朴子", "static": True},
        {"id": "R1", "name": "紅1（嘉義－高鐵）", "from": "嘉義後站", "to": "嘉義高鐵站", "static": True},
    ]


# ── 11. 嘉義 YouBike 站點（TDX / YouBike API） ──────────────────────────────
def fetch_youbike():
    """嘉義市 YouBike 站點資料"""
    URLS = [
        # TDX Bike Station API（嘉義市）
        "https://tdx.transportdata.tw/api/basic/v2/Bike/Station/City/Chiayi?%24top=30&%24format=JSON",
        # TDX Bike Availability（可借數）
        "https://tdx.transportdata.tw/api/basic/v2/Bike/Availability/City/Chiayi?%24top=30&%24format=JSON",
    ]
    stations_map = {}  # StationUID → info

    for url in URLS:
        try:
            if _HAS_REQUESTS:
                r = _req.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
                if r.status_code == 403:
                    continue
                r.raise_for_status()
                data = r.json()
            else:
                data = _get_json(url, timeout=15)

            items = data if isinstance(data, list) else []
            for item in items:
                uid = item.get("StationUID", "")
                if not uid:
                    continue
                if uid not in stations_map:
                    sn = item.get("StationName", {})
                    name = sn.get("Zh_tw", str(sn)) if isinstance(sn, dict) else str(sn)
                    addr = item.get("StationAddress", {})
                    addr_str = addr.get("Zh_tw", str(addr)) if isinstance(addr, dict) else str(addr)
                    pos = item.get("StationPosition", {})
                    stations_map[uid] = {
                        "id": uid,
                        "name": name.replace("YouBike2.0_", ""),
                        "lat": float(pos.get("PositionLat", 0)),
                        "lng": float(pos.get("PositionLon", 0)),
                        "total": int(item.get("BikesCapacity", 0)),
                        "available": int(item.get("AvailableRentBikes", 0)),
                        "addr": addr_str,
                    }
                else:
                    # Availability update
                    stations_map[uid]["available"] = int(item.get("AvailableRentBikes", 0))
        except Exception as e:
            print(f"  [youbike] {url[:50]}... 失敗: {type(e).__name__}")

    if stations_map:
        result = list(stations_map.values())[:20]
        print(f"  [youbike] 取得 {len(result)} 個 YouBike 站")
        return result

    print("  [youbike] 嘉義市目前無 YouBike 服務資料")
    return []


# ── 12. 嘉義市水情即時（水利署 WRAP） ──────────────────────────────────────
def fetch_water_level():
    """嘉義市河川水位即時資料（水利署）"""
    # 水利署水情資料 API
    try:
        url = "https://www.wrap.gov.tw/wrp2/opendata/getInfo.do?type=RIVERGAUGE&area=嘉義市"
        data = _get_json(url, timeout=15)
        stations = data if isinstance(data, list) else data.get("data", [])
        result = []
        for s in stations[:10]:
            result.append({
                "station": s.get("name", s.get("stationName", "")),
                "river": s.get("river", s.get("riverName", "")),
                "level": float(s.get("waterLevel", s.get("level", 0)) or 0),
                "flow": float(s.get("flow", s.get("discharge", 0)) or 0),
                "status": s.get("status", ""),
                "time": s.get("time", s.get("obsTime", "")),
            })
        if result:
            print(f"  [water] 取得 {len(result)} 個水位站")
        return result
    except Exception as e:
        print(f"  [water] 失敗: {e}")
        return []


# ── 整合函數 ─────────────────────────────────────────────────────────────────
def fetch_all_citydata():
    """整合所有嘉義市城市資料，回傳 dict（各類別資料）"""
    start = time.time()
    out = {"updated_at": datetime.now().isoformat()}

    steps = [
        ("aqi_realtime",   fetch_aqi_realtime),
        ("aqi_history",    fetch_aqi_history),
        ("earthquake",     fetch_earthquake),
        ("weather",        fetch_weather),
        ("announcements",  fetch_city_announcements),
        ("procurement",    fetch_procurement),
        ("disease",        fetch_disease_stats),
        ("fire",           fetch_fire_stats),
        ("population",     fetch_population_trend),
        ("bus",            fetch_bus_routes),
        ("youbike",        fetch_youbike),
        ("water",          fetch_water_level),
    ]

    for key, fn in steps:
        try:
            out[key] = fn()
        except Exception as e:
            print(f"  [citydata.{key}] 未預期錯誤: {e}")
            out[key] = []

    elapsed = time.time() - start
    out["fetch_seconds"] = round(elapsed, 1)
    print(f"  [citydata] 完成，共 {elapsed:.1f}s，{len(steps)} 個來源")
    return out
