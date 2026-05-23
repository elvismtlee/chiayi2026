"""Major page enrichment patch:
1. New section: 交通安全12年分析 (after Row 1)
2. New section: 橋梁設施 + 停車場明細 (before social section)
3. New section: 噪音監測 + 水域安全 (before Row 4)
4. Table: add category filter tabs
5. KPI header: add death/injury counters
6. More JS functions for dynamic rendering
"""
path = 'C:/Users/elvis/Downloads/elvis-agent/chiayi2026/index.html'
html = open(path, encoding='utf-8').read()
original = html

# ══════════════════════════════════════════════════════════════════════════════
# 1. NEW SECTION: 交通安全12年全面分析  (insert after Row 1 grid closes)
# ══════════════════════════════════════════════════════════════════════════════
TRAFFIC_SECTION = '''
  <!-- ── 交通安全12年全面分析 ─────────────────────────────────────────────── -->
  <div class="card p-6 mb-6">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-lg font-black text-slate-900">🚨 交通安全12年全面分析</h2>
        <p class="text-sm text-slate-500 mt-0.5">嘉義市道路交通事故 2014–2025，來源：政府開放資料（主計處）</p>
      </div>
      <span class="text-xs font-bold bg-red-100 text-red-600 px-3 py-1 rounded-full">高優先議題</span>
    </div>
    <!-- KPI 磚 -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
      <div class="bg-red-50 border border-red-100 rounded-xl p-3 text-center">
        <div class="text-xs font-bold text-red-400 uppercase tracking-wide mb-1">12年總事故</div>
        <div class="text-2xl font-black text-red-600" id="acc-total">—</div>
        <div class="text-[10px] text-red-300 mt-0.5">件</div>
      </div>
      <div class="bg-orange-50 border border-orange-100 rounded-xl p-3 text-center">
        <div class="text-xs font-bold text-orange-400 uppercase tracking-wide mb-1">累計死亡</div>
        <div class="text-2xl font-black text-orange-600" id="acc-dead">—</div>
        <div class="text-[10px] text-orange-300 mt-0.5">人</div>
      </div>
      <div class="bg-amber-50 border border-amber-100 rounded-xl p-3 text-center">
        <div class="text-xs font-bold text-amber-500 uppercase tracking-wide mb-1">累計受傷</div>
        <div class="text-2xl font-black text-amber-600" id="acc-inj">—</div>
        <div class="text-[10px] text-amber-300 mt-0.5">人</div>
      </div>
      <div class="bg-rose-50 border border-rose-100 rounded-xl p-3 text-center">
        <div class="text-xs font-bold text-rose-400 uppercase tracking-wide mb-1">平均每月事故</div>
        <div class="text-2xl font-black text-rose-600" id="acc-monthly">—</div>
        <div class="text-[10px] text-rose-300 mt-0.5">件/月</div>
      </div>
    </div>
    <!-- 年度趨勢圖 -->
    <div class="mb-4">
      <p class="text-xs font-bold text-slate-500 mb-2">歷年事故件數（2014–2025）</p>
      <div style="height:160px;"><canvas id="chartAccYear"></canvas></div>
    </div>
    <!-- 月份分布 + 洞察 -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <div>
        <p class="text-xs font-bold text-slate-500 mb-2">月份風險分布</p>
        <div style="height:120px;"><canvas id="chartAccMonth"></canvas></div>
      </div>
      <div id="acc-insight" class="text-xs text-slate-600 space-y-1.5 flex flex-col justify-center">
        <div class="text-slate-400">計算中...</div>
      </div>
    </div>
  </div>

'''

# Insert after the Row 1 closing </div> (before Row 2)
target_row2 = '  <!-- ── Row 2：年度趨勢 + 即時新聞 ── -->'
if target_row2 in html:
    html = html.replace(target_row2, TRAFFIC_SECTION + target_row2, 1)
    print('  OK 交通安全12年分析 section inserted')
else:
    print('  FAIL Row 2 marker not found')


