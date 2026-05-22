import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import json
import os

def fetch_chiayi_1999_mock_data():
    """
    核心爬蟲模組：模擬抓取嘉義市公開陳情資訊（西區選戰核心數據基礎）
    """
    print("啟動嘉義市城市故障數據收集器...")
    
    # 測試用初始結構化資料，涵蓋西區重要路段
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
    # 1. 抓取資料源
    raw_data = fetch_chiayi_1999_mock_data()
    
    # 2. 資料清洗與自動分類貼標
    processed_data = []
    for item in raw_data:
        processed_data.append({
            "通報日期": item["date"],
            "發生地點": item["location"],
            "原始描述": item["description"],
            "議題分類": classify_issue(item["description"]),
            "系統紀錄時間": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    # 3. 結構化輸出驗證
    df = pd.DataFrame(processed_data)
    print("\n[驗證成功] 今日清洗完成之結構化數據：")
    print(df.to_string(index=False))
    
    # 4. 存檔為歷史報表基底
    df.to_csv("chiayi_dashboard_latest.csv", index=False, encoding="utf-8-sig")
    print("\n歷史檔案已成功更新至 chiayi_dashboard_latest.csv")

if __name__ == "__main__":
    main()
