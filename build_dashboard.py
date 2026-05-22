import os
import json
import urllib.request
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timedelta
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def fetch_real_news():
    print("正在攔截嘉義市最新議事與市政新聞...")
    query = urllib.parse.quote("嘉義市 (議員 OR 質詢 OR 議會 OR 市府)")
    url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    news_items = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        xml_data = urllib.request.urlopen(req).read()
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:8]:
            title_full = item.find('title').text
            headline, source = title_full.rsplit(" - ", 1) if " - " in title_full else (title_full, "新聞報導")
            link = item.find('link').text
            pubDate = item.find('pubDate').text
            try:
                dt = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S GMT") + timedelta(hours=8)
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except:
                date_str = pubDate[:16]
            news_items.append({"headline": headline, "source": source, "link": link, "date": date_str, "type": "news"})
    except Exception as e:
        print(f"新聞抓取失敗: {e}")
    return news_items

def fetch_sheet_data():
    print("正在同步 Google Sheet 地方陣地數據...")
    secret_key_json = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not secret_key_json or not sheet_id:
        return []
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(secret_key_json), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sheet_id).worksheet("1999陳情案件表")
    
    records = sheet.get_all_records()
    formatted_records = []
    for i, row in enumerate(records):
        formatted_records.append({
            "id": f"CY-{1000+i}",
            "date": str(row.get("通報日期", "")),
            "location": str(row.get("發生地點", "")),
            "road": str(row.get("發生地點", ""))[:3], # 簡化提取路名
            "description": str(row.get("原始描述", "")),
            "category": str(row.get("議題分類", "")),
            "status": "處理中" # 預設狀態
        })
    return formatted_records[::-1] # 反轉讓最新在上

def build_html(news_data, sheet_data):
    print("正在編譯高質感前端儀表板...")
    # 這裡會動態載入你的資料庫數據，替換掉原本的假資料
    dataset_json = json.dumps(sheet_data, ensure_ascii=False)
    
    news_html = ""
    for n in news_data:
        news_html += f"""
        <a href="{n['link']}" target="_blank" class="block p-5 bg-white border-[0.5px] border-stone-300 shadow-sm hover:bg-stone-50 transition-colors">
            <div class="flex justify-between items-center mb-2">
                <span class="px-2 py-0.5 text-[10px] font-sans font-bold tracking-widest uppercase bg-stone-800 text-white">即時新聞</span>
                <span class="text-[11px] text-stone-400 font-mono">{n['date']}</span>
            </div>
            <h4 class="text-[14px] font-bold text-stone-900 leading-relaxed mb-2 hover:text-amber-900">{n['headline']}</h4>
            <div class="text-[11px] font-sans text-stone-400 tracking-widest">{n['source']}</div>
        </a>"""

    # 讀取原本的 index.html 模板並將 {news_html} 與 {dataset_json} 注入 (為節省篇幅，此處為邏輯示意，實際執行時會自動覆寫檔案)
    with open("index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    
    # 執行字串替換更新
    html_content = html_content.split("const dataset =")[0] + f"const dataset = {dataset_json};\n" + html_content.split("document.addEventListener")[1]
    
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

if __name__ == "__main__":
    news = fetch_real_news()
    sheet_records = fetch_sheet_data()
    build_html(news, sheet_records)
    print("網站建置完畢！")
