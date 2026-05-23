"""
patch_citydata_html.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
為 index.html 加入：
  1. const cityData = {};  注入錨點（scraper.py 用 re.sub 填入）
  2. 多元城市指標整合 section 擴充子區塊：
     - 市府最新公告
     - 氣象觀測資料
     - 地震警報資訊
     - 工程採購動態
     - 疾病監控（登革熱・腸病毒）
     - 公車路線 / YouBike
  3. renderCityData() JavaScript 渲染函數
"""

from pathlib import Path
import re

HTML = Path(__file__).parent / "index.html"
html = HTML.read_text(encoding="utf-8")

# ── 1. 加入 const cityData = {}; 錨點（在 councilStat 之後）────────────────
OLD_ANCHOR = '  const councilStat = {"meetings_count": 14, "question_count": 0, "councilors": 17};'
if 'const cityData' not in html:
    # 用 regex 找現有 councilStat（值可能已被 scraper 替換）
    html = re.sub(
        r'(const councilStat\s*=\s*\{[^;]*\};)',
        r'\1\n  // ── 城市綜合數據（scraper.py 注入）──\n  const cityData = {};',
        html,
        count=1,
    )
    print("[1] const cityData 錨點已加入")
else:
    print("[1] const cityData 已存在，跳過")

# ── 2. 在「多元城市指標整合」section 加入新子區塊 HTML ──────────────────────
OLD_CITY_CLOSE = '  <!-- ── Row 2.5：市民社群聲音 ── -->'

