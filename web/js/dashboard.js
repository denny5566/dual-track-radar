/**
 * 財經雷達 — 個人儀表板 (d.html)
 * 社群流量整合 + 文字探勘 + AI 分析聊天
 */

// ── 密碼驗證 ──────────────────────────────────────────────────────────────────
// 密碼存在 localStorage，可在 .env 中設定 DASHBOARD_PASS 對應值
// 預設密碼：radar2026（上線後請修改）
const DASH_PASS_KEY = 'radar_dash_auth';
const CORRECT_PASS = '1234'; // ← 請修改為您自己的密碼

function checkAuth() {
  if (localStorage.getItem(DASH_PASS_KEY) === CORRECT_PASS) {
    showDashboard();
  }
}

function showDashboard() {
  document.getElementById('auth-gate').style.display = 'none';
  document.getElementById('dash-content').hidden = false;
  init();
}

document.getElementById('auth-btn').addEventListener('click', () => {
  const val = document.getElementById('auth-input').value;
  if (val === CORRECT_PASS) {
    localStorage.setItem(DASH_PASS_KEY, val);
    showDashboard();
  } else {
    document.getElementById('auth-error').hidden = false;
  }
});
document.getElementById('auth-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') document.getElementById('auth-btn').click();
});

checkAuth();

// ── 數字格式化 ────────────────────────────────────────────────────────────────
function fmtNum(n) {
  if (n == null || n === '') return '—';
  const num = parseInt(n, 10);
  if (isNaN(num)) return '—';
  if (num >= 1_000_000) return (num / 1_000_000).toFixed(1) + 'M';
  if (num >= 1_000) return (num / 1_000).toFixed(1) + 'K';
  return num.toLocaleString();
}

function setStatus(el, text, cls = '') {
  el.textContent = text;
  el.className = `stat-status${cls ? ' ' + cls : ''}`;
}

// ── YouTube 數據 ──────────────────────────────────────────────────────────────
async function loadYouTubeStats() {
  const statusEl = document.getElementById('yt-status');
  try {
    const res = await fetch('/api/social-stats?platform=youtube');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.error) throw new Error(data.error);

    document.getElementById('yt-subs').textContent = fmtNum(data.subscribers);
    document.getElementById('yt-views').textContent = fmtNum(data.totalViews);
    document.getElementById('yt-videos').textContent = fmtNum(data.videoCount);

    if (data.latestVideo) {
      document.getElementById('yt-latest').innerHTML =
        `<strong>最新影片：</strong>${esc(data.latestVideo.title)}<br>` +
        `<span style="font-size:0.72rem;color:var(--text-3)">${esc(data.latestVideo.publishedAt?.slice(0, 10) || '')}</span>`;
    }
    setStatus(statusEl, '即時', 'live');

    // 渲染最新影片列表
    if (data.recentVideos?.length) {
      renderRecentVideos(data.recentVideos);
    }
  } catch (err) {
    setStatus(statusEl, '無法載入', 'error');
    console.error('YouTube stats error:', err);
  }
}

function renderRecentVideos(videos) {
  const container = document.getElementById('recent-videos');
  container.innerHTML = videos.slice(0, 3).map(v => {
    const thumb = v.thumbnail || `https://img.youtube.com/vi/${v.videoId}/mqdefault.jpg`;
    return `
      <a class="video-card" href="https://www.youtube.com/watch?v=${esc(v.videoId)}" target="_blank" rel="noopener">
        <div class="video-thumb-wrap">
          <img src="${esc(thumb)}" alt="${esc(v.title)}" loading="lazy">
          <div class="video-play-overlay">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>
          </div>
        </div>
        <div class="video-info">
          <div class="video-title">${esc(v.title)}</div>
          <div class="video-meta">${esc(v.publishedAt?.slice(0, 10) || '')}
            ${v.viewCount ? ` · ${fmtNum(v.viewCount)} 次觀看` : ''}</div>
        </div>
      </a>`;
  }).join('');
}

