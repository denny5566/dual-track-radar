/**
 * 財經雷達 — 文章頁 (article.html)
 *
 * URL 格式：article.html?date=20260416
 * 讀取 /data/{dateKey}.json 後渲染文章。
 */

// ── URL 解析 ──────────────────────────────────────────

function getDateKey() {
  return new URLSearchParams(location.search).get('date') || '';
}

// ── 資料讀取 ──────────────────────────────────────────

async function fetchArticle(dateKey) {
  if (dateKey) {
    const r = await fetch(`/data/${dateKey}.json`);
    if (r.ok) return r.json();
  }
  // fallback → latest
  const r = await fetch('/data/latest.json');
  if (r.ok) return r.json();
  throw new Error('文章資料讀取失敗');
}

// ── 日期工具 ──────────────────────────────────────────

function formatDateTW(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  return `${d.getFullYear()} 年 ${d.getMonth() + 1} 月 ${d.getDate()} 日`;
}

function estimateReadingTime(text) {
  const chars = String(text || '').replace(/\s/g, '').length;
  return `閱讀約 ${Math.max(1, Math.ceil(chars / 380))} 分鐘`;
}

// ── 閱讀進度 ──────────────────────────────────────────

function initProgress() {
  const bar = document.getElementById('reading-progress');
  if (!bar) return;
  window.addEventListener('scroll', () => {
    const pct = document.documentElement.scrollHeight - innerHeight;
    bar.style.width = pct > 0 ? `${Math.min(100, (scrollY / pct) * 100)}%` : '0%';
  }, { passive: true });
}

// ── Sentiment 分類 ────────────────────────────────────

function sentimentClass(s = '') {
  if (/多|牛|樂觀/.test(s)) return 'bull';
  if (/空|熊|悲觀/.test(s)) return 'bear';
  return '';
}

// ── XSS ──────────────────────────────────────────────

