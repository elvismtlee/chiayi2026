"""Patch renderCatBars to show source breakdown + news links per category."""
path = 'C:/Users/elvis/Downloads/elvis-agent/chiayi2026/index.html'
html = open(path, encoding='utf-8').read()

old_fn = r"""  function renderCatBars(catData) {
    const el = document.getElementById('cat-bars');
    const catMap = {};
    catData.forEach(d => { catMap[d.category] = d.count; });
    CAT_ORDER.forEach(c => { if (!(c in catMap)) catMap[c] = 0; });

    const nonZero  = CAT_ORDER.map(c => ({ category: c, count: catMap[c]||0 })).filter(d=>d.count>0);
    const zeroList = CAT_ORDER.map(c => ({ category: c, count: catMap[c]||0 })).filter(d=>d.count===0);
    const maxVal   = nonZero[0]?.count || 1;
    const total    = nonZero.reduce((s,d)=>s+d.count,0) || 1;

    const barHtml = nonZero.map(d => {
      const pct   = Math.round(d.count / total * 100);
      const w     = Math.max(2, Math.round(d.count / maxVal * 100));
      const color = getCatColor(d.category);
      const icon  = getCatIcon(d.category);
      return '<div>' +
        '<div class="flex items-center justify-between mb-1">' +
          '<div class="flex items-center gap-1.5 text-sm font-semibold text-slate-800">' +
            '<span class="text-lg leading-none">' + icon + '</span>' +
            '<span>' + d.category + '</span>' +
          '</div>' +
          '<div class="text-right shrink-0 pl-3">' +
            '<span class="text-sm font-black text-slate-900">' + d.count.toLocaleString() + '</span>' +
            '<span class="text-xs text-slate-400 ml-1">(' + pct + '%)</span>' +
          '</div>' +
        '</div>' +
        '<div class="h-2 bg-slate-100 rounded-full overflow-hidden">' +
          '<div class="h-full rounded-full bar-fill" style="--w:' + w + '%;background:' + color + ';"></div>' +
        '</div></div>';
    }).join('');

    const chipHtml = zeroList.length > 0 ?
      '<div class="mt-4 pt-3 border-t border-slate-100">' +
        '<p class="text-xs text-slate-400 mb-2 font-medium">另監測 ' + zeroList.length + ' 大議題（社群資料持續積累中）</p>' +
        '<div class="flex flex-wrap gap-1.5">' +
          zeroList.map(d => '<span class="inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-400">' + getCatIcon(d.category) + d.category + '</span>').join('') +
        '</div></div>' : '';

    // 子類別快速統計（從 dataset 計算，用 count 欄位加總）
    const subMap = {};
    dataset.forEach(r => {
      const sub = r.subcategory;
      if (sub && r.category !== '西區人口') subMap[sub] = (subMap[sub]||0) + (r.count || 1);
    });
    const topSubs = Object.entries(subMap).sort((a,b)=>b[1]-a[1]).slice(0,8);
    const fmt = n => n >= 10000 ? (n/10000).toFixed(1)+'萬' : n >= 1000 ? (n/1000).toFixed(1)+'K' : n.toLocaleString();
    const subHtml = topSubs.length > 0 ?
      '<div class="mt-4 pt-3 border-t border-slate-100">' +
        '<p class="text-xs font-bold text-slate-500 mb-2">各子類別累計件數</p>' +
        '<div class="grid grid-cols-2 gap-x-6 gap-y-1.5">' +
          topSubs.map(([sub,cnt]) =>
            '<div class="flex items-center justify-between text-xs">' +
              '<span class="text-slate-600">' + sub + '</span>' +
              '<span class="font-black text-orange-600 ml-1">' + fmt(cnt) + '</span>' +
            '</div>'
          ).join('') +
        '</div></div>' : '';

    // 頂部總計橫幅
    const grandTotal = nonZero.reduce((s,d)=>s+d.count, 0);
    const fmtGrand = grandTotal >= 10000 ? Math.round(grandTotal/1000)*1000 : grandTotal;
    const totalBanner = grandTotal > 0
      ? '<div class="mb-3 flex items-center gap-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2">' +
          '<span class="text-base">📊</span>' +
          '<span>12 年累計：<strong class="text-slate-800 text-sm">' + grandTotal.toLocaleString() + '</strong> 件次城市資料</span>' +
        '</div>' : '';

    el.innerHTML = totalBanner + barHtml + chipHtml + subHtml;
  }"""