// ── Instagram 數據（需 IG Graph API Token）────────────────────────────────────
async function loadInstagramStats() {
  const statusEl = document.getElementById('ig-status');
  try {
    const res = await fetch('/api/social-stats?platform=instagram');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.notConfigured) {
      setStatus(statusEl, '需要設定');
      return;
    }
    if (data.error) throw new Error(data.error);

    document.getElementById('ig-followers').textContent = fmtNum(data.followers);
    document.getElementById('ig-posts').textContent = fmtNum(data.mediaCount);
    document.getElementById('ig-reach').textContent = fmtNum(data.reach) || '—';
    document.getElementById('ig-hint').style.display = 'none';
    setStatus(statusEl, '即時', 'live');
  } catch (err) {
    setStatus(statusEl, '無法載入', 'error');
    console.error('Instagram stats error:', err);
  }
}

// ── Threads 數據（需 Threads API Token）──────────────────────────────────────
async function loadThreadsStats() {
  const statusEl = document.getElementById('threads-status');
  try {
    const res = await fetch('/api/social-stats?platform=threads');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.notConfigured) {
      setStatus(statusEl, '需要設定');
      return;
    }
    if (data.error) throw new Error(data.error);

    document.getElementById('threads-followers').textContent = fmtNum(data.followers);
    document.getElementById('threads-posts').textContent = fmtNum(data.postCount);
    document.getElementById('threads-replies').textContent = fmtNum(data.replyCount) || '—';
    document.getElementById('threads-hint').style.display = 'none';
    setStatus(statusEl, '即時', 'live');
  } catch (err) {
    setStatus(statusEl, '無法載入', 'error');
    console.error('Threads stats error:', err);
  }
}

// ── XSS helper ───────────────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ── Simple Markdown → HTML（僅供信任的 AI 回應使用）──────────────────────────
function mdToHtml(text) {
  return esc(text)
    // ## 標題
    .replace(/^## (.+)$/gm, '<strong class="md-h2">$1</strong>')
    // ### 標題
    .replace(/^### (.+)$/gm, '<strong class="md-h3">$1</strong>')
    // **粗體**
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // *斜體*
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // - 列表項
    .replace(/^- (.+)$/gm, '<span class="md-li">·&nbsp;$1</span>')
    // 換行
    .replace(/\n/g, '<br>');
}

// ── 文字探勘（Mining Tab）────────────────────────────────────────────────────
let _miningSource = 'youtube';
let _miningComments = [];

function initMiningTabs() {
  document.querySelectorAll('.mining-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.mining-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.mining-source-pane').forEach(p => {
        p.classList.remove('active');
        p.hidden = true;
      });
      tab.classList.add('active');
      _miningSource = tab.dataset.source;
      const pane = document.getElementById(`source-${_miningSource}`);
      if (pane) { pane.hidden = false; pane.classList.add('active'); }
    });
  });

  // YouTube comment fetch
  document.getElementById('yt-fetch-btn').addEventListener('click', async () => {
    const videoId = document.getElementById('yt-video-id').value.trim();
    if (!videoId) return;
    const btn = document.getElementById('yt-fetch-btn');
    btn.textContent = '抓取中…';
    btn.disabled = true;
    try {
      const res = await fetch(`/api/social-stats?platform=youtube-comments&videoId=${encodeURIComponent(videoId)}`);
      const data = await res.json();
      if (data.error) throw new Error(data.error);
      _miningComments = data.comments || [];
      const preview = document.getElementById('yt-comments-preview');
      preview.hidden = false;
      preview.innerHTML = _miningComments.slice(0, 10).map(c =>
        `<div class="comment-item">${esc(c)}</div>`
      ).join('');
    } catch (err) {
      alert(`抓取失敗：${err.message}`);
    } finally {
      btn.textContent = '抓取留言';
      btn.disabled = false;
    }
  });
}