# ══════════════════════════════════════════════════════════════════════════════
# 2. NEW SECTION: 橋梁設施 + 停車場明細  (after social feed, before Row 3)
# ══════════════════════════════════════════════════════════════════════════════
INFRA_DETAIL_SECTION = '''
  <!-- ── 橋梁設施 + 停車場 + 噪音 明細 ─────────────────────────────────────── -->
  <div class="grid grid-cols-1 lg:grid-cols-5 gap-6 mb-6">

    <!-- 橋梁設施 (3/5) -->
    <div class="lg:col-span-3 card p-6">
      <div class="flex items-center justify-between mb-4">
        <div>
          <h2 class="text-base font-black text-slate-900">🌉 橋梁設施盤點</h2>
          <p class="text-sm text-slate-500 mt-0.5">嘉義市 172 座橋梁，依道路等級分類管理</p>
        </div>
        <div class="flex gap-1.5" id="bridge-legend"></div>
      </div>
      <!-- 道路等級統計列 -->
      <div class="flex gap-2 flex-wrap mb-3" id="bridge-class-stats"></div>
      <!-- 橋梁列表 (滾動) -->
      <div class="overflow-y-auto space-y-1" style="max-height:220px;" id="bridge-list-detail">
        <div class="text-sm text-slate-400 text-center py-6">橋梁資料載入中...</div>
      </div>
    </div>

    <!-- 停車場 + 噪音 (2/5) -->
    <div class="lg:col-span-2 flex flex-col gap-4">
      <!-- 公有停車場 -->
      <div class="card p-5 flex-1">
        <h2 class="text-base font-black text-slate-900 mb-3">🅿️ 公有停車場清單</h2>
        <div class="overflow-y-auto space-y-1.5" style="max-height:140px;" id="parking-list-detail">
          <div class="text-sm text-slate-400 text-center py-4">停車場資料載入中...</div>
        </div>
        <div class="mt-2 pt-2 border-t border-slate-100 flex justify-between text-xs">
          <span class="text-slate-400">停車場總計</span>
          <span class="font-black text-slate-700" id="parking-total-cap">— 格</span>
        </div>
      </div>
      <!-- 噪音監測 -->
      <div class="card p-5 flex-1">
        <h2 class="text-base font-black text-slate-900 mb-3">🔊 噪音監測站</h2>
        <div class="space-y-1.5" id="noise-list-detail">
          <div class="text-sm text-slate-400 text-center py-4">監測資料載入中...</div>
        </div>
      </div>
    </div>

  </div>

'''

target_row3 = '  <!-- ── Row 3：西區各里人口分析 ── -->'
if target_row3 in html:
    html = html.replace(target_row3, INFRA_DETAIL_SECTION + target_row3, 1)
    print('  OK 橋梁+停車場+噪音 section inserted')
else:
    print('  FAIL Row 3 marker not found')


# ══════════════════════════════════════════════════════════════════════════════
# 3. NEW SECTION: 水域安全 + 議員質詢  (after Row 3.5 cards, before Row 4)
# ══════════════════════════════════════════════════════════════════════════════
SAFETY_COUNCIL_SECTION = '''
  <!-- ── 水域安全 + 議會資料 ──────────────────────────────────────────────── -->
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">

    <!-- 溺水安全統計 -->
    <div class="card p-6">
      <h2 class="text-base font-black text-slate-900 mb-3">🌊 水域溺水安全</h2>
      <div class="text-4xl font-black text-blue-600 mb-1" id="drowning-total">—</div>
      <p class="text-xs text-slate-400 mb-3">件歷年溺水案件</p>
      <div class="space-y-1.5" id="drowning-type-list"></div>
      <p class="text-xs text-blue-600 font-bold mt-3">⚠️ 水域安全需全面提升，溺水高峰在夏季</p>
    </div>

    <!-- 議員質詢記錄 -->
    <div class="card p-6 lg:col-span-2">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-black text-slate-900">🏛️ 嘉義市議會會議紀錄</h2>
        <a href="https://www.cycc.gov.tw" target="_blank" rel="noopener"
           class="text-xs text-blue-600 font-bold hover:underline">→ 議會官網</a>
      </div>
      <div class="grid grid-cols-3 gap-2 mb-3">
        <div class="bg-purple-50 rounded-lg p-2 text-center">
          <div class="text-xs text-purple-400 font-bold">會議場次</div>
          <div class="text-xl font-black text-purple-700" id="council-meetings">—</div>
        </div>
        <div class="bg-indigo-50 rounded-lg p-2 text-center">
          <div class="text-xs text-indigo-400 font-bold">質詢記錄</div>
          <div class="text-xl font-black text-indigo-700" id="council-questions">—</div>
        </div>
        <div class="bg-slate-100 rounded-lg p-2 text-center">
          <div class="text-xs text-slate-400 font-bold">現任議員</div>
          <div class="text-xl font-black text-slate-700" id="council-members">17</div>
        </div>
      </div>
      <div class="overflow-y-auto space-y-1.5" style="max-height:130px;" id="council-meeting-list">
        <div class="text-sm text-slate-400 text-center py-4">議會資料載入中...</div>
      </div>
      <div class="mt-3 pt-3 border-t border-slate-100">
        <p class="text-xs text-slate-400 mb-1.5 font-bold">議員名單（第 11 屆）</p>
        <div class="flex flex-wrap gap-1" id="councilor-list"></div>
      </div>
    </div>

  </div>

'''

