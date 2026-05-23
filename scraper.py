"""
主爬蟲程式 — 嘉義市城市故障分析儀表板資料更新
執行：python scraper.py
GitHub Actions 每小時自動執行一次
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def save_json(filename: str, data: object) -> None:
    path = DATA_DIR / filename
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [save] {path.name} ({len(data) if isinstance(data, list) else 1} 筆)")


def load_json(filename: str, default=None):
    path = DATA_DIR / filename
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default if default is not None else []


def run_news():
    print("\n=== 新聞爬蟲 ===")
    from scrapers.news import fetch_all_news
    news = fetch_all_news()
    save_json("news.json", news)
    return news


def run_opendata():
    print("\n=== 開放資料爬蟲（嘉義市真實 API）===")
    from scrapers.opendata import (
        fetch_opendata_datasets, fetch_all_opendata_records, build_complaint_stats,
        fetch_west_district_population,
    )

    # 1. 儲存資料集清單（中繼資料）
    datasets = fetch_opendata_datasets()
    save_json("opendata_datasets.json", datasets)

    # 2. 下載所有已知資料集的真實資料（交通事故、管線挖掘、路燈、橋梁、停車場等）
    all_records = fetch_all_opendata_records()

    if all_records:
        save_json("opendata_records.json", all_records)
        # 統計時排除人口類別（人口不是「投訴」，不計入市政問題統計）
        infra_only = [r for r in all_records if r.get("category") not in ("西區人口",)]
        stats = build_complaint_stats(infra_only)
        save_json("complaint_stats.json", stats)
    else:
        stats = load_json("complaint_stats.json", {})

    # 3. 單獨儲存西區各里人口資料（選戰分析用）
    west_pop = fetch_west_district_population()
    if west_pop:
        save_json("west_population.json", west_pop)

    return stats


def run_council():
    print("\n=== 議會爬蟲 ===")
    from scrapers.council import fetch_all_council_data
    data = fetch_all_council_data()
    save_json("council.json", data)
    return data


def run_citizen_reports():
    print("\n=== 市民通報整合 ===")
    from scrapers.citizen_reports import fetch_from_sheet, build_stats
    records = fetch_from_sheet()
    if records:
        save_json("citizen_reports.json", records)
        stats = build_stats(records)
        save_json("citizen_stats.json", stats)
        return stats
    else:
        return load_json("citizen_stats.json", {})


def run_social():
    print("\n=== 社群聲音爬蟲（PTT + Dcard + Meta）===")
    from scrapers.social import fetch_all_social
    from scrapers.meta_social import fetch_all_meta

    ptt_dcard = fetch_all_social()
    meta = fetch_all_meta()

    # 合併去重（以 id 為 key）
    seen: set[str] = set()
    merged: list[dict] = []
    for p in ptt_dcard + meta:
        if p["id"] not in seen:
            seen.add(p["id"])
            merged.append(p)

    if merged:
        save_json("social_posts.json", merged)
    else:
        merged = load_json("social_posts.json", [])
    return merged


def build_dashboard(news, complaint_stats, council_data, citizen_stats, social_posts=None):
    print("\n=== 更新儀表板 ===")
    import re

    social_posts = social_posts or []
    dashboard_data = {
        "updated_at": datetime.now().isoformat(),
        "news": news[:12],
        "complaint_stats": complaint_stats,
        "council": {
            "meetings_count": len(council_data.get("meetings", [])),
            "councilors": council_data.get("councilor_names", []),
            "question_count": len(council_data.get("question_records", [])),
        },
        "citizen_stats": citizen_stats,
        "social_posts": social_posts[:30],
    }
    save_json("dashboard_data.json", dashboard_data)

    # 更新 index.html 中的資料
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        print("  [build] index.html 不存在，跳過")
        return

    html = index_path.read_text(encoding="utf-8")

    # 注入西區各里人口資料
    west_pop = load_json("west_population.json", [])
    if west_pop:
        west_pop_json = json.dumps(west_pop, ensure_ascii=False)
        html = re.sub(
            r"const westPopData\s*=\s*\[.*?\];",
            f"const westPopData = {west_pop_json};",
            html,
            flags=re.DOTALL,
        )

    # 注入 dataset (market complaint data)
    complaint_records = load_json("opendata_records.json", [])
    citizen_records = load_json("citizen_reports.json", [])
    # 過濾掉人口類別（不需要顯示在主表格）
    infra_records = [r for r in complaint_records if r.get("category") not in ("西區人口",)]
    all_records = infra_records + citizen_records

    def clean_str(v):
        """清理字串中的控制字符，避免 JSON 注入到 HTML 時出錯"""
        if isinstance(v, str):
            return v.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
        return v

    def clean_record(r):
        return {k: clean_str(v) for k, v in r.items()}

    all_records_clean = [clean_record(r) for r in all_records[:500]]
    dataset_json = json.dumps(all_records_clean, ensure_ascii=False)
    html = re.sub(
        r"const dataset\s*=\s*\[.*?\];",
        f"const dataset = {dataset_json};",
        html,
        flags=re.DOTALL,
    )

    # ── 注入議題類別統計（13 大類別：開放資料 + 社群 + 新聞 + 議會）──────────
    cat_data = complaint_stats.get("top_categories", []) or citizen_stats.get("category_counts", {})
    if isinstance(cat_data, dict):
        cat_data = [{"category": k, "count": v} for k, v in cat_data.items()]
    # 過濾掉舊分類名稱 / 人口
    EXCLUDE_CATS = {"西區人口", "道路交通", "路燈照明", "道路工程", "市政服務",
                    "停車設施", "橋梁設施", "噪音管制"}
    cat_data = [d for d in cat_data if d.get("category") not in EXCLUDE_CATS]

    VALID_CATS = {"交通停車", "道路路平", "人行步道", "環境衛生", "排水水利",
                  "公共安全", "市場商圈", "公園綠地", "通學安全", "社福高齡",
                  "文化觀光", "行政服務", "其他"}

    # 來源分解計數器：{cat: {opendata, social, news, council}}
    def _src_add(src_map, cat, src, n=1):
        if cat not in src_map:
            src_map[cat] = {"opendata": 0, "social": 0, "news": 0, "council": 0}
        src_map[cat][src] = src_map[cat].get(src, 0) + n

    cat_sources: dict[str, dict] = {}

    # 1. 開放資料 → cat_map（count 加總）
    cat_map: dict[str, int] = {}
    for d in cat_data:
        cat_map[d["category"]] = d["count"]
        _src_add(cat_sources, d["category"], "opendata", d["count"])

    # 2. 社群貼文
    for post in (social_posts or []):
        pcat = post.get("category", "其他")
        if pcat in VALID_CATS:
            cat_map[pcat] = cat_map.get(pcat, 0) + 1
            _src_add(cat_sources, pcat, "social")

    # 3. 新聞文章（依標題分類，計入類別並建立 newsByCat）
    news_by_cat: dict[str, list] = {}
    for article in (news or []):
        txt = article.get("headline", "") + " " + article.get("query", "")
        cat = classify_text(txt)
        # 收錄到 newsByCat（所有類別含「其他」）
        if cat not in news_by_cat:
            news_by_cat[cat] = []
        if len(news_by_cat[cat]) < 5:   # 每類最多 5 則
            news_by_cat[cat].append({
                "title": article.get("headline", "")[:80],
                "source": article.get("source", ""),
                "date": article.get("date", "")[:10],
                "url": article.get("link", ""),
            })
        # 計入類別
        if cat in VALID_CATS:
            cat_map[cat] = cat_map.get(cat, 0) + 1
            _src_add(cat_sources, cat, "news")

    # 4. 議員質詢 / 議會會議紀錄（分類後計入 行政服務 + 對應類別）
    council_items = council_data.get("meetings", []) + council_data.get("question_records", [])
    for item in council_items:
        txt = item.get("type", "") + " " + item.get("snippet", "")
        cat = classify_text(txt)
        if cat == "其他":
            cat = "行政服務"   # 議會事務預設歸 行政服務
        if cat in VALID_CATS:
            cat_map[cat] = cat_map.get(cat, 0) + 1
            _src_add(cat_sources, cat, "council")

    # 確保所有 12 非「其他」類別都出現
    for c in VALID_CATS - {"其他"}:
        if c not in cat_map:
            cat_map[c] = 0

    cat_data = sorted([{"category": k, "count": v} for k, v in cat_map.items()
                        if k != "其他"],
                       key=lambda x: -x["count"])
    if "其他" in cat_map and cat_map["其他"] > 0:
        cat_data.append({"category": "其他", "count": cat_map["其他"]})

    cat_json = json.dumps(cat_data, ensure_ascii=False)
    html = re.sub(
        r"const categoryData\s*=\s*\[.*?\];",
        f"const categoryData = {cat_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入 newsByCat（各類別相關新聞）
    news_by_cat_json = json.dumps(news_by_cat, ensure_ascii=False)
    html = re.sub(
        r"const newsByCat\s*=\s*\{.*?\};",
        f"const newsByCat = {news_by_cat_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入 catSources（各類別資料來源分解）
    cat_sources_json = json.dumps(cat_sources, ensure_ascii=False)
    html = re.sub(
        r"const catSources\s*=\s*\{.*?\};",
        f"const catSources = {cat_sources_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入議會統計（會議場次、議員質詢等）
    council_stat = {
        "meetings_count": len(council_data.get("meetings", [])),
        "question_count": len(council_data.get("question_records", [])),
        "councilors": len(council_data.get("councilor_names", [])),
    }
    html = re.sub(
        r"const councilStat\s*=\s*\{.*?\};",
        f"const councilStat = {json.dumps(council_stat, ensure_ascii=False)};",
        html,
        flags=re.DOTALL,
    )

    # 注入路段熱點
    road_data = complaint_stats.get("top_roads", []) or citizen_stats.get("top_roads", [])
    road_json = json.dumps(road_data[:10], ensure_ascii=False)
    html = re.sub(
        r"const roadData\s*=\s*\[.*?\];",
        f"const roadData = {road_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入社群聲音 HTML（id="social-feed"）
    all_social = load_json("social_posts.json", [])
    if all_social:
        social_parts = []
        for p in all_social[:20]:
            color = p.get("platform_color", "#666")
            platform = p.get("platform", "")
            board = p.get("board", "")
            board_tag = f' · {board}' if board else ''
            reactions = p.get("reactions", 0)
            comments = p.get("comments", 0)
            excerpt = p.get("excerpt", "")
            excerpt_html = f'<p class="text-xs text-slate-500 mt-1 leading-relaxed line-clamp-2">{excerpt}</p>' if excerpt else ''
            social_parts.append(
                f'<div class="social-card bg-white rounded-xl p-4 border border-slate-100 hover:border-slate-300 transition-colors">'
                f'<div class="flex items-center gap-2 mb-2">'
                f'<span class="text-xs font-black px-2 py-0.5 rounded-full text-white" style="background:{color}">{platform}</span>'
                f'<span class="text-xs text-slate-400">{board_tag}</span>'
                f'<span class="text-xs text-slate-400 ml-auto">{p.get("date","")}</span>'
                f'</div>'
                f'<a href="{p["url"]}" target="_blank" rel="noopener" '
                f'class="text-sm font-bold text-slate-800 leading-snug hover:text-orange-500 transition-colors block">'
                f'{p["title"]}</a>'
                f'{excerpt_html}'
                f'<div class="flex items-center gap-3 mt-2 text-xs text-slate-400">'
                f'<span>👍 {reactions}</span><span>💬 {comments}</span>'
                f'<span class="ml-auto text-xs px-2 py-0.5 bg-slate-100 rounded-full">{p.get("category","")}</span>'
                f'</div>'
                f'</div>'
            )
        social_html = "\n".join(social_parts)
        html = re.sub(
            r'(<div[^>]+id="social-feed"[^>]*>).*?(</div>\s*</div>\s*<!-- ── social-end)',
            rf"\1\n{social_html}\n</div>\n<!-- ── social-end",
            html,
            flags=re.DOTALL,
        )

    # 注入即時新聞 HTML（配合新版 id="news-list" + <!-- ── news-end --> 標記）
    if news:
        # 依來源決定顏色
        def _news_color(src):
            s = src or ''
            if '市政府' in s or '嘉義市' in s: return '#7C3AED'
            if 'PTT' in s: return '#00b300'
            if 'Dcard' in s: return '#ef4444'
            return '#F97316'

        # 依標題決定議題分類
        def _news_cat(n):
            return classify_text(n.get('headline','') + ' ' + n.get('query',''))

        # 分類顏色
        _cat_colors = {
            '交通停車':'#EF4444','道路路平':'#F97316','人行步道':'#F59E0B',
            '環境衛生':'#10B981','排水水利':'#3B82F6','公共安全':'#8B5CF6',
            '市場商圈':'#EC4899','公園綠地':'#22C55E','通學安全':'#06B6D4',
            '社福高齡':'#6366F1','文化觀光':'#A78BFA','行政服務':'#64748B','其他':'#94A3B8'
        }

        news_html_parts = []
        # 先放市府官方新聞（最多 3 則）
        gov_news = [n for n in news if '市政府' in (n.get('source',''))][:3]
        rss_news = [n for n in news if '市政府' not in (n.get('source',''))][:17]
        ordered_news = gov_news + rss_news

        for n in ordered_news[:20]:
            color = _news_color(n.get('source',''))
            cat = _news_cat(n)
            cat_color = _cat_colors.get(cat, '#94A3B8')
            src_label = (n.get('source','') or '新聞')[:20]
            date_str = (n.get('date','') or '')[:10]
            headline = (n.get('headline','') or '').replace('<','&lt;').replace('>','&gt;')[:90]
            url = n.get('link','') or '#'
            news_html_parts.append(
                f'<div class="news-card bg-white rounded-xl p-3 border border-slate-100">'
                f'<div class="flex items-center gap-1.5 mb-1.5">'
                f'<span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full text-white" style="background:{color}">{src_label}</span>'
                f'<span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full text-white" style="background:{cat_color}">{cat}</span>'
                f'<span class="text-[10px] text-slate-400 ml-auto font-en">{date_str}</span>'
                f'</div>'
                f'<a href="{url}" target="_blank" rel="noopener" '
                f'class="text-xs font-bold text-slate-800 leading-relaxed hover:text-orange-500 transition-colors block line-clamp-2">'
                f'{headline}</a>'
                f'</div>'
            )
        news_html = "\n".join(news_html_parts)
        html = re.sub(
            r'(<div[^>]+id="news-list"[^>]*>).*?(<!-- ── news-end)',
            rf"\1\n{news_html}\n</div>\n      <!-- ── news-end",
            html,
            flags=re.DOTALL,
        )

    # 注入更新時間（JS 會自動顯示，此處備用靜態注入）
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = html.replace("最後更新：載入中...", f"最後更新：{now_str}")

    index_path.write_text(html, encoding="utf-8")
    print(f"  [build] index.html 已更新（{len(all_records)} 筆記錄，{len(news)} 則新聞，{len(all_social)} 則社群聲音）")



# ── 共用：依關鍵詞將文字分類至 13 大議題 ─────────────────────────────────────
_CAT_KEYWORDS = {
    "交通停車": ["交通事故", "違規停車", "停車場", "車禍", "機車", "闖紅燈",
                 "行人穿越", "交通壅塞", "交通", "停車"],
    "道路路平": ["路面坑洞", "管線挖掘", "道路施工", "橋梁", "路坑", "路平",
                 "道路破損", "道路", "路面", "鋪路", "施工挖掘"],
    "人行步道": ["人行道", "步道", "騎樓", "無障礙", "行人空間"],
    "環境衛生": ["垃圾", "清潔", "噪音", "廢水", "環境衛生", "污染",
                 "臭味", "蚊蟲", "病媒", "環保", "資源回收"],
    "排水水利": ["排水", "積水", "淹水", "水溝", "颱風", "暴雨",
                 "下水道", "水患", "雨水"],
    "公共安全": ["路燈", "消防", "路燈不亮", "溺水", "事故傷亡", "死亡",
                 "危險建物", "公共安全", "意外"],
    "市場商圈": ["市場", "夜市", "攤販", "商圈", "小吃", "傳統市場", "逢甲"],
    "公園綠地": ["公園", "綠地", "行道樹", "廣場", "休閒設施", "樹木", "遊樂"],
    "通學安全": ["通學", "上學", "放學", "學生", "校園周邊", "學童", "接送"],
    "社福高齡": ["長照", "老人", "社福", "弱勢", "身障", "社會福利",
                 "獨居", "高齡", "照護", "托育"],
    "文化觀光": ["文化", "觀光", "旅遊", "古蹟", "藝術", "節慶",
                 "博物館", "嘉年華", "活動"],
    "行政服務": ["市政", "陳情", "市民服務", "1999", "申請", "質詢",
                 "施政", "議會", "議員", "預算"],
}


def classify_text(text: str) -> str:
    """依關鍵詞將文字分類至 13 大市政議題"""
    for cat, kws in _CAT_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return cat
    return "其他"


if __name__ == "__main__":
    print(f"[start] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 開始更新嘉義市城市故障分析儀表板")

    news = run_news()
    complaint_stats = run_opendata()
    council_data = run_council()
    citizen_stats = run_citizen_reports()
    social_posts = run_social()

    build_dashboard(news, complaint_stats, council_data, citizen_stats, social_posts)

    print(f"\n[done] 完成 ✓")