NEW_CITY_SECTIONS = '''
  <!-- ── 城市即時監控（市府公告・氣象・地震・採購・疾病・公車） ── -->
  <div class="card p-6 mb-6" style="border-left:4px solid #0EA5E9;">
    <div class="flex items-start gap-3 mb-5 pb-3 border-b border-slate-100">
      <div class="w-1 min-h-[2rem] rounded bg-sky-500 mt-0.5 flex-shrink-0"></div>
      <div class="flex-1">
        <h2 class="text-xl font-black text-slate-900">📡 城市即時監控</h2>
        <p class="text-sm text-slate-500 mt-0.5">市府公告・氣象觀測・地震資訊・工程採購・疾病監控・大眾運輸，多元資料即時呈現</p>
      </div>
      <span class="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded-lg" id="citydata-updated">資料更新中...</span>
    </div>

    <!-- 上排：市府公告 + 氣象觀測 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">

      <!-- 市府最新公告 -->
      <div class="bg-sky-50 rounded-xl p-4 border border-sky-100">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-lg">📢</span>
          <h3 class="font-black text-sky-800 text-sm">嘉義市政府最新公告</h3>
          <a href="https://www.chiayi.gov.tw" target="_blank" rel="noopener"
             class="ml-auto text-[10px] text-sky-500 hover:underline">官網 →</a>
        </div>
        <div id="city-announcements" class="space-y-2">
          <div class="text-xs text-slate-400 italic">載入中...</div>
        </div>
      </div>

      <!-- 氣象觀測 -->
      <div class="bg-blue-50 rounded-xl p-4 border border-blue-100">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-lg">🌤️</span>
          <h3 class="font-black text-blue-800 text-sm">嘉義氣象觀測</h3>
          <a href="https://www.cwa.gov.tw/V8/C/W/Town/Town.html?TID=1100800" target="_blank" rel="noopener"
             class="ml-auto text-[10px] text-blue-500 hover:underline">氣象局 →</a>
        </div>
        <div id="city-weather" class="space-y-2">
          <div class="text-xs text-slate-400 italic">載入中...</div>
        </div>
        <!-- 靜態備援（API 不可用時顯示） -->
        <div class="mt-3 pt-3 border-t border-blue-100">
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="bg-white rounded-lg p-2 text-center border border-blue-100">
              <div class="text-blue-500 font-bold text-base" id="weather-temp">—</div>
              <div class="text-slate-500">氣溫 °C</div>
            </div>
            <div class="bg-white rounded-lg p-2 text-center border border-blue-100">
              <div class="text-blue-500 font-bold text-base" id="weather-humidity">—</div>
              <div class="text-slate-500">相對濕度 %</div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 中排：地震資訊 + 工程採購 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">

      <!-- 地震資訊 -->
      <div class="bg-orange-50 rounded-xl p-4 border border-orange-100">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-lg">🔔</span>
          <h3 class="font-black text-orange-800 text-sm">最近地震資訊</h3>
          <a href="https://www.cwa.gov.tw/V8/C/E/index.html" target="_blank" rel="noopener"
             class="ml-auto text-[10px] text-orange-500 hover:underline">氣象局 →</a>
        </div>
        <div id="city-earthquake" class="space-y-2">
          <div class="text-xs text-slate-400 italic">載入中...</div>
        </div>
      </div>

      <!-- 工程採購 -->
      <div class="bg-amber-50 rounded-xl p-4 border border-amber-100">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-lg">🏗️</span>
          <h3 class="font-black text-amber-800 text-sm">嘉義市工程採購動態</h3>
          <a href="https://web.pcc.gov.tw/tps/prkms/tender/common/bulletinBoard/readBulletinBoard?typeID=2"
             target="_blank" rel="noopener" class="ml-auto text-[10px] text-amber-500 hover:underline">採購網 →</a>
        </div>
        <div id="city-procurement" class="space-y-2">
          <div class="text-xs text-slate-400 italic">載入中...</div>
        </div>
      </div>
    </div>

    <!-- 下排：疾病監控 + 大眾運輸 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-5 mb-5">

      <!-- 疾病監控 -->
      <div class="bg-red-50 rounded-xl p-4 border border-red-100">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-lg">🦟</span>
          <h3 class="font-black text-red-800 text-sm">疾病監控（登革熱・腸病毒）</h3>
          <a href="https://www.cdc.gov.tw/Category/Page/vSvhd8jgkSJGzGLIwzFLJw" target="_blank" rel="noopener"
             class="ml-auto text-[10px] text-red-500 hover:underline">疾管署 →</a>
        </div>
        <div id="city-disease" class="space-y-2">
          <div class="text-xs text-slate-400 italic">載入中...</div>
        </div>
        <div class="mt-3 pt-3 border-t border-red-100 grid grid-cols-2 gap-3 text-xs">
          <div class="text-center bg-white rounded-lg p-2 border border-red-100">
            <div class="text-red-600 font-black text-lg" id="dengue-count">—</div>
            <div class="text-slate-500">登革熱（嘉義）</div>
          </div>
          <div class="text-center bg-white rounded-lg p-2 border border-red-100">
            <div class="text-orange-500 font-black text-lg" id="entero-count">—</div>
            <div class="text-slate-500">腸病毒（嘉義）</div>
          </div>
        </div>
      </div>

      <!-- 大眾運輸 -->
      <div class="bg-green-50 rounded-xl p-4 border border-green-100">
        <div class="flex items-center gap-2 mb-3">
          <span class="text-lg">🚌</span>
          <h3 class="font-black text-green-800 text-sm">大眾運輸覆蓋率</h3>
          <a href="https://oba.motc.gov.tw/" target="_blank" rel="noopener"
             class="ml-auto text-[10px] text-green-500 hover:underline">公路局 →</a>
        </div>
        <!-- 統計 KPI -->
        <div class="grid grid-cols-3 gap-2 mb-3">
          <div class="bg-white rounded-lg p-2 text-center border border-green-100">
            <div class="text-green-700 font-black text-lg" id="bus-count">—</div>
            <div class="text-[10px] text-slate-500">公車路線</div>
          </div>
          <div class="bg-white rounded-lg p-2 text-center border border-green-100">
            <div class="text-green-700 font-black text-lg" id="youbike-count">—</div>
            <div class="text-[10px] text-slate-500">YouBike 站</div>
          </div>
          <div class="bg-white rounded-lg p-2 text-center border border-green-100">
            <div class="text-green-700 font-black text-lg" id="youbike-bikes">—</div>
            <div class="text-[10px] text-slate-500">可借車輛</div>
          </div>
        </div>
        <div id="city-bus" class="space-y-1.5">
          <div class="text-xs text-slate-400 italic">載入中...</div>
        </div>
      </div>
    </div>

    <!-- 底部：水位監控（若有資料才顯示） -->
    <div id="city-water-wrap" class="hidden bg-slate-50 rounded-xl p-4 border border-slate-200">
      <div class="flex items-center gap-2 mb-3">
        <span class="text-lg">🌊</span>
        <h3 class="font-black text-slate-700 text-sm">河川水位即時監測</h3>
        <a href="https://www.wrap.gov.tw/" target="_blank" rel="noopener"
           class="ml-auto text-[10px] text-slate-500 hover:underline">水利署 →</a>
      </div>
      <div id="city-water" class="grid grid-cols-2 md:grid-cols-3 gap-2"></div>
    </div>

    <!-- 政策呼籲 -->
    <div class="mt-5 bg-sky-700 text-white rounded-xl p-4">
      <div class="flex items-start gap-3">
        <span class="text-2xl">💡</span>
        <div>
          <div class="font-black text-sm mb-1">李明燦擬參選人的城市數位治理主張</div>
          <ul class="text-xs text-sky-100 space-y-0.5 list-disc list-inside">
            <li>建立嘉義市統一「城市儀表板」，整合12+數據來源即時監控</li>
            <li>AQI超標自動推播，疾病預警早於官方通知 24 小時</li>
            <li>工程採購資訊全公開，追蹤進度到最後一根螺絲</li>
            <li>大眾運輸覆蓋率列入市政 KPI，每季向市民報告</li>
          </ul>
        </div>
      </div>
    </div>
  </div>

'''

