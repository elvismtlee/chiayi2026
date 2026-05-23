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
            r"const westPopData = \[.*?\];",
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
        r"const dataset = \[.*?\];",
        f"const dataset = {dataset_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入議題類別統計（13 大類別，合併政府開放資料 + 社群媒體分類）
    cat_data = complaint_stats.get("top_categories", []) or citizen_stats.get("category_counts", {})
    if isinstance(cat_data, dict):
        cat_data = [{"category": k, "count": v} for k, v in cat_data.items()]
    # 過濾掉人口類別
    EXCLUDE_CATS = {"西區人口", "道路交通", "路燈照明", "道路工程", "市政服務",
                    "停車設施", "橋梁設施", "噪音管制"}
    cat_data = [d for d in cat_data if d.get("category") not in EXCLUDE_CATS]

    # 合併社群貼文的類別計數（讓 13 類別都有資料）
    # 使用已傳入的 social_posts 參數（不再重讀 JSON，all_social 在後面才載入）
    VALID_CATS = {"交通停車", "道路路平", "人行步道", "環境衛生", "排水水利",
                  "公共安全", "市場商圈", "公園綠地", "通學安全", "社福高齡",
                  "文化觀光", "行政服務", "其他"}
    cat_map = {d["category"]: d["count"] for d in cat_data}
    for post in (social_posts or []):
        pcat = post.get("category", "其他")
        if pcat in VALID_CATS:
            cat_map[pcat] = cat_map.get(pcat, 0) + 1

    # 確保所有 13 類別都出現（即使 count=0，也顯示在 UI 供使用者了解監測範圍）
    for c in VALID_CATS - {"其他"}:
        if c not in cat_map:
            cat_map[c] = 0

    cat_data = sorted([{"category": k, "count": v} for k, v in cat_map.items()
                        if k != "其他"],
                       key=lambda x: -x["count"])
    # 附加「其他」到最後
    if "其他" in cat_map and cat_map["其他"] > 0:
        cat_data.append({"category": "其他", "count": cat_map["其他"]})

    cat_json = json.dumps(cat_data, ensure_ascii=False)
    html = re.sub(
        r"const categoryData = \[.*?\];",
        f"const categoryData = {cat_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入路段熱點
    road_data = complaint_stats.get("top_roads", []) or citizen_stats.get("top_roads", [])
    road_json = json.dumps(road_data[:10], ensure_ascii=False)
    html = re.sub(
        r"const roadData = \[.*?\];",
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

    # 注入即時新聞 HTML（配合新版 id="news-list"）
    if news:
        news_html_parts = []
        for n in news[:12]:
            news_html_parts.append(
                f'<div class="news-card bg-white rounded-xl p-4 border border-slate-100">'
                f'<div class="flex justify-between items-center mb-2">'
                f'<span class="text-xs font-bold text-orange-500">{n["source"]}</span>'
                f'<span class="text-xs text-slate-400 font-en">{n["date"][:10]}</span>'
                f'</div>'
                f'<a href="{n["link"]}" target="_blank" rel="noopener" '
                f'class="text-sm font-bold text-slate-800 leading-relaxed hover:text-orange-500 transition-colors block">'
                f'{n["headline"]}</a>'
                f'</div>'
            )
        news_html = "\n".join(news_html_parts)
        html = re.sub(
            r'(<div[^>]+id="news-list"[^>]*>).*?(</div>\s*</div>\s*</div>\s*<!-- ── Row 3)',
            rf"\1\n{news_html}\n</div>\n<!-- ── Row 3",
            html,
            flags=re.DOTALL,
        )

    # 注入更新時間（JS 會自動顯示，此處備用靜態注入）
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = html.replace("最後更新：載入中...", f"最後更新：{now_str}")

    index_path.write_text(html, encoding="utf-8")
    print(f"  [build] index.html 已更新（{len(all_records)} 筆記錄，{len(news)} 則新聞，{len(all_social)} 則社群聲音）")


if __name__ == "__main__":
    print(f"[start] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 開始更新嘉義市城市故障分析儀表板")

    news = run_news()
    complaint_stats = run_opendata()
    council_data = run_council()
    citizen_stats = run_citizen_reports()
    social_posts = run_social()

    build_dashboard(news, complaint_stats, council_data, citizen_stats, social_posts)

    print(f"\n[done] 完成 ✓")
