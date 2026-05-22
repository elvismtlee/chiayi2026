"""快速測試 Meta API 連線 — 執行前先設定環境變數"""
import os, sys, io, requests, json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

app_id = os.environ.get("META_APP_ID", "")
app_secret = os.environ.get("META_APP_SECRET", "")

if not app_id or not app_secret:
    print("❌ 請先設定 META_APP_ID 和 META_APP_SECRET 環境變數")
    sys.exit(1)

token = f"{app_id}|{app_secret}"
print(f"✓ App ID: {app_id[:6]}... (長度:{len(app_id)})")

# 測試 1：驗證 App Token 有效
print("\n[測試1] 驗證 App Token...")
r = requests.get("https://graph.facebook.com/v19.0/me",
                 params={"access_token": token}, timeout=10)
print(f"  狀態: {r.status_code}")
d = r.json()
if "id" in d:
    print(f"  ✓ Token 有效，App ID: {d.get('id')}")
else:
    print(f"  回應: {d}")

# 測試 2：Threads 搜尋
print("\n[測試2] Threads 搜尋 API...")
r2 = requests.get("https://graph.threads.net/v1.0/threads/search",
                  params={"access_token": token, "q": "嘉義市", "limit": 3,
                          "fields": "id,text,username,timestamp"}, timeout=10)
print(f"  狀態: {r2.status_code}")
d2 = r2.json()
if "data" in d2:
    print(f"  ✓ 找到 {len(d2['data'])} 篇")
    for p in d2["data"][:2]:
        print(f"    @{p.get('username','')} : {str(p.get('text',''))[:50]}")
else:
    print(f"  回應: {json.dumps(d2, ensure_ascii=False)[:200]}")

# 測試 3：Facebook 公開頁面貼文
print("\n[測試3] Facebook 嘉義市政府粉絲頁...")
r3 = requests.get("https://graph.facebook.com/v19.0/chiayicitygov/posts",
                  params={"access_token": token, "limit": 3,
                          "fields": "id,message,created_time"}, timeout=10)
print(f"  狀態: {r3.status_code}")
d3 = r3.json()
if "data" in d3:
    print(f"  ✓ 找到 {len(d3['data'])} 篇")
    for p in d3["data"][:2]:
        msg = str(p.get("message", ""))[:50]
        print(f"    {p.get('created_time','')[:10]} : {msg}")
else:
    print(f"  回應: {json.dumps(d3, ensure_ascii=False)[:200]}")

print("\n完成。把上面的結果告訴 Claude。")
