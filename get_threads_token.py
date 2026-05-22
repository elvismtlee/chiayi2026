"""
Threads OAuth Token 交換工具
用法：python get_threads_token.py <授權碼>

授權碼從這個 URL 跑完後的 ?code= 參數取得：
https://threads.net/oauth/authorize?client_id=1587054653420345&redirect_uri=https://elvismtlee.github.io/chiayi2026/&scope=threads_basic,threads_read_replies&response_type=code
"""
import sys, requests, json

APP_ID = "1687250975736436"   # Threads 專用 App ID
APP_SECRET = ""  # Threads App Secret（在設定頁「顯示」取得）
REDIRECT_URI = "https://elvismtlee.github.io/chiayi2026/"

if len(sys.argv) < 2:
    print("用法: python get_threads_token.py <授權碼>")
    print()
    print("請先用瀏覽器打開：")
    print(f"https://threads.net/oauth/authorize?client_id={APP_ID}&redirect_uri={REDIRECT_URI}&scope=threads_basic,threads_read_replies&response_type=code")
    sys.exit(1)

code = sys.argv[1].split("#")[0]  # 移除 #_ 尾巴
print(f"授權碼: {code[:20]}...")

# 第一步：短期 token
print("\n[1] 換取短期 token...")
r = requests.post("https://graph.threads.net/oauth/access_token", data={
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "code": code,
    "grant_type": "authorization_code",
    "redirect_uri": REDIRECT_URI,
}, timeout=15)
print(f"  狀態: {r.status_code}")
d = r.json()
if "access_token" not in d:
    print(f"  ❌ 失敗: {json.dumps(d, ensure_ascii=False)}")
    sys.exit(1)

short_token = d["access_token"]
print(f"  ✓ 短期 token: {short_token[:30]}...")

# 第二步：換長效 token（60 天）
print("\n[2] 換取長效 token（60 天）...")
r2 = requests.get("https://graph.threads.net/access_token", params={
    "grant_type": "th_exchange_token",
    "client_id": APP_ID,
    "client_secret": APP_SECRET,
    "access_token": short_token,
}, timeout=15)
d2 = r2.json()
if "access_token" not in d2:
    print(f"  ⚠️ 長效 token 失敗，使用短期 token")
    long_token = short_token
else:
    long_token = d2["access_token"]
    expires = d2.get("expires_in", "?")
    print(f"  ✓ 長效 token（{expires} 秒 ≈ {int(expires)//86400} 天）")

# 第三步：驗證
print("\n[3] 驗證 token...")
r3 = requests.get("https://graph.threads.net/v1.0/me", params={
    "access_token": long_token,
    "fields": "id,username,name"
}, timeout=10)
d3 = r3.json()
if "username" in d3:
    print(f"  ✓ 帳號: @{d3['username']} (ID: {d3['id']})")
else:
    print(f"  結果: {json.dumps(d3, ensure_ascii=False)}")

print("\n" + "="*60)
print("✅ 請把以下 token 加進 GitHub Secrets（名稱：THREADS_USER_TOKEN）：")
print()
print(long_token)
print("="*60)
print("\n注意：此 token 60 天後過期，需重新執行此程式更新。")