function esc(v) {
  return String(v ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── 主渲染 ────────────────────────────────────────────

function loadCoverImage(dateKey) {
  const figure = document.getElementById('article-cover');
  const img    = document.getElementById('cover-img');
  if (!figure || !img || !dateKey) return;

  figure.hidden = false;
  img.src = `/images/${dateKey}.jpg`;
  img.onerror = () => { figure.hidden = true; };
}

function render(data) {
  const article = data.article || buildFallback(data);
  const dateStr = data.meta?.date || new Date().toISOString().slice(0, 10);

  // <title>
  document.title = '財經雷達';

  // Header date — 永遠顯示今天的日期
  document.getElementById('header-date').textContent = formatDateTW(new Date().toLocaleDateString('sv-SE'));

  // Kicker
  document.getElementById('kicker-date').textContent = formatDateTW(dateStr);

  // Headline
  document.getElementById('article-headline').textContent = article.title || '今日市場速報';

  // Reading time (計算全文字數)
  const allText = (article.sections || []).map(s => s.content).join('');
  document.getElementById('reading-time').textContent = estimateReadingTime(allText);

  // Body
  renderBody(article, data.investor_reminder, data.top5_news || []);

  // Sidebar
  renderSidebar(data.comparison, data.top5_news || [], data._relatedArticles || []);

  // Tags
  renderTags(article.tags);
}

function renderBody(article, reminder, top5) {
  const el = document.getElementById('article-content');
  let html = '';

  (article.sections || []).forEach(sec => {
    html += `<h2>${esc(sec.heading)}</h2>`;
    const paras = sec.content.split(/\n{2,}/).filter(p => p.trim());
    (paras.length ? paras : [sec.content]).forEach(p => {
      html += `<p>${esc(p.trim())}</p>`;
    });
  });

  if (reminder) {
    html += `<div class="reminder-block">
      <strong>市場提醒：</strong>${esc(reminder)}
    </div>`;
  }

  if (top5.length) {
    html += `<div class="top5-section"><h2>今日 5 大市場新聞</h2>
      <ol class="top5-list">`;
    top5.slice(0, 5).forEach((item, i) => {
      html += `<li class="top5-item">
        <span class="top5-num${i === 0 ? ' n1' : ''}">${String(i + 1).padStart(2, '0')}</span>
        <div class="top5-info">
          <div class="top5-headline">${esc(item.headline || '')}</div>
          ${item.summary ? `<div class="top5-summary">${esc(item.summary)}</div>` : ''}
        </div>
      </li>`;
    });
    html += `</ol></div>`;
  }

  el.innerHTML = html;
}

function renderSidebar(comparison, top5, relatedArticles = []) {
  const el = document.getElementById('sidebar');
  let html = '';

  const views = [
    { d: comparison?.capital_futures, label: '技術面觀察' },
    { d: comparison?.yu_ting_hao,     label: '宏觀基本面' },
  ].filter(v => v.d);

  views.forEach(({ d, label }) => {
    const sc    = sentimentClass(d.sentiment || '');
    const scCls = sc ? ` ${sc}` : '';
    const points = (d.main_points || []).slice(0, 3)
      .map(p => `<div class="sc-point">${esc(p.slice(0, 100))}${p.length > 100 ? '…' : ''}</div>`)
      .join('');

    html += `
      <div class="sidebar-card">
        <div class="sc-label">${esc(label)}</div>
        ${d.sentiment ? `<span class="sc-sentiment${scCls}">${esc(d.sentiment)}</span>` : ''}
        ${d.key_levels ? `<div class="sc-key">${esc(d.key_levels.slice(0, 120))}${d.key_levels.length > 120 ? '…' : ''}</div>` : ''}
        <div class="sc-points">${points}</div>
      </div>`;
  });

  if (top5.length) {
    const items = top5.slice(0, 5).map((n, i) => `
      <div class="sc-news-item">
        <span class="sc-news-rank">${i + 1}</span>
        <span class="sc-news-title">${esc(n.headline || '')}</span>
      </div>`).join('');
    html += `
      <div class="sidebar-card">
        <div class="sc-label">今日重點</div>
        <div class="sc-news">${items}</div>
      </div>`;
  }

  // 推薦文章
  if (relatedArticles.length) {
    const currentDate = getDateKey();
    const others = relatedArticles
      .filter(a => (a.date || '').replace(/-/g, '') !== currentDate)
      .slice(0, 5);
    if (others.length) {
      const items = others.map(a => {
        const dateKey = (a.date || '').replace(/-/g, '');
        const d = new Date((a.date || '') + 'T00:00:00');
        const dateLabel = a.date
          ? `${d.getMonth() + 1}/${d.getDate()}`
          : '';
        return `<a class="related-article-item" href="/article.html?date=${esc(dateKey)}">
          <span class="related-date">${esc(dateLabel)}</span>
          <span class="related-title">${esc(a.title || '每日市場速報')}</span>
        </a>`;
      }).join('');
      html += `
        <div class="sidebar-card">
          <div class="sc-label">推薦文章</div>
          <div class="related-articles">${items}</div>
        </div>`;
    }
  }

  el.innerHTML = html;
}

function renderTags(tags = []) {
  const el = document.getElementById('tags-row');
  el.innerHTML = tags.map(t => `<span class="tag">${esc(t)}</span>`).join('');
}

// ── Fallback（舊格式無 article 欄位）────────────────────

function buildFallback(data) {
  return {
    title:    (data.outputs?.edm_subject || '').replace(/^【.*?】\s*/, '') || '今日市場速報',
    sections: [
      { heading: '今日焦點',    content: data.daily_focus    || '摘要生成中…' },
      { heading: '雙軌觀點統整', content: data.clash_or_sync || '分析進行中…' },
    ],
    tags: ['#台股', '#美股', '#財經雷達'],
  };
}

// ── 分享功能 ──────────────────────────────────────────────

function initShare() {
  const url = encodeURIComponent(location.href);

  const lineBtn = document.getElementById('share-line');
  if (lineBtn) {
    lineBtn.href = `https://social-plugins.line.me/lineit/share?url=${url}`;
  }

  const fbBtn = document.getElementById('share-fb');
  if (fbBtn) {
    fbBtn.href = `https://www.facebook.com/sharer/sharer.php?u=${url}`;
  }

  const copyBtn = document.getElementById('share-copy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(location.href);
        const orig = copyBtn.innerHTML;
        copyBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg> 已複製`;
        copyBtn.classList.add('copied');
        setTimeout(() => {
          copyBtn.innerHTML = orig;
          copyBtn.classList.remove('copied');
        }, 2000);
      } catch {
        prompt('複製以下連結：', location.href);
      }
    });
  }
}

// ── AI Chat Drawer ────────────────────────────────────────

let _articleContext = '';   // 保存當日文章內容，作為 AI 上下文

function buildContext(data) {
  const article = data.article || buildFallback(data);
  const parts = [
    `日期：${data.meta?.date || ''}`,
    `標題：${article.title || ''}`,
    `今日焦點：${data.daily_focus || ''}`,
    ...(article.sections || []).map(s => `${s.heading}：${s.content}`),
    data.clash_or_sync ? `觀點統整：${data.clash_or_sync}` : '',
    data.investor_reminder ? `投資提醒：${data.investor_reminder}` : '',
    ...(data.top5_news || []).map((n, i) => `新聞${i + 1}：${n.headline} — ${n.summary || ''}`),
  ].filter(Boolean);
  return parts.join('\n');
}

function openDrawer() {
  document.getElementById('ai-drawer').classList.add('open');
  document.getElementById('ai-overlay').classList.add('open');
  document.getElementById('ai-input').focus();
}

function closeDrawer() {
  document.getElementById('ai-drawer').classList.remove('open');
  document.getElementById('ai-overlay').classList.remove('open');
}

function appendMessage(role, text) {
  const el = document.createElement('div');
  el.className = `ai-msg ${role}`;
  el.textContent = text;
  const container = document.getElementById('ai-messages');
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
  return el;
}

async function sendChat(question) {
  if (!question.trim()) return;

  const sendBtn = document.getElementById('ai-send');
  const input   = document.getElementById('ai-input');
  const suggestions = document.getElementById('ai-suggestions');

  // 隱藏建議列
  suggestions.style.display = 'none';

  sendBtn.disabled = true;
  input.value = '';
  input.style.height = 'auto';

  appendMessage('user', question);
  const thinkingEl = appendMessage('thinking', '分析中…');

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, context: _articleContext }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { answer } = await res.json();

    thinkingEl.className = 'ai-msg assistant';
    thinkingEl.textContent = answer;
  } catch (err) {
    thinkingEl.className = 'ai-msg assistant';
    thinkingEl.textContent = '抱歉，目前無法連線到 AI 服務，請稍後再試。';
    console.error('AI chat error:', err);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function initDrawer() {
  const fab     = document.getElementById('fab');
  const overlay = document.getElementById('ai-overlay');
  const closeBtn = document.getElementById('ai-close');
  const sendBtn  = document.getElementById('ai-send');
  const input    = document.getElementById('ai-input');

  fab.addEventListener('click', openDrawer);
  overlay.addEventListener('click', closeDrawer);
  closeBtn.addEventListener('click', closeDrawer);

  // Escape 關閉
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeDrawer();
  });

  // 送出按鈕
  sendBtn.addEventListener('click', () => sendChat(input.value));

  // Enter 送出（Shift+Enter 換行）
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChat(input.value);
    }
  });

  // 自動調整高度
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  });

  // 建議按鈕
  document.querySelectorAll('.ai-suggestion-btn').forEach(btn => {
    btn.addEventListener('click', () => sendChat(btn.textContent));
  });
}

// ── Market Ticker ──────────────────────────────────────

function fmtPrice(price, decimals = 2) {
  if (price == null || isNaN(price)) return '—';
  return price.toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

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

  track.innerHTML = html + html;
}

async function loadMarketData() {
  try {
    const res = await fetch('/api/market-data');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data.ticker?.length) renderTicker(data.ticker);
  } catch (err) {
    console.warn('Ticker load failed:', err);
  }
}

// ── Init ─────────────────────────────────────────────

async function init() {
  initProgress();
  initDrawer();
  initShare();
  loadMarketData();

  try {
    const dateKey = getDateKey();

    // 並行載入文章與文章列表（用於推薦文章）
    const [data, indexData] = await Promise.allSettled([
      fetchArticle(dateKey),
      fetch('/data/index.json').then(r => r.ok ? r.json() : []),
    ]);

    if (data.status === 'rejected') throw data.reason;

    const article = data.value;
    _articleContext = buildContext(article);

    // 把文章列表附加到 data 供 render 使用
    article._relatedArticles = indexData.status === 'fulfilled' ? (indexData.value || []) : [];

    const resolvedKey = dateKey || (article.meta?.date || '').replace(/-/g, '');
    setTimeout(() => {
      render(article);
      loadCoverImage(resolvedKey);
    }, 250);
  } catch (err) {
    console.error(err);
    document.getElementById('article-headline').textContent = '文章載入失敗';
    document.getElementById('article-content').innerHTML =
      `<p style="color:var(--text-2)">無法讀取資料，請確認 data/ 目錄中有對應的 JSON 檔案。</p>`;
  }
}

document.addEventListener('DOMContentLoaded', init);
