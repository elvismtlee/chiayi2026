import os
import json
from datetime import datetime
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def fetch_chiayi_1999_mock_data():
    """
    核心爬蟲模組：模擬抓取嘉義市公開陳情資訊
    """
    print("啟動嘉義市城市故障數據收集器...")
    mock_data = [
        {"date": "2026-05-20", "location": "嘉義市西區中山路與文化路口", "description": "路燈不亮，影響夜間行車安全"},
        {"date": "2026-05-21", "location": "嘉義市東區林森東路", "description": "水溝嚴重堵塞散發惡臭"},
        {"date": "2026-05-22", "location": "嘉義市西區中興路", "description": "違規停車嚴重，霸占人行道與騎樓"}
    ]
    return mock_data

def classify_issue(description):
    """
    議題自動分類器：精準標籤化市民陳情痛點
    """
    issue_dict = {
        "路燈照明": ["路燈", "太暗", "不亮", "照明"],
        "水溝排水": ["水溝", "淹水", "惡臭", "排水", "清淤"],
        "停車亂象": ["違規停車", "違停", "佔用", "併排", "車位"],
        "道路工程": ["坑洞", "路面", "柏油", "凹陷"]
    }
    for category, keywords in issue_dict.items():
        if any(keyword in description for keyword in keywords):
            return category
    return "其他"

def main():
    # 1. 讀取 GitHub Secrets 保險箱裡的憑證
    secret_key_json = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    
    if not secret_key_json or not sheet_id:
        print("[錯誤] 找不到 GitHub Secrets 設定，請檢查保險箱密鑰。")
        return

    # 2. 抓取與清洗資料
    raw_data = fetch_chiayi_1999_mock_data()
    processed_data = []
    for item in raw_data:
        processed_data.append([
            item["date"],
            item["location"],
            item["description"],
            classify_issue(item["description"]),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])

    # 3. 透過 API 連線至 Google Sheet
    print("正在連線至 Google 試算表...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(secret_key_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    # 打開指定試算表與工作表
    sheet = client.open_by_key(sheet_id).worksheet("1999陳情案件表")
    
    # 4. 寫入資料（若工作表是完全空的，先寫入欄位名稱）
    existing_records = sheet.get_all_values()
    if len(existing_records) == 0:
        headers = ["通報日期", "發生地點", "原始描述", "議題分類", "系統紀錄時間"]
        sheet.append_row(headers)
        print("已建立欄位標頭。")
    
    # 批次寫入新資料
    for row in processed_data:
        sheet.append_row(row)
        
    print(f"[成功] 已將 {len(processed_data)} 筆最新的故障數據自動灌入 Google Sheet！")

if __name__ == "__main__":
    main()
