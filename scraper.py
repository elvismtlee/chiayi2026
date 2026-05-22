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
    print("\n=== 開放資料爬蟲 ===")
    from scrapers.opendata import fetch_opendata_datasets, fetch_opendata_records, build_complaint_stats
    datasets = fetch_opendata_datasets()
    save_json("opendata_datasets.json", datasets)

    # 嘗試下載找到的 CSV/JSON 資源
    all_records = load_json("opendata_records.json", [])
    for ds in datasets:
        for res in ds.get("resources", []):
            url = res.get("url", "")
            if url and res.get("format", "").upper() in ("CSV", "JSON"):
                records = fetch_opendata_records(url)
                if records:
                    all_records.extend(records)
                    print(f"  [opendata] 下載 {len(records)} 筆: {ds['title']}")

    if all_records:
        save_json("opendata_records.json", all_records)
        stats = build_complaint_stats(all_records)
        save_json("complaint_stats.json", stats)
        return stats
    else:
        # 讀快取
        return load_json("complaint_stats.json", {})


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


def build_dashboard(news, complaint_stats, council_data, citizen_stats):
    print("\n=== 更新儀表板 ===")
    import re

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
    }
    save_json("dashboard_data.json", dashboard_data)

    # 更新 index.html 中的資料
    index_path = Path(__file__).parent / "index.html"
    if not index_path.exists():
        print("  [build] index.html 不存在，跳過")
        return

    html = index_path.read_text(encoding="utf-8")

    # 注入 dataset (market complaint data)
    complaint_records = load_json("opendata_records.json", [])
    citizen_records = load_json("citizen_reports.json", [])
    all_records = complaint_records + citizen_records

    dataset_json = json.dumps(all_records[:200], ensure_ascii=False)
    html = re.sub(
        r"const dataset = \[.*?\];",
        f"const dataset = {dataset_json};",
        html,
        flags=re.DOTALL,
    )

    # 注入議題類別統計
    cat_data = complaint_stats.get("top_categories", []) or citizen_stats.get("category_counts", {})
    if isinstance(cat_data, dict):
        cat_data = [{"category": k, "count": v} for k, v in cat_data.items()]
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

    # 注入即時新聞 HTML
    if news:
        news_html_parts = []
        for n in news[:10]:
            news_html_parts.append(
                f'<div class="block p-5 bg-white border-[0.5px] border-[#E2DFD8] shadow-sm hover:bg-stone-50 transition-colors group">'
                f'<div class="flex justify-between items-center mb-3">'
                f'<span class="px-2 py-0.5 text-[10px] font-sans font-bold tracking-widest uppercase bg-stone-800 text-white">即時新聞</span>'
                f'<span class="text-[11px] text-stone-400 font-mono">{n["date"]}</span>'
                f'</div>'
                f'<a href="{n["link"]}" target="_blank" rel="noopener" '
                f'class="text-[14px] font-bold text-stone-900 leading-relaxed mb-2 group-hover:text-amber-900 transition-colors block">'
                f'{n["headline"]}</a>'
                f'<div class="text-[11px] font-sans text-stone-400 uppercase tracking-widest">{n["source"]}</div>'
                f'</div>'
            )
        news_html = "\n".join(news_html_parts)
        html = re.sub(
            r'(<div class="space-y-4 overflow-y-auto flex-grow hide-scrollbar pr-1"[^>]*>).*?(</div>\s*<div class="mt-6 pt-4)',
            rf"\1\n{news_html}\n\2",
            html,
            flags=re.DOTALL,
        )

    # 注入更新時間
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = re.sub(r"最後更新：[\d\-: ]+", f"最後更新：{now_str}", html)

    index_path.write_text(html, encoding="utf-8")
    print(f"  [build] index.html 已更新（{len(all_records)} 筆記錄，{len(news)} 則新聞）")


if __name__ == "__main__":
    print(f"[start] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 開始更新嘉義市城市故障分析儀表板")

    news = run_news()
    complaint_stats = run_opendata()
    council_data = run_council()
    citizen_stats = run_citizen_reports()

    build_dashboard(news, complaint_stats, council_data, citizen_stats)

    print(f"\n[done] 完成 ✓")