target_row4 = '  <!-- ── Row 4：詳細記錄表格 ── -->'
if target_row4 in html:
    html = html.replace(target_row4, SAFETY_COUNCIL_SECTION + target_row4, 1)
    print('  OK 水域安全+議會 section inserted')
else:
    print('  FAIL Row 4 marker not found')


# ══════════════════════════════════════════════════════════════════════════════
# 4. TABLE: Add category filter tabs above table
# ══════════════════════════════════════════════════════════════════════════════
old_table_header = '''    <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
      <div>
        <h2 class="text-base font-black text-slate-900">嘉義市城市問題原始紀錄</h2>
        <p class="text-xs text-slate-400 mt-0.5">交通事故・道路施工・路燈・橋梁・停車場，每 6 小時自動更新</p>
      </div>
      <button onclick="toggleTable()" id="toggle-btn" class="text-xs text-slate-500 border border-slate-200 rounded-lg px-3 py-1.5 hover:bg-slate-50">
        展開全部
      </button>
    </div>'''

new_table_header = '''    <div class="px-6 py-4 border-b border-slate-100">
      <div class="flex items-center justify-between mb-3">
        <div>
          <h2 class="text-base font-black text-slate-900">嘉義市城市問題原始紀錄</h2>
          <p class="text-xs text-slate-400 mt-0.5">交通事故・道路施工・路燈・橋梁・停車場，每 6 小時自動更新</p>
        </div>
        <button onclick="toggleTable()" id="toggle-btn" class="text-xs text-slate-500 border border-slate-200 rounded-lg px-3 py-1.5 hover:bg-slate-50">
          展開全部
        </button>
      </div>
      <!-- 類別篩選 tabs -->
      <div class="flex flex-wrap gap-1.5" id="table-filter-tabs">
        <button onclick="filterTable('')"
          class="filter-tab text-xs px-3 py-1 rounded-full font-bold bg-slate-900 text-white transition-colors" data-cat="">
          全部
        </button>
        <button onclick="filterTable('交通停車')"
          class="filter-tab text-xs px-3 py-1 rounded-full font-bold bg-slate-100 text-slate-600 hover:bg-orange-100 transition-colors" data-cat="交通停車">
          🚗 交通停車
        </button>
        <button onclick="filterTable('道路路平')"
          class="filter-tab text-xs px-3 py-1 rounded-full font-bold bg-slate-100 text-slate-600 hover:bg-orange-100 transition-colors" data-cat="道路路平">
          🛣️ 道路路平
        </button>
        <button onclick="filterTable('公共安全')"
          class="filter-tab text-xs px-3 py-1 rounded-full font-bold bg-slate-100 text-slate-600 hover:bg-orange-100 transition-colors" data-cat="公共安全">
          🔦 公共安全
        </button>
        <button onclick="filterTable('環境衛生')"
          class="filter-tab text-xs px-3 py-1 rounded-full font-bold bg-slate-100 text-slate-600 hover:bg-orange-100 transition-colors" data-cat="環境衛生">
          🌿 環境衛生
        </button>
        <button onclick="filterTable('行政服務')"
          class="filter-tab text-xs px-3 py-1 rounded-full font-bold bg-slate-100 text-slate-600 hover:bg-orange-100 transition-colors" data-cat="行政服務">
          📋 行政服務
        </button>
      </div>
    </div>'''