new_fn = r"""  function renderCatBars(catData) {
    const el = document.getElementById('cat-bars');
    const catMap = {};
    catData.forEach(d => { catMap[d.category] = d.count; });
    CAT_ORDER.forEach(c => { if (!(c in catMap)) catMap[c] = 0; });

    const nonZero  = CAT_ORDER.map(c => ({ category: c, count: catMap[c]||0 })).filter(d=>d.count>0);
    const zeroList = CAT_ORDER.map(c => ({ category: c, count: catMap[c]||0 })).filter(d=>d.count===0);
    const maxVal   = nonZero[0]?.count || 1;
    const total    = nonZero.reduce((s,d)=>s+d.count,0) || 1;
    const fmt = n => n >= 10000 ? (n/10000).toFixed(1)+'萬' : n >= 1000 ? (n/1000).toFixed(1)+'K' : n.toLocaleString();

    const barHtml = nonZero.map(d => {
      const pct   = Math.round(d.count / total * 100);
      const w     = Math.max(2, Math.round(d.count / maxVal * 100));
      const color = getCatColor(d.category);
      const icon  = getCatIcon(d.category);
      const src   = (typeof catSources !== 'undefined' && catSources[d.category]) || {};
      // 來源標籤（開放資料/新聞/社群/議會）
      const srcPills = [];
      if (src.opendata > 0) srcPills.push('<span class="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded font-bold">開放資料 ' + fmt(src.opendata) + '</span>');
      if (src.news    > 0) srcPills.push('<span class="text-[10px] px-1.5 py-0.5 bg-orange-50 text-orange-600 rounded font-bold">新聞 ' + src.news + '則</span>');
      if (src.social  > 0) srcPills.push('<span class="text-[10px] px-1.5 py-0.5 bg-green-50 text-green-600 rounded font-bold">社群 ' + src.social + '則</span>');
      if (src.council > 0) srcPills.push('<span class="text-[10px] px-1.5 py-0.5 bg-purple-50 text-purple-600 rounded font-bold">議會 ' + src.council + '次</span>');
      const srcLine = srcPills.length > 0 ? '<div class="flex flex-wrap gap-1 mt-1 mb-1">' + srcPills.join('') + '</div>' : '';
      // 相關新聞（最多 2 則）
      const nbc = (typeof newsByCat !== 'undefined') ? newsByCat : {};
      const catNews = (nbc[d.category] || []).slice(0, 2);
      const newsLinks = catNews.map(n =>
        '<div class="flex items-start gap-1 text-[11px] text-slate-500 leading-snug">' +
          '<span class="text-orange-400 mt-0.5 shrink-0 text-[9px]">▸</span>' +
          '<a href="' + (n.url||'#') + '" target="_blank" rel="noopener" ' +
             'class="hover:text-orange-500 transition-colors line-clamp-1 flex-1 min-w-0">' +
            n.title + (n.source ? ' <span class="text-slate-400">—' + n.source + '</span>' : '') +
          '</a>' +
        '</div>'
      ).join('');
      const newsHtml = newsLinks ? '<div class="mt-1 space-y-0.5 mb-0.5">' + newsLinks + '</div>' : '';
      return '<div class="pb-2">' +
        '<div class="flex items-center justify-between mb-0.5">' +
          '<div class="flex items-center gap-1.5 text-sm font-semibold text-slate-800">' +
            '<span class="text-base leading-none">' + icon + '</span>' +
            '<span>' + d.category + '</span>' +
          '</div>' +
          '<div class="text-right shrink-0 pl-2">' +
            '<span class="text-sm font-black text-slate-900">' + fmt(d.count) + '</span>' +
            '<span class="text-xs text-slate-400 ml-1">(' + pct + '%)</span>' +
          '</div>' +
        '</div>' +
        '<div class="h-1.5 bg-slate-100 rounded-full overflow-hidden">' +
          '<div class="h-full rounded-full bar-fill" style="--w:' + w + '%;background:' + color + ';"></div>' +
        '</div>' +
        srcLine + newsHtml +
      '</div>';
    }).join('<div class="border-t border-slate-50 my-0.5"></div>');

    const chipHtml = zeroList.length > 0 ?
      '<div class="mt-3 pt-3 border-t border-slate-100">' +
        '<p class="text-xs text-slate-400 mb-1.5 font-medium">另監測 ' + zeroList.length + ' 大議題（資料持續積累中）</p>' +
        '<div class="flex flex-wrap gap-1.5">' +
          zeroList.map(d => '<span class="inline-flex items-center gap-0.5 text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-400">' + getCatIcon(d.category) + d.category + '</span>').join('') +
        '</div></div>' : '';

    // 子類別快速統計（從 dataset 計算，用 count 欄位加總）
    const subMap = {};
    dataset.forEach(r => {
      const sub = r.subcategory;
      if (sub && r.category !== '西區人口') subMap[sub] = (subMap[sub]||0) + (r.count || 1);
    });
    const topSubs = Object.entries(subMap).sort((a,b)=>b[1]-a[1]).slice(0,8);
    const subHtml = topSubs.length > 0 ?
      '<div class="mt-3 pt-3 border-t border-slate-100">' +
        '<p class="text-xs font-bold text-slate-500 mb-1.5">各子類別累計件數</p>' +
        '<div class="grid grid-cols-2 gap-x-4 gap-y-1">' +
          topSubs.map(([sub,cnt]) =>
            '<div class="flex items-center justify-between text-xs">' +
              '<span class="text-slate-600 truncate">' + sub + '</span>' +
              '<span class="font-black text-orange-600 ml-1 shrink-0">' + fmt(cnt) + '</span>' +
            '</div>'
          ).join('') +
        '</div></div>' : '';

    // 頂部總計橫幅（顯示來源分解）
    const grandTotal = nonZero.reduce((s,d)=>s+d.count, 0);
    const srcObj = typeof catSources !== 'undefined' ? catSources : {};
    const totalNews  = Object.values(srcObj).reduce((s,v)=>s+(v.news||0), 0);
    const totalSoc   = Object.values(srcObj).reduce((s,v)=>s+(v.social||0), 0);
    const totalCou   = Object.values(srcObj).reduce((s,v)=>s+(v.council||0), 0);
    const srcSummary = [
      totalNews  > 0 ? '新聞 ' + totalNews + '則'   : '',
      totalSoc   > 0 ? '社群 ' + totalSoc + '則'    : '',
      totalCou   > 0 ? '議會 ' + totalCou + '次'    : '',
    ].filter(Boolean).join(' · ');
    const totalBanner = grandTotal > 0
      ? '<div class="mb-3 flex items-center gap-2 text-xs text-slate-500 bg-slate-50 rounded-lg px-3 py-2">' +
          '<span>📊</span>' +
          '<span>12 年累計 <strong class="text-slate-800">' + grandTotal.toLocaleString() + '</strong> 件次' +
          (srcSummary ? ' <span class="text-slate-400 ml-1">＋' + srcSummary + '</span>' : '') + '</span>' +
        '</div>' : '';

    el.innerHTML = totalBanner + barHtml + chipHtml + subHtml;
  }"""

if old_fn in html:
    html = html.replace(old_fn, new_fn, 1)
    print('  OK renderCatBars replaced')
else:
    print('  FAIL old_fn not found')
    # Debug: find closest match
    import difflib
    lines_old = old_fn.splitlines()
    for i, line in enumerate(lines_old):
        if line not in html:
            print(f'  First missing line {i}: {repr(line[:60])}')
            break

open(path, 'w', encoding='utf-8').write(html)
print('  OK file saved')