if '<!-- ── 城市即時監控' not in html:
    html = html.replace(OLD_CITY_CLOSE, NEW_CITY_SECTIONS + OLD_CITY_CLOSE)
    print("[2] 城市即時監控 section 已加入")
else:
    print("[2] 城市即時監控 section 已存在，跳過")

# ── 3. 加入 renderCityData() JavaScript ──────────────────────────────────────
OLD_AQI_JS = '  // ── AQI 即時空氣品質（環境部開放API）──\n  async function fetchAQI() {'

NEW_CITYDATA_JS = '''  // ── 城市綜合數據渲染（cityData 由 scraper.py 注入）──
  function renderCityData() {
    if (!window.cityData || !cityData.updated_at) return;

    // 更新時間
    const updStr = cityData.updated_at.replace('T', ' ').slice(0, 16);
    const el = document.getElementById('citydata-updated');
    if (el) el.textContent = `資料更新：${updStr}`;

    // ── 市府公告 ──
    const annEl = document.getElementById('city-announcements');
    if (annEl) {
      const anns = cityData.announcements || [];
      if (anns.length) {
        annEl.innerHTML = anns.slice(0, 6).map(a => `
          <div class="flex items-start gap-1.5">
            <span class="text-sky-400 mt-0.5 flex-shrink-0">▶</span>
            <div class="flex-1 min-w-0">
              <a href="${a.link || '#'}" target="_blank" rel="noopener"
                 class="text-xs font-bold text-slate-800 hover:text-sky-600 line-clamp-2 block leading-snug">${a.title}</a>
              <span class="text-[10px] text-slate-400">${(a.date || '').slice(0, 10)}</span>
            </div>
          </div>`).join('');
      } else {
        annEl.innerHTML = '<p class="text-xs text-slate-400">暫無公告資料（可能需要 scraper 重新執行）</p>';
      }
    }

    // ── 氣象觀測 ──
    const weatherEl = document.getElementById('city-weather');
    const obs = (cityData.weather || []);
    if (weatherEl && obs.length) {
      const w = obs[0];
      document.getElementById('weather-temp')?.style && (document.getElementById('weather-temp').textContent = w.temp || '—');
      document.getElementById('weather-humidity')?.style && (document.getElementById('weather-humidity').textContent = w.humidity || '—');
      weatherEl.innerHTML = obs.slice(0, 2).map(w => `
        <div class="flex flex-wrap gap-x-3 gap-y-1 text-xs bg-white rounded-lg p-2 border border-blue-100">
          <span class="font-bold text-blue-700">📍 ${w.station}</span>
          ${w.temp ? `<span>🌡️ <b>${w.temp}</b>°C</span>` : ''}
          ${w.humidity ? `<span>💧 <b>${w.humidity}</b>%</span>` : ''}
          ${w.rainfall !== '' && w.rainfall !== undefined ? `<span>🌧️ 雨量 <b>${w.rainfall}</b>mm</span>` : ''}
          ${w.wind_speed ? `<span>💨 <b>${w.wind_speed}</b>m/s</span>` : ''}
          <span class="text-slate-400 text-[10px] w-full">${(w.time || '').slice(0, 16)}</span>
        </div>`).join('');
    } else if (weatherEl) {
      weatherEl.innerHTML = '<p class="text-xs text-slate-400 italic">氣象觀測 API 暫無資料</p>';
    }

    // ── 地震資訊 ──
    const eqEl = document.getElementById('city-earthquake');
    if (eqEl) {
      const eqs = cityData.earthquake || [];
      if (eqs.length) {
        eqEl.innerHTML = eqs.slice(0, 4).map(eq => `
          <div class="flex items-start gap-1.5 text-xs">
            <span class="text-orange-400 font-black flex-shrink-0 mt-0.5">⚡</span>
            <div class="flex-1 min-w-0">
              <a href="${eq.link || '#'}" target="_blank" rel="noopener"
                 class="font-bold text-slate-800 hover:text-orange-600 block line-clamp-1">${eq.title}</a>
              ${eq.desc ? `<span class="text-[10px] text-slate-500 line-clamp-1">${eq.desc}</span>` : ''}
              <span class="text-[10px] text-slate-400">${(eq.date || '').slice(0, 16)}</span>
            </div>
          </div>`).join('');
      } else {
        eqEl.innerHTML = '<p class="text-xs text-slate-400 italic">近期無顯著地震資料</p>';
      }
    }

    // ── 工程採購 ──
    const procEl = document.getElementById('city-procurement');
    if (procEl) {
      const procs = cityData.procurement || [];
      if (procs.length) {
        procEl.innerHTML = procs.slice(0, 5).map(p => `
          <div class="flex items-start gap-1.5 text-xs">
            <span class="text-amber-500 flex-shrink-0 mt-0.5">🔨</span>
            <div class="flex-1 min-w-0">
              <a href="${p.link || '#'}" target="_blank" rel="noopener"
                 class="font-bold text-slate-800 hover:text-amber-600 block line-clamp-2 leading-snug">${p.title}</a>
              <span class="text-[10px] text-slate-400">${p.org || ''} · ${(p.date || '').slice(0, 10)}</span>
            </div>
          </div>`).join('');
      } else {
        procEl.innerHTML = '<p class="text-xs text-slate-400 italic">採購公告資料更新中</p>';
      }
    }

    // ── 疾病監控 ──
    const diseaseEl = document.getElementById('city-disease');
    if (diseaseEl) {
      const dis = cityData.disease || {};
      const dengue = dis.dengue || [];
      const entero = dis.enterovirus || [];
      // 計算今年總數
      const yr = String(new Date().getFullYear());
      const dengueCnt = dengue.filter(r => String(r['年度'] || r['year'] || '').includes(yr))
                              .reduce((s,r) => s + parseInt(r['確定病例數'] || r['cases'] || 0), 0);
      const enteroCnt = entero.filter(r => String(r['年度'] || r['year'] || '').includes(yr))
                               .reduce((s,r) => s + parseInt(r['確定病例數'] || r['cases'] || 0), 0);
      document.getElementById('dengue-count').textContent = dengueCnt > 0 ? `${dengueCnt}例` : '0例';
      document.getElementById('entero-count').textContent = enteroCnt > 0 ? `${enteroCnt}例` : '0例';
      if (dengue.length || entero.length) {
        diseaseEl.innerHTML = `
          <div class="text-xs text-slate-700 space-y-1">
            ${dengue.slice(0,2).map(r => `<div class="flex justify-between bg-white rounded p-1.5 border border-red-100">
              <span>登革熱 ${r['年份'] || r['年度'] || ''}</span>
              <span class="font-bold text-red-600">${r['確定病例數'] || r['cases'] || 0} 例</span>
            </div>`).join('')}
            ${!dengue.length ? '<p class="text-slate-400 italic text-[10px]">登革熱資料更新中</p>' : ''}
          </div>`;
      } else {
        diseaseEl.innerHTML = '<p class="text-xs text-slate-400 italic">疾病監控資料 API 更新中</p>';
      }
    }

    // ── 大眾運輸 ──
    const busEl = document.getElementById('city-bus');
    const buses = cityData.bus || [];
    const bikes = cityData.youbike || [];
    if (document.getElementById('bus-count')) document.getElementById('bus-count').textContent = buses.length || '—';
    if (document.getElementById('youbike-count')) document.getElementById('youbike-count').textContent = bikes.length || '—';
    if (document.getElementById('youbike-bikes')) {
      const avail = bikes.reduce((s, b) => s + (b.available || 0), 0);
      document.getElementById('youbike-bikes').textContent = avail || '—';
    }
    if (busEl && buses.length) {
      busEl.innerHTML = buses.slice(0, 8).map(b => `
        <div class="flex items-center gap-1.5 text-xs bg-white rounded px-2 py-1 border border-green-100">
          <span class="text-green-600 font-black text-[11px] min-w-[2rem]">${b.id || ''}</span>
          <span class="font-bold text-slate-700 flex-1 truncate">${b.name || ''}</span>
          <span class="text-slate-400 text-[10px] truncate">${b.from || ''} → ${b.to || ''}</span>
        </div>`).join('');
    } else if (busEl) {
      busEl.innerHTML = '<p class="text-xs text-slate-400 italic">公車路線資料更新中</p>';
    }

    // ── 水位監控 ──
    const waterWrap = document.getElementById('city-water-wrap');
    const waterEl = document.getElementById('city-water');
    const waters = cityData.water || [];
    if (waterWrap && waters.length) {
      waterWrap.classList.remove('hidden');
      waterEl.innerHTML = waters.map(w => `
        <div class="bg-white rounded-lg p-2 border border-slate-200 text-xs text-center">
          <div class="font-bold text-slate-700 truncate">${w.station}</div>
          <div class="text-blue-600 font-black">${w.level}m</div>
          <div class="text-slate-400 text-[10px]">${w.river || ''}</div>
        </div>`).join('');
    }
  }

  // ── AQI 即時空氣品質（環境部開放API）──
  async function fetchAQI() {'''

if 'renderCityData' not in html:
    html = html.replace(
        OLD_AQI_JS,
        NEW_CITYDATA_JS
    )
    print("[3] renderCityData() JavaScript 已加入")
else:
    print("[3] renderCityData 已存在，跳過")

# ── 4. 在 DOMContentLoaded 呼叫 renderCityData() ────────────────────────────
OLD_DOM = "  document.addEventListener('DOMContentLoaded', () => {"
if 'renderCityData()' not in html:
    html = html.replace(
        OLD_DOM,
        "  document.addEventListener('DOMContentLoaded', () => {\n    renderCityData();"
    )
    print("[4] DOMContentLoaded 加入 renderCityData() 呼叫")
else:
    print("[4] renderCityData() 已在 DOMContentLoaded 中，跳過")

HTML.write_text(html, encoding="utf-8")
print(f"\n[done] index.html 已更新（{len(html):,} chars）")