if old_table_header in html:
    html = html.replace(old_table_header, new_table_header, 1)
    print('  OK table filter tabs added')
else:
    print('  FAIL table header not found')


# ══════════════════════════════════════════════════════════════════════════════
# 5. KPI tiles: Add deaths + injuries tiles next to existing ones
# ══════════════════════════════════════════════════════════════════════════════
old_kpi_grid = '''      <!-- 大數字 KPI -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 fade-up delay-3">
        <div class="bg-white/10 backdrop-blur rounded-2xl p-5 border border-white/10">
          <div class="text-orange-400 text-xs font-en font-bold tracking-widest uppercase mb-2">12年累計件數</div>
          <div class="text-4xl font-black font-en counter" id="kpi-total">0</div>
          <div class="text-slate-400 text-xs mt-1">件城市基礎建設資料</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-5 border border-white/10">
          <div class="text-orange-400 text-xs font-en font-bold tracking-widest uppercase mb-2">最大議題</div>
          <div class="text-2xl font-black" id="kpi-top-cat">—</div>
          <div class="text-slate-400 text-xs mt-1">數據第一名類別</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-5 border border-white/10">
          <div class="text-orange-400 text-xs font-en font-bold tracking-widest uppercase mb-2">西區人口</div>
          <div class="text-2xl font-black font-en" id="kpi-west-pop">145,077</div>
          <div class="text-slate-400 text-xs mt-1">位西區市民</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-5 border border-white/10">
          <div class="text-orange-400 text-xs font-en font-bold tracking-widest uppercase mb-2">本月紀錄</div>
          <div class="text-4xl font-black font-en counter" id="kpi-month">0</div>
          <div class="text-slate-400 text-xs mt-1">件本月城市事件</div>
        </div>
      </div>'''

new_kpi_grid = '''      <!-- 大數字 KPI (6格) -->
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 fade-up delay-3">
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/10">
          <div class="text-orange-400 text-xs font-bold tracking-widest uppercase mb-1">12年事故件數</div>
          <div class="text-3xl font-black font-en counter" id="kpi-total">0</div>
          <div class="text-slate-400 text-xs mt-0.5">件城市資料</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/10">
          <div class="text-red-300 text-xs font-bold tracking-widest uppercase mb-1">事故死亡</div>
          <div class="text-3xl font-black font-en" id="kpi-deaths">—</div>
          <div class="text-slate-400 text-xs mt-0.5">累計死亡人數</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/10">
          <div class="text-yellow-300 text-xs font-bold tracking-widest uppercase mb-1">事故受傷</div>
          <div class="text-3xl font-black font-en" id="kpi-injuries">—</div>
          <div class="text-slate-400 text-xs mt-0.5">累計受傷人數</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/10">
          <div class="text-orange-400 text-xs font-bold tracking-widest uppercase mb-1">最大議題</div>
          <div class="text-xl font-black" id="kpi-top-cat">—</div>
          <div class="text-slate-400 text-xs mt-0.5">資料第一名類別</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/10">
          <div class="text-orange-400 text-xs font-bold tracking-widest uppercase mb-1">西區人口</div>
          <div class="text-2xl font-black font-en" id="kpi-west-pop">145,077</div>
          <div class="text-slate-400 text-xs mt-0.5">位西區市民</div>
        </div>
        <div class="bg-white/10 backdrop-blur rounded-2xl p-4 border border-white/10">
          <div class="text-orange-400 text-xs font-bold tracking-widest uppercase mb-1">本月事件</div>
          <div class="text-3xl font-black font-en counter" id="kpi-month">0</div>
          <div class="text-slate-400 text-xs mt-0.5">件本月城市事件</div>
        </div>
      </div>'''

if old_kpi_grid in html:
    html = html.replace(old_kpi_grid, new_kpi_grid, 1)
    print('  OK KPI grid expanded to 6 tiles')
else:
    print('  FAIL KPI grid not found')


