/**
 * 財經雷達 — 首頁 (index.html)
 * 讀取 index.json，渲染文章列表。
 */

// ── 日期工具 ──────────────────────────────────────────

function todayTW() {
  const d = new Date();
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}

function formatDateShort(dateStr) {
  // "2026-04-16" → "04 / 16"
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

// ── 取得資料 ──────────────────────────────────────────

async function fetchIndex() {
  const res = await fetch('/data/index.json');
  if (!res.ok) throw new Error('index.json 讀取失敗');
  return res.json();
}

// ── 渲染 ─────────────────────────────────────────────

function renderList(articles) {
  const root = document.getElementById('article-list');
  if (!articles.length) {
    root.innerHTML = '<p style="color:var(--text-2);font-size:.88rem;padding:1rem 0">尚無文章</p>';
    return;
  }

  // 依月份分組
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
      const dateShort   = formatDateShort(a.date);
      const weekday     = getWeekdayTW(a.date);
      const tagsHtml    = (a.tags || []).slice(0, 4)
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

// ── XSS ──────────────────────────────────────────────

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Tab Switching Logic ─────────────────────────────────

function initTabs() {
  const btns = document.querySelectorAll('.tab-btn');
  const panes = document.querySelectorAll('.tab-pane');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      // Remove active from all
      btns.forEach(b => b.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));

      // Add active to clicked
      btn.classList.add('active');
      const targetId = btn.getAttribute('data-target');
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add('active');
      }
    });
  });
}

// ── Video Hub Logic ──────────────────────────────────────

async function initVideos() {
  const container = document.getElementById('video-accordion');
  if (!container) return;

  // Simulate fetching video data
  const mockVideos = [
    { title: "2026-04-16 AI 雙軌財經解析短影音", date: "2026-04-16", url: "#" },
    { title: "2026-04-15 台積電法說會前瞻短評", date: "2026-04-15", url: "#" }
  ];

  let html = '';
  mockVideos.forEach((v, i) => {
    html += `
      <div class="accordion-item">
        <div class="accordion-header" onclick="this.parentElement.classList.toggle('active')">
          <span>${esc(v.date)} - ${esc(v.title)}</span>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M6 9l6 6 6-6"/></svg>
        </div>
        <div class="accordion-content">
          <div style="background:#111; padding:2rem; text-align:center; border-radius:6px; margin-top:1rem; border:1px solid rgba(255,255,255,0.1)">
             <p style="color:var(--text-2); margin-bottom:1rem;">🎥 此區域將置入生成的短影音播放器</p>
             <button class="tab-btn" style="display:inline-block">▶ 播放影片</button>
          </div>
        </div>
      </div>
    `;
  });

  container.innerHTML = html;
}

// ── Init ─────────────────────────────────────────────

async function init() {
  document.getElementById('header-date').textContent = todayTW();
  initTabs();
  initVideos();

  try {
    const { articles } = await fetchIndex();
    renderList(articles || []);
  } catch (err) {
    console.error(err);
    document.getElementById('article-list').innerHTML =
      `<p style="color:var(--text-2);font-size:.88rem;padding:1rem 0">資料載入失敗，請稍後再試。</p>`;
  }
}

document.addEventListener('DOMContentLoaded', init);