async function analyzeComments() {
  const btn = document.getElementById('analyze-comments-btn');
  btn.disabled = true;
  btn.textContent = '分析中…';

  let comments = [];
  if (_miningSource === 'paste') {
    const text = document.getElementById('paste-comments').value.trim();
    comments = text.split('\n').filter(l => l.trim());
  } else {
    comments = _miningComments;
  }

  if (!comments.length) {
    alert('請先輸入或抓取留言內容');
    btn.disabled = false;
    btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/></svg> 分析留言';
    return;
  }

  try {
    const res = await fetch('/api/dashboard-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: 'mining',
        platform: _miningSource,
        comments: comments.slice(0, 100), // 最多 100 則
      }),
    });
    const data = await res.json();
    const resultEl = document.getElementById('mining-result');
    resultEl.hidden = false;
    resultEl.innerHTML = mdToHtml(data.answer || '分析失敗，請稍後再試');
  } catch (err) {
    alert(`分析失敗：${err.message}`);
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3H5a2 2 0 0 0-2 2v4m6-6h10a2 2 0 0 1 2 2v4M9 3v18m0 0h10a2 2 0 0 0 2-2V9M9 21H5a2 2 0 0 1-2-2V9m0 0h18"/></svg> 分析留言';
  }
}

document.getElementById('analyze-comments-btn').addEventListener('click', analyzeComments);

// ── AI Analytics Chat ─────────────────────────────────────────────────────────
let _chatStats = {}; // 會話中記憶的統計數據

function appendDashMsg(role, text) {
  const el = document.createElement('div');
  el.className = `ai-msg ${role}`;
  el.textContent = text;
  const container = document.getElementById('dash-messages');
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
  return el;
}

async function sendDashChat(question) {
  if (!question.trim()) return;

  const sendBtn = document.getElementById('dash-send-btn');
  const input = document.getElementById('dash-chat-input');

  // 隱藏建議列
  document.querySelector('.dash-suggestions').style.display = 'none';

  sendBtn.disabled = true;
  input.value = '';
  input.style.height = 'auto';

  appendDashMsg('user', question);
  const thinkingEl = appendDashMsg('thinking', '分析中…');

  try {
    const res = await fetch('/api/dashboard-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode: 'chat',
        question,
        statsContext: _chatStats,
      }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { answer } = await res.json();
    thinkingEl.className = 'ai-msg assistant';
    thinkingEl.textContent = answer;
  } catch {
    thinkingEl.className = 'ai-msg assistant';
    thinkingEl.textContent = '抱歉，目前無法連線到 AI 服務，請稍後再試。';
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

function initDashChat() {
  const sendBtn = document.getElementById('dash-send-btn');
  const input = document.getElementById('dash-chat-input');

  sendBtn.addEventListener('click', () => sendDashChat(input.value));
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendDashChat(input.value); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  });

  document.querySelectorAll('.dash-suggestion-btn').forEach(btn => {
    btn.addEventListener('click', () => sendDashChat(btn.dataset.q || btn.textContent));
  });
}

// ── Refresh ───────────────────────────────────────────────────────────────────
document.getElementById('refresh-btn').addEventListener('click', async () => {
  const btn = document.getElementById('refresh-btn');
  btn.classList.add('spinning');
  await loadAllStats();
  btn.classList.remove('spinning');
});

async function loadAllStats() {
  const [ytData] = await Promise.allSettled([
    loadYouTubeStats(),
    loadInstagramStats(),
    loadThreadsStats(),
  ]);
  // 記憶統計數據供 AI 聊天使用
  try {
    const res = await fetch('/api/social-stats?platform=youtube');
    if (res.ok) _chatStats.youtube = await res.json();
  } catch { /* silent */ }
}

// ── Init ─────────────────────────────────────────────────────────────────────
function init() {
  initMiningTabs();
  initDashChat();
  loadAllStats();
}
