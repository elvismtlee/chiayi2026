import os
import json
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def fetch_real_news():
    print("啟動新聞爬蟲：抓取嘉義市最新市政與議事新聞...")
    query = urllib.parse.quote("嘉義市 (議員 OR 質詢 OR 西區)")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    news_list = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        xml_data = urllib.request.urlopen(req).read()
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:8]:
            title = item.find('title').text
            headline, source = title.rsplit(" - ", 1) if " - " in title else (title, "新聞")
            news_list.append({
                "headline": headline,
                "source": source,
                "link": item.find('link').text,
                "date": item.find('pubDate').text[5:16]
            })
    except Exception as e:
        print("新聞爬蟲失敗:", e)
    return news_list

def fetch_citizen_reports():
    print("啟動資料庫爬蟲：同步 1999 通報數據...")
    secret = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not secret or not sheet_id:
        print("缺乏保險箱憑證，無法抓取 Google Sheet")
        return []
    
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(secret), scope)
        sheet = gspread.authorize(creds).open_by_key(sheet_id).worksheet("1999陳情案件表")
        records = sheet.get_all_records()
        data = []
        for i, r in enumerate(records):
            data.append({
                "id": f"CY-LIVE-{1000+i}",
                "date": str(r.get("通報日期", "")),
                "location": str(r.get("發生地點", "")),
                "road": str(r.get("發生地點", ""))[:3],
                "description": str(r.get("原始描述", "")),
                "category": str(r.get("議題分類", "")),
                "status": "處理中"
            })
        return data[::-1]
    except Exception as e:
        print("Sheet 爬蟲失敗:", e)
        return []

def update_dashboard():
    news_data = fetch_real_news()
    sheet_data = fetch_citizen_reports()
    
    print("啟動可視化統計引擎：更新儀表板圖表與數據...")
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    # 1. 精準替換 Chart.js 統計圖表所需的 dataset (JSON 格式)
    json_str = json.dumps(sheet_data, ensure_ascii=False)
    html = re.sub(r"const dataset = \[.*?\];", f"const dataset = {json_str};", html, flags=re.DOTALL)

    # 2. 動態生成並替換右側即時新聞的 HTML 區塊
    if news_data:
        news_html = ""
        for n in news_data:
            news_html += f'''<div class="block p-5 bg-white border-[0.5px] border-[#E2DFD8] shadow-sm hover:bg-stone-50 transition-colors group"><div class="flex justify-between items-center mb-3"><span class="px-2 py-0.5 text-[10px] font-sans font-bold tracking-widest uppercase bg-stone-800 text-white">即時新聞</span><span class="text-[11px] text-stone-400 font-mono">{n['date']}</span></div><a href="{n['link']}" target="_blank" class="text-[14px] font-bold text-stone-900 leading-relaxed mb-2 group-hover:text-amber-900 transition-colors block">{n['headline']}</a><div class="text-[11px] font-sans text-stone-400 uppercase tracking-widest">{n['source']}</div></div>'''
        
        # 利用正則表達式鎖定輿情面板區塊進行替換
        html = re.sub(
            r'(<div class="space-y-4 overflow-y-auto flex-grow hide-scrollbar pr-1" style="max-height: 600px;">).*?(</div>\s*<div class="mt-6 pt-4)',
            rf'\1\n{news_html}\n\2',
            html,
            flags=re.DOTALL
        )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ 數據爬取與可視化更新大功告成！")

if __name__ == "__main__":
    update_dashboard()
