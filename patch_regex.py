"""Fix scraper.py injection regexes to tolerate any whitespace around = sign,
and redesign the 基礎建設一覽 card in index.html to be dynamic."""
import re

# ── Fix 1: scraper.py regex patterns ──────────────────────────────────────────
spath = 'C:/Users/elvis/Downloads/elvis-agent/chiayi2026/scraper.py'
s = open(spath, encoding='utf-8').read()
original_s = s

replacements = [
    (r'r"const westPopData = \[.*?\];"',    r'r"const westPopData\s*=\s*\[.*?\];"'),
    (r'r"const dataset = \[.*?\];"',        r'r"const dataset\s*=\s*\[.*?\];"'),
    (r'r"const categoryData = \[.*?\];"',   r'r"const categoryData\s*=\s*\[.*?\];"'),
    (r'r"const roadData = \[.*?\];"',       r'r"const roadData\s*=\s*\[.*?\];"'),
    (r'r"const newsByCat = \{.*?\};"',      r'r"const newsByCat\s*=\s*\{.*?\};"'),
    (r'r"const catSources = \{.*?\};"',     r'r"const catSources\s*=\s*\{.*?\};"'),
    (r'r"const councilStat = \{.*?\};"',    r'r"const councilStat\s*=\s*\{.*?\};"'),
]

for old, new in replacements:
    if old in s:
        s = s.replace(old, new, 1)
        print(f'  OK fixed: {old[:45]}')
    else:
        print(f'  FAIL not found: {old[:45]}')

open(spath, 'w', encoding='utf-8').write(s)
print(f'  scraper.py saved ({"modified" if s != original_s else "NO CHANGE"})')

# ── Fix 2: index.html — redesign 基礎建設一覽 card ──────────────────────────
hpath = 'C:/Users/elvis/Downloads/elvis-agent/chiayi2026/index.html'
html = open(hpath, encoding='utf-8').read()
original_html = html

old_infra = '''    <div class="card p-6 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100">
      <div class="text-3xl mb-3">🌉</div>
      <h3 class="font-black text-slate-900 text-base mb-2">基礎建設一覽</h3>
      <p class="text-sm text-slate-600 leading-relaxed">
        嘉義市有 <strong>172 座橋梁</strong>、<strong>28,688 盞路燈</strong>、<strong>38 處公有停車場</strong>。<br>
        <span class="font-bold text-blue-700 mt-2 inline-block">維護城市基礎，是議員的責任</span>
      </p>
    </div>'''

new_infra = '''    <div class="card p-6 bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100">
      <div class="text-2xl mb-2">🌉</div>
      <h3 class="font-black text-slate-900 text-base mb-3">基礎建設資產盤點</h3>
      <!-- 4 格統計磚 -->
      <div class="grid grid-cols-2 gap-2 mb-3">
        <div class="bg-white/80 rounded-xl p-2.5 text-center border border-blue-100">
          <div class="text-[10px] font-bold text-blue-500 uppercase tracking-wide">橋梁</div>
          <div class="text-xl font-black text-blue-700" id="ib-bridges">172</div>
          <div class="text-[9px] text-slate-400">座</div>
        </div>
        <div class="bg-white/80 rounded-xl p-2.5 text-center border border-yellow-100">
          <div class="text-[10px] font-bold text-yellow-500 uppercase tracking-wide">路燈</div>
          <div class="text-xl font-black text-yellow-600" id="ib-lights">28,688</div>
          <div class="text-[9px] text-slate-400">盞</div>
        </div>
        <div class="bg-white/80 rounded-xl p-2.5 text-center border border-green-100">
          <div class="text-[10px] font-bold text-green-500 uppercase tracking-wide">公有停車場</div>
          <div class="text-xl font-black text-green-600" id="ib-parking">38</div>
          <div class="text-[9px] text-slate-400">處</div>
        </div>
        <div class="bg-white/80 rounded-xl p-2.5 text-center border border-orange-100">
          <div class="text-[10px] font-bold text-orange-500 uppercase tracking-wide">管線施工</div>
          <div class="text-xl font-black text-orange-600" id="ib-pipes">—</div>
          <div class="text-[9px] text-slate-400">路段</div>
        </div>
      </div>
      <!-- 動態細節（JS 填入） -->
      <div id="ib-detail" class="space-y-1 text-xs text-slate-600 mb-2"></div>
      <p class="text-[11px] font-bold text-blue-700">維護城市基礎建設，是議員的責任</p>
    </div>'''