# ══════════════════════════════════════════════════════════════════════════════
# 6. JS: Add new rendering functions + update renderKPIs + filterTable
# ══════════════════════════════════════════════════════════════════════════════
# Insert new JS before the closing </script> tag
old_closing = '''  // ── 主程式 ──
  document.addEventListener('DOMContentLoaded', () => {
    const effCat  = (categoryData && categoryData.length > 0) ? categoryData : computeCatData(dataset);
    const effRoad = (roadData && roadData.length > 0) ? roadData : computeRoadData(dataset);

    renderKPIs(dataset, effCat, effRoad);
    renderCatBars(effCat);
    renderRoadList(effRoad);
    renderTrendChart(dataset);
    renderWestPopChart(westPopData);
    renderInfraCard();
    renderAccidentStats();
    renderSummary(effCat);
    renderTable(dataset);
  });'''

new_js = '''  // ── 表格篩選 ──
  let tableFilter = '';
  function filterTable(cat) {
    tableFilter = cat;
    document.querySelectorAll('.filter-tab').forEach(btn => {
      const active = btn.dataset.cat === cat;
      btn.className = 'filter-tab text-xs px-3 py-1 rounded-full font-bold transition-colors ' +
        (active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-600 hover:bg-orange-100');
    });
    renderTable(dataset);
  }

  // ── 交通事故年度/月份分析 ──
  function renderAccidentCharts() {
    const yearMap = {}, monthMap = {};
    let totalAcc = 0, totalDead = 0, totalInj = 0, months = 0;
    dataset.forEach(r => {
      if (r.subcategory !== '交通事故') return;
      const y = r.year || (r.date||'').slice(0,4);
      const m = (r.date||'').slice(5,7);
      const c = r.count||0, d = r.deaths||0, inj = r.injuries||0;
      totalAcc += c; totalDead += d; totalInj += inj;
      if (y) { yearMap[y] = (yearMap[y]||0) + c; months++; }
      if (m) { monthMap[m] = (monthMap[m]||0) + c; }
    });
    // KPI 更新
    const fmt = n => n >= 10000 ? (n/10000).toFixed(1)+'萬' : n >= 1000 ? (n/1000).toFixed(1)+'K' : String(n);
    const gi = id => document.getElementById(id);
    if (gi('acc-total'))   gi('acc-total').textContent   = totalAcc   ? totalAcc.toLocaleString()  : '—';
    if (gi('acc-dead'))    gi('acc-dead').textContent    = totalDead  ? totalDead.toLocaleString() : '—';
    if (gi('acc-inj'))     gi('acc-inj').textContent     = totalInj   ? fmt(totalInj)              : '—';
    if (gi('acc-monthly')) gi('acc-monthly').textContent = months > 0 ? Math.round(totalAcc/months): '—';
    // 年度趨勢圖
    const years = Object.keys(yearMap).sort();
    const yVals = years.map(y=>yearMap[y]);
    if (gi('chartAccYear') && years.length > 0) {
      new Chart(gi('chartAccYear').getContext('2d'), {
        type: 'bar',
        data: { labels: years, datasets: [{
          data: yVals,
          backgroundColor: yVals.map((v,i) => {
            const mx = Math.max(...yVals);
            return v === mx ? '#EF4444' : '#FCA5A5';
          }),
          borderRadius: 3, borderSkipped: false
        }]},
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: {
            label: c => ' ' + c.parsed.y.toLocaleString() + ' 件'
          }}},
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: { grid: { color: '#F1F5F9' }, ticks: { font: { size: 10 },
              callback: v => v >= 1000 ? (v/1000).toFixed(0)+'K' : v }}
          }
        }
      });
    }
    // 月份分布圖
    const mLabels = ['1','2','3','4','5','6','7','8','9','10','11','12'];
    const mVals = mLabels.map(m => monthMap[m.padStart(2,'0')]||0);
    if (gi('chartAccMonth') && mVals.some(v=>v>0)) {
      new Chart(gi('chartAccMonth').getContext('2d'), {
        type: 'bar',
        data: { labels: mLabels.map(m=>m+'月'), datasets: [{
          data: mVals,
          backgroundColor: mVals.map((v,i) => {
            const mx = Math.max(...mVals);
            return v === mx ? '#F97316' : '#FED7AA';
          }),
          borderRadius: 2, borderSkipped: false
        }]},
        options: {
          responsive: true, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: {
            label: c => ' ' + c.parsed.y.toLocaleString() + ' 件'
          }}},
          scales: {
            x: { grid: { display: false }, ticks: { font: { size: 10 } } },
            y: { grid: { color: '#F1F5F9' }, ticks: { font: { size: 10 } } }
          }
        }
      });
    }
    // 洞察文字
    const ins = gi('acc-insight');
    if (ins && years.length > 0) {
      const maxY = years.reduce((a,b)=>yearMap[a]>yearMap[b]?a:b);
      const minY = years.reduce((a,b)=>yearMap[a]<yearMap[b]?a:b);
      const maxM = mLabels.reduce((a,b)=>(monthMap[a.padStart(2,'0')]||0)>(monthMap[b.padStart(2,'0')]||0)?a:b);
      const trend = yVals.length >= 2 ? (yVals[yVals.length-1] - yVals[0]) : 0;
      ins.innerHTML = [
        '<div class="flex items-start gap-1.5"><span class="text-red-400 font-bold shrink-0">●</span><span>最高峰：<strong class="text-slate-800">' + maxY + ' 年</strong>（' + yearMap[maxY].toLocaleString() + '件）</span></div>',
        '<div class="flex items-start gap-1.5"><span class="text-green-400 font-bold shrink-0">●</span><span>最少年：<strong class="text-slate-800">' + minY + ' 年</strong>（' + yearMap[minY].toLocaleString() + '件）</span></div>',
        '<div class="flex items-start gap-1.5"><span class="text-orange-400 font-bold shrink-0">●</span><span>事故高峰月：<strong class="text-slate-800">' + maxM + ' 月</strong>，需加強執法</span></div>',
        '<div class="flex items-start gap-1.5"><span class="text-' + (trend>0?'red':'green') + '-400 font-bold shrink-0">●</span><span>12年趨勢：' + (trend>0?'事故增加 ↑':'事故減少 ↓') + ' <strong class="text-slate-800">' + Math.abs(trend).toLocaleString() + '件</strong></span></div>',
        '<div class="flex items-start gap-1.5"><span class="text-blue-400 font-bold shrink-0">●</span><span>每 <strong class="text-slate-800">' + (totalAcc>0?Math.round(24*365*12/totalAcc):0) + ' 小時</strong>發生 1 件事故</span></div>',
      ].join('');
    }
  }

  // ── 橋梁設施明細 ──
  function renderBridgeDetail() {
    const bridges = dataset.filter(r => r.subcategory === '橋梁設施');
    if (!bridges.length) return;
    // 道路等級統計
    const classMap = {};
    bridges.forEach(b => { const c = b.description?.match(/([^，]+)，/)?.[1] || '其他'; classMap[c] = (classMap[c]||0)+1; });
    const classEl = document.getElementById('bridge-class-stats');
    if (classEl) {
      const colors = ['bg-blue-100 text-blue-700','bg-green-100 text-green-700','bg-orange-100 text-orange-700','bg-purple-100 text-purple-700'];
      classEl.innerHTML = Object.entries(classMap).sort((a,b)=>b[1]-a[1]).slice(0,6).map(([k,v],i)=>
        '<span class="text-[11px] font-bold px-2 py-0.5 rounded-full ' + (colors[i%colors.length]) + '">' + k + ' ×' + v + '</span>'
      ).join('');
    }
    const el = document.getElementById('bridge-list-detail');
    if (!el) return;
    el.innerHTML = bridges.map(b => {
      const desc = b.description || '';
      const cls = desc.match(/([^，]+)/)?.[1] || '';
      const lenM = b.length_m ? parseFloat(b.length_m).toFixed(0) + 'm' : '';
      const mgr = desc.match(/管理：(.+)/)?.[1] || '';
      return '<div class="flex items-center gap-2 py-1 border-b border-slate-50 text-xs">' +
        '<span class="text-slate-400 shrink-0">🌉</span>' +
        '<span class="text-slate-700 font-semibold flex-1 truncate">' + (b.title||'') + '</span>' +
        '<span class="shrink-0 text-[10px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">' + cls + '</span>' +
        (lenM ? '<span class="shrink-0 text-slate-400 text-[10px]">' + lenM + '</span>' : '') +
      '</div>';
    }).join('');
  }

  // ── 停車場明細 ──
  function renderParkingDetail() {
    const lots = dataset.filter(r => r.subcategory === '公有停車場').sort((a,b)=>(b.count||0)-(a.count||0));
    if (!lots.length) return;
    const el = document.getElementById('parking-list-detail');
    const capEl = document.getElementById('parking-total-cap');
    if (!el) return;
    const totalCap = lots.reduce((s,r)=>s+(r.count||0),0);
    if (capEl) capEl.textContent = totalCap.toLocaleString() + ' 格';
    el.innerHTML = lots.map(p => {
      const name = (p.title||'').replace(/\\s+/g,' ').trim();
      const type = p.description?.match(/^([^停]+)停車場/)?.[1] || '';
      return '<div class="flex items-center justify-between text-xs py-0.5">' +
        '<span class="text-slate-600 truncate max-w-[140px]">🅿️ ' + (name.length>15?name.slice(0,15)+'…':name) + '</span>' +
        '<div class="flex items-center gap-1.5 shrink-0">' +
          (type ? '<span class="text-[10px] bg-green-50 text-green-600 px-1 rounded">' + type + '</span>' : '') +
          '<span class="font-black text-slate-700">' + (p.count||0) + '格</span>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // ── 噪音監測站明細 ──
  function renderNoiseDetail() {
    const stations = {};
    dataset.filter(r => r.subcategory === '噪音管制').forEach(r => {
      const st = r.location || '';
      if (!stations[st]) stations[st] = { db: [], zone: '' };
      const m = (r.description||'').match(/月均([\d.]+)dB/);
      if (m) stations[st].db.push(parseFloat(m[1]));
      const z = (r.description||'').match(/管制區(.)/);
      if (z) stations[st].zone = z[1];
    });
    const el = document.getElementById('noise-list-detail');
    if (!el) return;
    const stList = Object.entries(stations).map(([st, info]) => {
      const avgDb = info.db.length ? (info.db.reduce((s,v)=>s+v,0)/info.db.length).toFixed(1) : null;
      return { st, avgDb: avgDb ? parseFloat(avgDb) : 0, zone: info.zone };
    }).sort((a,b)=>b.avgDb-a.avgDb);
    if (!stList.length) { el.innerHTML = '<p class="text-xs text-slate-400">暫無噪音資料</p>'; return; }
    const stdLimit = 65; // 交通主幹道管制標準
    el.innerHTML = stList.slice(0,5).map(s => {
      const over = s.avgDb > stdLimit;
      const bar = Math.round(Math.min(s.avgDb/90*100, 100));
      return '<div class="mb-1.5">' +
        '<div class="flex justify-between text-xs mb-0.5">' +
          '<span class="text-slate-600 truncate">' + (s.st||'').replace('嘉義市','') + '</span>' +
          '<span class="font-black ' + (over?'text-red-600':'text-green-600') + '">' + s.avgDb + ' dB' + (over?' ⚠️':'') + '</span>' +
        '</div>' +
        '<div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">' +
          '<div class="h-full rounded-full" style="width:' + bar + '%;background:' + (over?'#EF4444':'#22C55E') + '"></div>' +
        '</div>' +
      '</div>';
    }).join('') + (stList.length > 5 ? '<p class="text-[10px] text-slate-400 mt-1">另有 ' + (stList.length-5) + ' 個監測站</p>' : '');
  }

  // ── 溺水安全統計 ──
  function renderDrowningStats() {
    const drowning = dataset.filter(r => r.subcategory === '水域安全');
    if (!drowning.length) return;
    const gi = id => document.getElementById(id);
    if (gi('drowning-total')) gi('drowning-total').textContent = drowning.length.toLocaleString();
    // 水域類型分布
    const typeMap = {};
    drowning.forEach(r => {
      const t = (r.title||'').replace('溺水事故（','').replace('）','') || '不明';
      typeMap[t] = (typeMap[t]||0)+1;
    });
    const tEl = gi('drowning-type-list');
    if (tEl) {
      tEl.innerHTML = Object.entries(typeMap).sort((a,b)=>b[1]-a[1]).slice(0,5).map(([t,n]) =>
        '<div class="flex justify-between text-xs py-0.5 border-b border-blue-50">' +
          '<span class="text-slate-600">💧 ' + t + '</span>' +
          '<span class="font-black text-blue-600">' + n + ' 件</span>' +
        '</div>'
      ).join('');
    }
  }

  // ── 議會資料 ──
  function renderCouncilSection() {
    const cs = typeof councilStat !== 'undefined' ? councilStat : {};
    const gi = id => document.getElementById(id);
    if (gi('council-meetings'))  gi('council-meetings').textContent  = cs.meetings_count || '—';
    if (gi('council-questions')) gi('council-questions').textContent = cs.question_count  || '—';
    if (gi('council-members'))   gi('council-members').textContent   = cs.councilors     || '17';
    // 議員名單（簡易顯示）
    const councilors = ['蕭淑玲','陳怡岳','蔡明儀','林建豐','柳宗廷','吳竟銓','徐欣瑩','謝明匡','許明財','劉蓁蓁','蕭貫譽','王美惠','廖怡琛','郭明賓','李明進','陳靜思','唐美玲'];
    const cEl = gi('councilor-list');
    if (cEl) cEl.innerHTML = councilors.map(n =>
      '<span class="text-[10px] px-2 py-0.5 bg-purple-50 text-purple-600 rounded-full font-bold">' + n + '</span>'
    ).join('');
  }

  // ── renderKPIs 更新（加入 deaths/injuries）──
  // Override after original definition

  // ── 主程式 ──
  document.addEventListener('DOMContentLoaded', () => {
    const effCat  = (categoryData && categoryData.length > 0) ? categoryData : computeCatData(dataset);
    const effRoad = (roadData && roadData.length > 0) ? roadData : computeRoadData(dataset);

    renderKPIs(dataset, effCat, effRoad);
    // Deaths / injuries KPI
    let kpiDead = 0, kpiInj = 0;
    dataset.forEach(r => { if (r.subcategory==='交通事故') { kpiDead+=(r.deaths||0); kpiInj+=(r.injuries||0); }});
    const fmt2 = n => n>=10000?(n/10000).toFixed(1)+'萬':n>=1000?(n/1000).toFixed(1)+'K':String(n);
    const gd = document.getElementById('kpi-deaths');
    const gi2 = document.getElementById('kpi-injuries');
    if (gd) gd.textContent = kpiDead ? kpiDead.toLocaleString() : '—';
    if (gi2) gi2.textContent = kpiInj ? fmt2(kpiInj) : '—';

    renderCatBars(effCat);
    renderRoadList(effRoad);
    renderTrendChart(dataset);
    renderWestPopChart(westPopData);
    renderInfraCard();
    renderAccidentStats();
    renderAccidentCharts();
    renderBridgeDetail();
    renderParkingDetail();
    renderNoiseDetail();
    renderDrowningStats();
    renderCouncilSection();
    renderSummary(effCat);
    renderTable(dataset);
  });'''

if old_closing in html:
    html = html.replace(old_closing, new_js, 1)
    print('  OK JS functions + DOMContentLoaded updated')
else:
    print('  FAIL DOMContentLoaded block not found')

# ══════════════════════════════════════════════════════════════════════════════
# 7. TABLE renderTable: apply filter
# ══════════════════════════════════════════════════════════════════════════════
old_render_table = '    data.slice(0, tableExpanded ? 50 : 15).forEach(item => {'
new_render_table = '''    const filteredData = tableFilter ? data.filter(r => r.category === tableFilter || r.subcategory === tableFilter) : data;
    filteredData.slice(0, tableExpanded ? 100 : 20).forEach(item => {'''

if old_render_table in html:
    html = html.replace(old_render_table, new_render_table, 1)
    print('  OK renderTable filter applied')
else:
    print('  FAIL renderTable filter line not found')

# Save
open(path, 'w', encoding='utf-8').write(html)
changed = html != original
print(f'\nOK index.html saved ({"MODIFIED" if changed else "NO CHANGE"})')
