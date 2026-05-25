/**
 * 財經雷達 — 首頁 (index.html)
 * 讀取 index.json 渲染文章列表，並從 /api/market-data 載入即時市場數據。
 */

// ── 日期工具 ──────────────────────────────────────────

function todayTW() {
  const d = new Date();
  const days = ['日', '一', '二', '三', '四', '五', '六'];
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日（週${days[d.getDay()]}）`;
}

function formatDateShort(dateStr) {
  const [, m, dd] = dateStr.split('-');
  return `${m} / ${dd}`;
}

function getWeekdayTW(dateStr) {
  const days = ['日', '一', '二', '三', '四', '五', '六'];
  const d = new Date(dateStr + 'T00:00:00');
  return `週${days[d.getDay()]}`;
}

function getMonthLabel(dateStr) {
  const [y, m] = dateStr.split('-');
  return `${y} 年 ${parseInt(m)} 月`;
}

// ── 數字格式化 ──────────────────────────────────────────

function fmtPrice(price, decimals = 2) {
  if (price == null || isNaN(price)) return '—';
  return price.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function fmtStatValue(value, decimals = 2) {
  if (value == null || isNaN(value)) return '—';
  return Number(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function formatMarketTime(ts) {
  if (!ts) return '—';
  const t = new Date(ts);
  const hh = String(t.getHours()).padStart(2, '0');
  const mm = String(t.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}

// ── XSS ──────────────────────────────────────────────

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── 取得文章資料 ──────────────────────────────────────────

async function fetchIndex() {
  const res = await fetch('/data/index.json');
  if (!res.ok) throw new Error('index.json 讀取失敗');
  return res.json();
}

// ── 渲染文章列表 ─────────────────────────────────────────

function renderList(articles) {
  const root = document.getElementById('article-list');
  if (!articles.length) {
    root.innerHTML = '<p style="color:var(--text-2);font-size:.88rem;padding:1rem 0">尚無文章</p>';
    return;
  }

  const groups = new Map();
  articles.forEach(a => {
    const key = getMonthLabel(a.date);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(a);
  });

  let html = '';
  groups.forEach((items, monthLabel) => {
    html += `<div class="month-group">`;
    if (groups.size > 1) {
      html += `<div class="month-label">${esc(monthLabel)}</div>`;
    }
    items.forEach(a => {
      const dateShort = formatDateShort(a.date);
      const weekday   = getWeekdayTW(a.date);
      const tagsHtml  = (a.tags || []).slice(0, 4)
        .map(t => `<span class="item-tag">${esc(t)}</span>`).join('');

      html += `
        <a class="article-item" href="article.html?date=${esc(a.date_key)}" aria-label="${esc(a.title)}">
          <span class="article-item-date">${esc(dateShort)}<br><span style="color:var(--text-3)">${esc(weekday)}</span></span>
          <span class="article-item-body">
            <span class="article-item-title">${esc(a.title)}</span>
            <span class="article-item-tags">${tagsHtml}</span>
          </span>
          <svg class="article-item-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="5" y1="12" x2="19" y2="12"/>
            <polyline points="12 5 19 12 12 19"/>
          </svg>
        </a>`;
    });
    html += `</div>`;
  });

  root.innerHTML = html;
}

function syncStickyOffsets() {
  const root = document.documentElement;
  const ticker = document.querySelector('.ticker-wrap');
  const header = document.querySelector('.site-header');
  const tabNav = document.querySelector('.tab-nav');
  if (!root || !ticker || !header || !tabNav) return;

  const tickerH = Math.round(ticker.getBoundingClientRect().height || 40);
  const headerH = Math.round(header.getBoundingClientRect().height || 52);
  const tabNavH = Math.round(tabNav.getBoundingClientRect().height || 56);

  root.style.setProperty('--ticker-h', `${tickerH}px`);
  root.style.setProperty('--header-h', `${headerH}px`);
  root.style.setProperty('--tab-nav-h', `${tabNavH}px`);
}

// ── Tab Switching ─────────────────────────────────────

function initTabs() {
  const btns  = document.querySelectorAll('.tab-btn');
  const panes = document.querySelectorAll('.tab-pane');

  const switchTo = (targetId) => {
    document.body.classList.toggle('dashboard-tab-active', targetId === 'tab-dashboard');

    btns.forEach(b => b.classList.remove('active'));
    panes.forEach(p => p.classList.remove('active'));

    const targetBtn = Array.from(btns).find(b => b.getAttribute('data-target') === targetId);
    if (targetBtn) targetBtn.classList.add('active');

    const targetPane = document.getElementById(targetId);
    if (targetPane) targetPane.classList.add('active');

    const resetScroll = () => {
      window.scrollTo(0, 0);
      document.documentElement.scrollTop = 0;
      document.body.scrollTop = 0;
    };
    resetScroll();
    requestAnimationFrame(() => {
      resetScroll();
      syncStickyOffsets();
      requestAnimationFrame(resetScroll);
    });
    syncStickyOffsets();

    if (targetId === 'tab-dashboard' || targetId === 'tab-video') {
      [120, 320, 700, 1200, 1800].forEach(ms => {
        setTimeout(resetScroll, ms);
      });

      const lockUntil = Date.now() + 1800;
      const onFocusIn = (e) => {
        if (Date.now() > lockUntil) {
          document.removeEventListener('focusin', onFocusIn, true);
          return;
        }
        if (targetPane && targetPane.contains(e.target)) {
          resetScroll();
        }
      };
      document.addEventListener('focusin', onFocusIn, true);
    }
  };

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      switchTo(btn.getAttribute('data-target'));
    });
  });

}

function initHeroRotator() {
  const root = document.querySelector('.hero-rotator');
  if (!root) return;

  const slides = Array.from(root.querySelectorAll('.hero-slide'));
  const dotsWrap = root.querySelector('#hero-dots');
  const prevBtn = root.querySelector('#hero-prev');
  const nextBtn = root.querySelector('#hero-next');
  if (!slides.length || !dotsWrap || !prevBtn || !nextBtn) return;

  let idx = 0;
  let timer = null;
  const intervalMs = 6200;

  const dots = slides.map((_, i) => {
    const b = document.createElement('button');
    b.className = `hero-dot${i === 0 ? ' is-active' : ''}`;
    b.type = 'button';
    b.setAttribute('aria-label', `切換到第 ${i + 1} 張 Banner`);
    b.addEventListener('click', () => {
      goTo(i);
      restartAuto();
    });
    dotsWrap.appendChild(b);
    return b;
  });

  function goTo(next) {
    idx = (next + slides.length) % slides.length;
    slides.forEach((s, i) => s.classList.toggle('is-active', i === idx));
    dots.forEach((d, i) => d.classList.toggle('is-active', i === idx));
  }

  function next() { goTo(idx + 1); }
  function prev() { goTo(idx - 1); }
  function startAuto() { if (!timer) timer = setInterval(next, intervalMs); }
  function stopAuto() { if (timer) { clearInterval(timer); timer = null; } }
  function restartAuto() { stopAuto(); startAuto(); }

  nextBtn.addEventListener('click', () => { next(); restartAuto(); });
  prevBtn.addEventListener('click', () => { prev(); restartAuto(); });

  root.addEventListener('mouseenter', stopAuto);
  root.addEventListener('mouseleave', startAuto);
  root.addEventListener('focusin', stopAuto);
  root.addEventListener('focusout', startAuto);

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopAuto();
    else startAuto();
  });

  startAuto();
}

// ── Market Data ───────────────────────────────────────

/**
 * 繪製 sparkline SVG。
 * @param {SVGElement} svg
 * @param {number[]} values  最近 N 個收盤價
 * @param {string}   color   線條顏色
 */
function drawSparkline(svg, values, color) {
  if (!values || values.length < 2) return;

  const W = 200, H = 46, pad = 3;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const pts = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (W - pad * 2);
    const y = H - pad - ((v - min) / range) * (H - pad * 2);
    return [x, y];
  });

  const polyPts = pts.map(p => p.join(',')).join(' ');
  // Area polygon: close path along bottom
  const areaPts = [
    ...pts,
    [pts[pts.length - 1][0], H - pad],
    [pts[0][0], H - pad],
  ].map(p => p.join(',')).join(' ');

  const gradId = 'spk' + Math.random().toString(36).slice(2, 7);

  svg.innerHTML = `
    <defs>
      <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"   stop-color="${color}" stop-opacity="0.28"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <polygon
      points="${areaPts}"
      fill="url(#${gradId})"
    />
    <polyline
      points="${polyPts}"
      fill="none"
      stroke="${color}"
      stroke-width="1.6"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  `;
}

/**
 * 渲染 ticker 橫幅（CSS marquee）。
 */
function renderTicker(items) {
  const track = document.getElementById('ticker-track');
  if (!track || !items?.length) return;

  const html = items.map(item => {
    const up   = item.change >= 0;
    const sign = up ? '+' : '';
    const cls  = up ? 'up' : 'down';
    return `
      <div class="ticker-item">
        <span class="ti-name">${esc(item.name)}</span>
        <span class="ti-price">${fmtPrice(item.price)}</span>
        <span class="ti-change ${cls}">${sign}${item.change.toFixed(2)}</span>
        <span class="ti-sep">·</span>
        <span class="ti-pct ${cls}">${sign}${item.changePct.toFixed(2)}%</span>
      </div>
    `;
  }).join('');

  // Duplicate for seamless loop
  track.innerHTML = html + html;
}

function renderMarketOverview(items) {
  const root = document.getElementById('market-overview-grid');
  if (!root || !items?.length) return;

  root.innerHTML = items.map(item => {
    const hasPrice = item.price != null && !isNaN(item.price);
    const up = Number(item.change) >= 0;
    const sign = up ? '+' : '';
    const cls = up ? 'market-up' : 'market-down';
    const d = item.decimals ?? 2;
    const status = item.fresh ? '即時/準即時' : '快取/待更新';
    const statusCls = item.fresh ? 'fresh' : 'stale';

    return `
      <article class="market-overview-card ${hasPrice ? '' : 'is-empty'}">
        <div class="market-card-topline">
          <span class="market-card-group">${esc(item.group || item.market || '')}</span>
          <span class="market-card-status ${statusCls}">${status}</span>
        </div>
        <h4 class="market-card-name">${esc(item.name)}</h4>
        <div class="market-card-price">${hasPrice ? fmtPrice(item.price, d) : '—'}</div>
        <div class="market-card-change ${hasPrice ? cls : ''}">
          ${hasPrice ? `${sign}${Number(item.change).toFixed(d)} · ${sign}${Number(item.changePct).toFixed(2)}%` : '資料待補'}
        </div>
        <div class="market-card-date">資料日：${esc(item.date || '—')}</div>
      </article>
    `;
  }).join('');
}

function renderWatchlist(items) {
  const body = document.getElementById('watchlist-body');
  if (!body || !items?.length) return;

  body.innerHTML = items.map(item => {
    const hasPrice = item.price != null && !isNaN(item.price);
    const up = Number(item.change) >= 0;
    const sign = up ? '+' : '';
    const cls = up ? 'market-up' : 'market-down';
    const d = item.decimals ?? 2;
    return `
      <tr class="${item.fresh ? '' : 'is-stale'}">
        <td>
          <span class="watch-name">${esc(item.name)}</span>
          <span class="watch-symbol">${esc(item.symbol || '')}</span>
        </td>
        <td><span class="watch-market">${esc(item.market || '—')}</span></td>
        <td class="num">${hasPrice ? fmtPrice(item.price, d) : '—'}</td>
        <td class="num ${hasPrice ? cls : ''}">
          ${hasPrice ? `${sign}${Number(item.change).toFixed(d)} / ${sign}${Number(item.changePct).toFixed(2)}%` : '—'}
        </td>
        <td>
          <span class="watch-date">${esc(item.date || '—')}</span>
          ${item.fresh ? '' : '<span class="watch-cache">快取</span>'}
        </td>
      </tr>
    `;
  }).join('');
}

/**
 * 渲染總經指標卡片。
 */
function renderMacro(macro) {
  const COLORS = {
    usdtwd: '#60a5fa',
    twse:   '#22c55e',
    brent:  '#fb923c',
    gold:   '#f59e0b',
    copper: '#f97316',
  };

  document.querySelectorAll('.macro-data[data-key]').forEach(el => {
    const key  = el.dataset.key;
    const item = macro[key];
    if (!item) return;

    const up  = item.change >= 0;
    const sign = up ? '+' : '';
    const d   = item.decimals ?? 2;
    const color = el.dataset.color || COLORS[key] || '#888';

    el.querySelector('.macro-price-num').textContent = fmtPrice(item.price, d);

    const chgEl = el.querySelector('.macro-price-chg');
    const chgStr = `${sign}${item.change.toFixed(d)}   ${sign}${item.changePct.toFixed(2)}%`;
    chgEl.textContent = chgStr;
    chgEl.className = `macro-price-chg ${up ? 'market-up' : 'market-down'}`;

    const sparkEl = el.querySelector('.macro-spark');
    if (sparkEl && item.closes?.length >= 2) {
      drawSparkline(sparkEl, item.closes, color);
    }
  });
}

function renderMacroStats(stats) {
  if (!stats) return;

  document.querySelectorAll('.macro-stat-item[data-stat-key]').forEach(el => {
    const key = el.dataset.statKey;
    const item = stats[key];
    if (!item) return;

    const valueEl = el.querySelector('.macro-stat-value');
    const dateEl = el.querySelector('.macro-stat-date');
    if (!valueEl || !dateEl) return;

    const d = item.decimals ?? 2;
    const unit = item.unit ? ` ${item.unit}` : '';
    valueEl.textContent = `${fmtStatValue(item.value, d)}${unit}`;
    dateEl.textContent = `更新：${item.date || '—'}${item.fresh === false ? '（快取）' : ''}`;
  });
}

/**
 * 載入市場數據，渲染 ticker 和 macro 卡片。
 * 每 5 分鐘自動刷新。
 */
async function loadMarketData() {
  try {
    const res = await fetch('/api/market-data');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.overview?.length) renderMarketOverview(data.overview);
    if (data.watchlist?.length) renderWatchlist(data.watchlist);
    if (data.ticker?.length) renderTicker(data.ticker);
    if (data.macro)          renderMacro(data.macro);
    if (data.macroStats)     renderMacroStats(data.macroStats);

    // 更新時間標籤
    const noteEl = document.getElementById('macro-update-time');
    if (noteEl && data.ts) {
      noteEl.textContent = `資料來源：Stooq + 官方機構 · 更新 ${formatMarketTime(data.ts)}${data.stale ? ' · 使用快取' : ''}`;
    }
    const freshEl = document.getElementById('market-freshness');
    if (freshEl && data.ts) {
      freshEl.textContent = `資料來源：Stooq + TradingView · 更新 ${formatMarketTime(data.ts)}${data.stale ? ' · 使用快取' : ''}`;
    }
  } catch (err) {
    console.warn('[market-data]', err.message);
  }
}

// ── Video Hub — 動態更新影音專區 ──────────────────────

function escVid(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatVideoDate(dateStr) {
  if (!dateStr) return '';
  const [, m, d] = dateStr.split('-');
  return `${parseInt(m)} 月 ${parseInt(d)} 日`;
}

async function initVideos() {
  const featuredContainer = document.getElementById('video-featured-container');
  const gridContainer     = document.getElementById('video-grid-container');
  if (!featuredContainer) return;

  try {
    const res = await fetch('/data/videos.json');
    if (!res.ok) throw new Error('no videos.json');
    const { videos } = await res.json();
    if (!videos || !videos.length) return;

    // ── 主推影片（最新，嵌入播放器）────────────────────
    const latest = videos[0];
    const vid    = encodeURIComponent(latest.video_id);
    featuredContainer.innerHTML = `
      <div class="yt-embed-container">
        <iframe
          src="https://www.youtube.com/embed/${vid}?rel=0&modestbranding=1&autoplay=0"
          title="${escVid(latest.title)}"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowfullscreen
        ></iframe>
      </div>
      <div class="yt-featured-meta">
        <span class="yt-featured-date">${escVid(formatVideoDate(latest.date))}</span>
        <h4 class="yt-featured-title">${escVid(latest.title)}</h4>
        <a class="yt-featured-link" href="https://www.youtube.com/watch?v=${vid}" target="_blank" rel="noopener noreferrer">在 YouTube 觀看 ↗</a>
      </div>`;

    // 更新副標題
    const descEl = document.querySelector('#tab-video .yt-channel-desc');
    if (descEl) {
      descEl.textContent = `最新影片：${latest.date}　·　每日 AI 自動生成財經解析短影音`;
    }

    // ── 過往影片 grid（第 2 筆以後）─────────────────────
    if (videos.length > 1) {
      const items = videos.slice(1).map(v => {
        const vid2 = encodeURIComponent(v.video_id);
        return `
          <a class="yt-past-item" href="https://www.youtube.com/watch?v=${vid2}" target="_blank" rel="noopener noreferrer">
            <div class="yt-past-thumb">
              <img src="https://img.youtube.com/vi/${vid2}/mqdefault.jpg" alt="${escVid(v.title)}" loading="lazy">
              <div class="yt-past-play">▶</div>
            </div>
            <div class="yt-past-info">
              <span class="yt-past-date">${escVid(formatVideoDate(v.date))}</span>
              <div class="yt-past-title">${escVid(v.title)}</div>
            </div>
          </a>`;
      }).join('');

      gridContainer.innerHTML = `
        <h4 class="yt-past-heading">過往影片</h4>
        <div class="yt-past-grid">${items}</div>`;
    }
  } catch {
    // fallback — 維持 HTML 中的頻道播放清單嵌入
  }
}

// ── AI 觀點驗證 Widget ────────────────────────────────

function renderAccuracyRow(label, stats) {
  return `
    <div class="acc-row">
      <div class="acc-row-head">
        <span class="acc-row-label">${label}</span>
        <span class="acc-row-summary">偏多 ${stats.bullish_pct}% · 中立 ${stats.neutral_pct}% · 偏空 ${stats.bearish_pct}%</span>
      </div>
      <div class="acc-stack">
        <div class="acc-seg bull" style="width:${stats.bullish_pct}%"></div>
        <div class="acc-seg neut" style="width:${stats.neutral_pct}%"></div>
        <div class="acc-seg bear" style="width:${stats.bearish_pct}%"></div>
      </div>
    </div>`;
}

async function loadAccuracy(options = {}) {
  try {
    const url = options.bustCache
      ? `/data/accuracy.json?t=${Date.now()}`
      : '/data/accuracy.json';
    const res = await fetch(url, { cache: options.bustCache ? 'no-store' : 'default' });
    if (!res.ok) return;
    const d = await res.json();

    const rowsEl = document.getElementById('acc-rows');
    const updEl = document.getElementById('acc-updated');
    if (!rowsEl) return;

    if (d.last_updated) {
      const [, m, dd] = d.last_updated.split('-');
      updEl.textContent = `更新 ${m}/${dd}`;
    }

    const total = d.record_count ?? 0;
    const combined = {
      bullish_pct: d.bullish_pct ?? 0,
      neutral_pct: d.neutral_pct ?? 0,
      bearish_pct: d.bearish_pct ?? 0,
    };
    const technical = d.technical || combined;
    const macro = d.macro || combined;

    rowsEl.innerHTML = total === 0 ? `<div style="color:var(--text-3);font-size:.75rem">資料累積中</div>` : `
      <div class="acc-row-list">
        ${renderAccuracyRow('技術面', technical)}
        ${renderAccuracyRow('總經面', macro)}
      </div>
      <div class="acc-legend">
        <span class="acc-legend-item"><span class="acc-dot bull"></span>偏多</span>
        <span class="acc-legend-item"><span class="acc-dot neut"></span>中立</span>
        <span class="acc-legend-item"><span class="acc-dot bear"></span>偏空</span>
        <span class="acc-legend-item" style="margin-left:auto">近 ${total} 日</span>
      </div>`;
  } catch {
    // 靜默失敗，不影響主頁面
  }
}

// ── Init ─────────────────────────────────────────────

async function init() {
  document.getElementById('header-date').textContent = todayTW();
  syncStickyOffsets();
  window.addEventListener('resize', syncStickyOffsets);
  window.addEventListener('orientationchange', syncStickyOffsets);
  requestAnimationFrame(syncStickyOffsets);
  setTimeout(syncStickyOffsets, 300);
  setTimeout(syncStickyOffsets, 1200);

  initTabs();
  initHeroRotator();
  initVideos();

  // 載入文章列表
  try {
    const { articles } = await fetchIndex();
    renderList(articles || []);
  } catch (err) {
    console.error(err);
    document.getElementById('article-list').innerHTML =
      `<p style="color:var(--text-2);font-size:.88rem;padding:1rem 0">資料載入失敗，請稍後再試。</p>`;
  }

  // 載入 AI 觀點驗證
  loadAccuracy();

  // 載入市場數據（不阻塞）
  loadMarketData();

  // 每 5 分鐘自動刷新
  setInterval(loadMarketData, 5 * 60 * 1000);
  setInterval(() => loadAccuracy({ bustCache: true }), 5 * 60 * 1000);
}

document.addEventListener('DOMContentLoaded', init);