if old_infra in html:
    html = html.replace(old_infra, new_infra, 1)
    print('  OK infra card replaced')
else:
    print('  FAIL infra card not found')

# ── Fix 3: Add renderInfraCard() before renderRoadList() ─────────────────────
old_road_fn = '  function renderRoadList(roadData) {'
new_infra_fn = '''  function renderInfraCard() {
    // 從 dataset 計算各類基礎建設數量
    let bridges = 0, lights = 0, parking = 0, pipes = 0, parkingCap = 0;
    const lightAreas = [], parkingLots = [], pipeTypes = {};
    dataset.forEach(r => {
      const sub = r.subcategory || '';
      if (sub === '橋梁設施')       { bridges += (r.count || 1); }
      else if (sub === '路燈照明')   { lights += (r.count || 0); if (r.count > 0) lightAreas.push({loc: r.location||'', n: r.count}); }
      else if (sub === '公有停車場') { parking += 1; parkingCap += (r.count || 0); parkingLots.push({name:(r.title||'').replace(/\\s+/g,' ').trim(), cap: r.count||0}); }
      else if (['電力管線','電信管線','自來水管線','瓦斯管線','市府工程','道路施工'].includes(sub)) {
        pipes += 1; pipeTypes[sub] = (pipeTypes[sub]||0) + 1;
      }
    });
    const gi = id => document.getElementById(id);
    if (gi('ib-bridges'))  gi('ib-bridges').textContent  = bridges  > 0 ? bridges  : '172';
    if (gi('ib-lights'))   gi('ib-lights').textContent   = lights   > 0 ? lights.toLocaleString() : '28,688';
    if (gi('ib-parking'))  gi('ib-parking').textContent  = parking  > 0 ? parking  : '38';
    if (gi('ib-pipes'))    gi('ib-pipes').textContent    = pipes    > 0 ? pipes    : '—';
    const det = gi('ib-detail');
    if (!det) return;
    const parts = [];
    if (parkingCap > 0) parts.push('<div class="flex justify-between border-b border-blue-50 pb-1"><span class="text-slate-500">停車格總數</span><span class="font-bold text-slate-700">' + parkingCap.toLocaleString() + ' 格</span></div>');
    // 最大路燈路段 Top 3
    if (lightAreas.length > 0) {
      lightAreas.sort((a,b)=>b.n-a.n).slice(0,3).forEach(a => {
        parts.push('<div class="flex justify-between text-[11px]"><span class="text-slate-400 truncate max-w-[110px]">💡' + a.loc + '</span><span class="font-bold text-slate-600 shrink-0 ml-1">' + a.n.toLocaleString() + '盞</span></div>');
      });
    }
    // 停車場容量前3
    if (parkingLots.length > 0) {
      parkingLots.sort((a,b)=>b.cap-a.cap).slice(0,2).forEach(p => {
        parts.push('<div class="flex justify-between text-[11px]"><span class="text-slate-400 truncate max-w-[110px]">🅿️' + (p.name.length>12?p.name.slice(0,12)+'…':p.name) + '</span><span class="font-bold text-slate-600 shrink-0 ml-1">' + (p.cap||0) + '格</span></div>');
      });
    }
    // 管線施工類型
    const ptEntries = Object.entries(pipeTypes);
    if (ptEntries.length > 0) {
      parts.push('<div class="text-[11px] text-slate-400 pt-1">🔧管線：' + ptEntries.map(([k,v])=>k+'×'+v).join('・') + '</div>');
    }
    det.innerHTML = parts.join('');
  }

  function renderRoadList(roadData) {'''

if old_road_fn in html:
    html = html.replace(old_road_fn, new_infra_fn, 1)
    print('  OK renderInfraCard() inserted')
else:
    print('  FAIL renderRoadList marker not found')

# ── Fix 4: Call renderInfraCard() in DOMContentLoaded ────────────────────────
html = html.replace(
    '    renderAccidentStats();',
    '    renderInfraCard();\n    renderAccidentStats();',
    1
)
print('  OK renderInfraCard() call added')

open(hpath, 'w', encoding='utf-8').write(html)
print(f'  index.html saved ({"modified" if html != original_html else "NO CHANGE"})')
print('\nAll done.')
