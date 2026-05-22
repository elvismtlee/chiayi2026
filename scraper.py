import os
import json
import random
from datetime import datetime, timedelta
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def generate_chiayi_west_district_data(num_records=200):
    print("啟動嘉義市西區真實情境數據模擬引擎...")
    
    # 鎖定西區重點路段
    locations = ["中山路", "文化路", "中興路", "友愛路", "北港路", "世賢路二段", "民族路", "民生北路", "新民路", "垂楊路"]
    issue_types = {
        "道路工程": ["路面柏油破損，出現坑洞", "道路施工未設警告標誌", "人孔蓋周邊凹陷", "道路標線斑駁不清"],
        "停車亂象": ["紅線違規停車嚴重", "騎樓被整排機車佔用", "併排停車導致交通阻塞", "廢棄車輛長期霸占停車格"],
        "路燈照明": ["路燈整排不亮，影響夜間安全", "路燈閃爍不定", "巷弄內照明死角太多"],
        "水溝排水": ["水溝蓋損壞或遺失", "水溝內積滿垃圾與淤泥，散發惡臭", "大雨後水溝排水不及導致積水"],
        "環境衛生": ["空地雜草叢生，恐孳生登革熱", "路邊被惡意棄置大型垃圾", "流浪狗群聚造成環境髒亂"],
        "噪音管制": ["深夜改裝車呼嘯而過", "周邊工地清晨施工噪音擾人", "營業場所擴音器音量過大"]
    }
    
    mock_data = []
    end_date = datetime.now()
    
    for _ in range(num_records):
        # 隨機產生過去半年的日期
        random_days = random.randint(0, 180)
        report_date = (end_date - timedelta(days=random_days)).strftime("%Y-%m-%d")
        
        road = random.choice(locations)
        exact_location = f"嘉義市西區{road}{random.randint(10, 300)}號周邊"
        
        category = random.choice(list(issue_types.keys()))
        description = random.choice(issue_types[category])
        
        mock_data.append([
            report_date,
            exact_location,
            description,
            category,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
        
    # 依照日期由新到舊排序
    mock_data.sort(key=lambda x: x[0], reverse=True)
    return mock_data

def main():
    secret_key_json = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    
    if not secret_key_json or not sheet_id:
        print("[錯誤] 找不到 GitHub Secrets。")
        return

    processed_data = generate_chiayi_west_district_data(200)

    print("正在連線至 Google 試算表...")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = json.loads(secret_key_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(sheet_id).worksheet("1999陳情案件表")
    
    # 霸氣重置：清空現有測試資料並寫入 200 筆最新數據
    sheet.clear()
    headers = ["通報日期", "發生地點", "原始描述", "議題分類", "系統紀錄時間"]
    sheet.append_row(headers)
    
    # 批次高速寫入
    sheet.update(f"A2:E{len(processed_data)+1}", processed_data)
    print(f"[成功] 已將 {len(processed_data)} 筆西區在地化數據自動灌入 Google Sheet！")

if __name__ == "__main__":
    main()
