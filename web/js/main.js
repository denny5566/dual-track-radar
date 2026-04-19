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

// ── Tab Switching ─────────────────────────────────────

function initTabs() {
  const btns  = document.querySelectorAll('.tab-btn');
  const panes = document.querySelectorAll('.tab-pane');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const targetPane = document.getElementById(btn.getAttribute('data-target'));
      if (targetPane) targetPane.classList.add('active');

      const resetScroll = () => {
        window.scrollTo(0, 0);
        document.documentElement.scrollTop = 0;
        document.body.scrollTop = 0;
      };
      resetScroll();
      requestAnimationFrame(() => {
        resetScroll();
        requestAnimationFrame(resetScroll);
      });
    });
  });
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

/**
 * 渲染總經指標卡片。
 */
function renderMacro(macro) {
  const COLORS = {
    vix:   '#ef4444',
    us10y: '#eab308',
    dxy:   '#2962ff',
    gold:  '#f59e0b',
    wti:   '#f97316',
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

/**
 * 載入市場數據，渲染 ticker 和 macro 卡片。
 * 每 5 分鐘自動刷新。
 */
async function loadMarketData() {
  try {
    const res = await fetch('/api/market-data');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.ticker?.length) renderTicker(data.ticker);
    if (data.macro)          renderMacro(data.macro);

    // 更新時間標籤
    const noteEl = document.getElementById('macro-update-time');
    if (noteEl && data.ts) {
      const t = new Date(data.ts);
      const hh = String(t.getHours()).padStart(2, '0');
      const mm = String(t.getMinutes()).padStart(2, '0');
      noteEl.textContent = `資料來源：Yahoo Finance · 更新 ${hh}:${mm}`;
    }
  } catch (err) {
    console.warn('[market-data]', err.message);
  }
}

// ── Video Hub — 動態更新影音專區 ──────────────────────

async function initVideos() {
  // 嘗試從 latest.json 讀取最新 YouTube video_id，更新嵌入式播放器
  const iframe = document.querySelector('#tab-video .yt-embed-container iframe');
  if (!iframe) return;

  try {
    const res = await fetch('/data/latest.json');
    if (!res.ok) return;
    const data = await res.json();

    if (data.youtube_video_id) {
      const vid = encodeURIComponent(data.youtube_video_id);
      iframe.src = `https://www.youtube.com/embed/${vid}?rel=0&modestbranding=1`;

      // 更新說明文字以顯示最新影片日期
      const descEl = document.querySelector('#tab-video .yt-channel-desc');
      if (descEl && data.meta?.date) {
        descEl.textContent =
          `最新影片：${data.meta.date}　·　每日 AI 自動生成財經解析短影音 · 台股 & 美股動態觀察 · 訂閱免費收看`;
      }
    }
  } catch {
    // 靜默 fallback — 維持 HTML 中的頻道播放清單嵌入
  }
}

// ── Init ─────────────────────────────────────────────

async function init() {
  document.getElementById('header-date').textContent = todayTW();
  initTabs();
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

  // 載入市場數據（不阻塞）
  loadMarketData();

  // 每 5 分鐘自動刷新
  setInterval(loadMarketData, 5 * 60 * 1000);
}

document.addEventListener('DOMContentLoaded', init);
