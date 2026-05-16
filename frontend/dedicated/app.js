/**
 * Matrix AI Sahayak — Dedicated Chat Page
 */
'use strict';

const API_BASE = (window.PHQ_API_BASE != null && window.PHQ_API_BASE !== '')
  ? window.PHQ_API_BASE
  : 'https://aibot.matrixupp.com';

const DEMO_MODE = !!window.DEMO_ANSWERS;

function getToken() {
  return localStorage.getItem('matrix_jwt')
    || sessionStorage.getItem('token')
    || sessionStorage.getItem('jwt')
    || '';
}

// ─── State ────────────────────────────────────────────────────────────────────
let currentSessionId = null;
let loading = false;

// In-memory store used only in DEMO_MODE
const _demoSessions = {};

// ─── DOM refs ─────────────────────────────────────────────────────────────────
const messagesArea   = document.getElementById('messagesArea');
const queryInput     = document.getElementById('queryInput');
const sendBtn        = document.getElementById('sendBtn');
const sessionsList   = document.getElementById('sessionsList');
const newChatBtn     = document.getElementById('newChatBtn');
const sidebarToggle  = document.getElementById('sidebarToggle');
const sidebar        = document.querySelector('.sidebar');
const chatTitle      = document.getElementById('chatTitle');

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadSessions();
  bindEvents();
  initTheme();
});

function bindEvents() {
  sendBtn.addEventListener('click', handleSend);

  queryInput.addEventListener('input', () => {
    sendBtn.disabled = !queryInput.value.trim() || loading;
    queryInput.style.height = 'auto';
    queryInput.style.height = Math.min(queryInput.scrollHeight, 120) + 'px';
  });

  queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  });

  newChatBtn.addEventListener('click', startNewChat);
  sidebarToggle.addEventListener('click', () => sidebar.classList.toggle('collapsed'));

  bindSampleBtns();

  const themeBtn = document.getElementById('themeToggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  initTrending();
  initLiveStream();
}

function bindSampleBtns() {
  document.querySelectorAll('.sample-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      queryInput.value = btn.textContent.trim();
      sendBtn.disabled = false;
      handleSend();
    });
  });
}

// ─── Theme ────────────────────────────────────────────────────────────────────
function initTheme() {
  const saved = localStorage.getItem('matrix_theme') || 'dark';
  applyTheme(saved);
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  applyTheme(next);
  localStorage.setItem('matrix_theme', next);
}

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = theme === 'dark' ? '☀️' : '🌙';
}

// ─── Sessions ─────────────────────────────────────────────────────────────────
async function loadSessions() {
  if (DEMO_MODE) { _renderDemoSessions(); return; }
  try {
    const res = await apiFetch('/api/v2/chat/sessions');
    const sessions = await res.json();
    renderSessions(sessions);
  } catch (_) {}
}

function _renderDemoSessions() {
  const sessions = Object.entries(_demoSessions)
    .map(([sid, s]) => ({ session_id: sid, title: s.title, updated_at: s.updated_at }))
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  renderSessions(sessions);
}

function renderSessions(sessions) {
  if (!sessions.length) {
    sessionsList.innerHTML = '<div class="sessions-empty">No conversations yet</div>';
    return;
  }
  sessionsList.innerHTML = sessions.map(s => `
    <div class="session-item ${s.session_id === currentSessionId ? 'active' : ''}"
         data-id="${s.session_id}">
      <div class="session-title">${escHtml(s.title)}</div>
      <div class="session-date">${formatDate(s.updated_at)}</div>
    </div>
  `).join('');
  sessionsList.querySelectorAll('.session-item').forEach(el => {
    el.addEventListener('click', () => loadSession(el.dataset.id));
  });
}

async function loadSession(sessionId) {
  currentSessionId = sessionId;
  document.getElementById('welcomeScreen')?.remove();

  let messages = [];
  if (DEMO_MODE) {
    messages = (_demoSessions[sessionId]?.messages || []);
  } else {
    try {
      const res = await apiFetch(`/api/v2/chat/sessions/${sessionId}/messages`);
      messages = await res.json();
    } catch (e) { console.error(e); return; }
  }

  messagesArea.innerHTML = '';
  messages.forEach(msg => appendMessage(msg.role, msg.content, msg.meta));
  messagesArea.scrollTop = messagesArea.scrollHeight;

  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === sessionId);
  });
}

function startNewChat() {
  currentSessionId = null;
  messagesArea.innerHTML = `
    <div class="welcome" id="welcomeScreen">
      <img src="/static/logo/UP_police_logo.jpg" alt="UP Police" class="welcome-logo" />
      <h2 class="welcome-title">Matrix AI Sahayak</h2>
      <p class="welcome-sub">
        Ask questions in <strong>Hindi or English</strong> about incidents,
        social media trends, and public sentiment across Uttar Pradesh.
      </p>
      <div class="sample-queries">
        <div class="sample-label">Sample queries:</div>
        <div class="sample-grid">
          <button class="sample-btn">Smart meter protest ka current status kya hai?</button>
          <button class="sample-btn">मथुरा में पिछले 30 दिनों की law &amp; order situation?</button>
          <button class="sample-btn">Varanasi mein social media pe kya trend kar raha hai?</button>
          <button class="sample-btn">Kawad Yatra 2026 ki preparation aur risk assessment?</button>
          <button class="sample-btn">Kanpur mein koi protest ya agitation chal rahi hai?</button>
          <button class="sample-btn">अयोध्या में tourist-related कोई incident हुई?</button>
          <button class="sample-btn">AAP ka UP mein social media campaign kaise chal raha hai?</button>
          <button class="sample-btn">UP mein active protests ka dashboard dikhao</button>
          <button class="sample-btn">Agra mein smart meter FIR waale case ka update?</button>
          <button class="sample-btn">गोरखपुर में हाल की सोशल मीडिया गतिविधि?</button>
        </div>
      </div>
    </div>`;
  bindSampleBtns();
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
  chatTitle.textContent = 'Matrix AI Sahayak';
  queryInput.focus();
}

// ─── Demo mode helpers ────────────────────────────────────────────────────────
function _matchDemo(query) {
  const q = query.toLowerCase();
  const answers = window.DEMO_ANSWERS || {};
  for (const [keyword, response] of Object.entries(answers)) {
    if (q.includes(keyword)) return response;
  }
  return null; // unknown query → server will fetch live news
}

function _demoStoreTurn(sessionId, query, response) {
  const now = new Date().toISOString();
  if (!_demoSessions[sessionId]) {
    _demoSessions[sessionId] = { title: query.slice(0, 60), messages: [], updated_at: now };
  }
  const sess = _demoSessions[sessionId];
  sess.messages.push({ role: 'user', content: query, meta: null });
  sess.messages.push({
    role: 'assistant', content: response.answer,
    meta: { confidence: response.confidence, evidence_count: response.evidence_count,
            sources: response.sources, latency_ms: response.latency_ms },
  });
  sess.updated_at = new Date().toISOString();
}

// ─── Send message ─────────────────────────────────────────────────────────────
async function handleSend() {
  const text = queryInput.value.trim();
  if (!text || loading) return;

  document.getElementById('welcomeScreen')?.remove();
  queryInput.value = '';
  queryInput.style.height = 'auto';
  sendBtn.disabled = true;
  setLoading(true);
  appendMessage('user', text);

  try {
    let data;

    if (DEMO_MODE) {
      const localResp = _matchDemo(text);
      if (localResp) {
        // Known topic — respond instantly from injected data, no network call
        await new Promise(r => setTimeout(r, 700 + Math.random() * 600));
        const sid = currentSessionId || ('demo-' + Math.random().toString(36).slice(2, 10));
        _demoStoreTurn(sid, text, localResp);
        data = { session_id: sid, ...localResp };
      } else {
        // Unknown query — fetch live news from demo server
        const res = await apiFetch('/api/v2/chat/query', {
          method: 'POST',
          body: JSON.stringify({ query: text, session_id: currentSessionId }),
        });
        if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${res.status}`); }
        data = await res.json();
        if (data.session_id) _demoStoreTurn(data.session_id, text, data);
      }
    } else {
      const res = await apiFetch('/api/v2/chat/query', {
        method: 'POST',
        body: JSON.stringify({ query: text, session_id: currentSessionId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      data = await res.json();
    }

    currentSessionId = data.session_id;
    removeTypingIndicator();
    appendMessage('assistant', data.answer, {
      confidence: data.confidence,
      evidence_count: data.evidence_count,
      sources: data.sources,
      latency_ms: data.latency_ms,
    });

    loadSessions();
    if (!chatTitle.textContent || chatTitle.textContent === 'Matrix AI Sahayak') {
      chatTitle.textContent = text.slice(0, 40) + (text.length > 40 ? '…' : '');
    }
  } catch (err) {
    removeTypingIndicator();
    appendMessage('assistant', `Error: ${err.message}. Please try again.`);
  } finally {
    setLoading(false);
    sendBtn.disabled = !queryInput.value.trim();
  }
}

// ─── Markdown renderer ────────────────────────────────────────────────────────
function renderMarkdown(text) {
  let h = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  h = h.replace(/(\|.+\|\n)+/g, (block) => {
    const rows = block.trim().split('\n').filter(r => !/^\|[-:| ]+\|$/.test(r));
    if (!rows.length) return block;
    const toRow = (r, tag) =>
      '<tr>' + r.split('|').filter((_, i, a) => i > 0 && i < a.length - 1)
        .map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
    const [head, ...body] = rows;
    return `<table><thead>${toRow(head,'th')}</thead><tbody>${body.map(r=>toRow(r,'td')).join('')}</tbody></table>`;
  });

  h = h
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`([^`\n]+)`/g, '<code>$1</code>');

  h = h.replace(/^#{1,3} (.+)$/gm, '<span class="md-h">$1</span>');
  h = h.replace(/^---+$/gm, '<hr class="md-sep">');
  h = h.replace(/^[•\-\*] (.+)$/gm, '<div class="md-li"><span>•</span><span>$1</span></div>');
  h = h.replace(/^(\d+)\. (.+)$/gm, '<div class="md-li"><span>$1.</span><span>$2</span></div>');
  h = h.replace(/\n\n/g, '<br>').replace(/\n/g, '<br>');

  return h;
}

// ─── Render helpers ───────────────────────────────────────────────────────────
function appendMessage(role, text, meta) {
  const msg = document.createElement('div');
  msg.className = `msg ${role}`;

  const avatar = role === 'user' ? '👤' : '🛡️';
  const bubble = role === 'assistant'
    ? `<div class="bubble">${renderMarkdown(text)}</div>`
    : `<div class="bubble">${escHtml(text)}</div>`;

  msg.innerHTML = `
    <div class="avatar">${avatar}</div>
    <div class="msg-content">
      ${bubble}
      ${meta ? renderMeta(meta) : ''}
    </div>`;
  messagesArea.appendChild(msg);
  messagesArea.scrollTop = messagesArea.scrollHeight;
}

function renderMeta(meta) {
  const conf = meta.confidence || 0;
  const confClass = conf >= 0.7 ? 'conf-high' : conf >= 0.4 ? 'conf-med' : 'conf-low';
  const sources = (meta.sources || [])
    .map(s => `<span class="src-pill">${escHtml(s)}</span>`).join('');
  const parts = [
    `<span class="${confClass}">⬤ ${Math.round(conf * 100)}% confidence</span>`,
    meta.evidence_count != null ? `<span>${meta.evidence_count} records</span>` : '',
    meta.latency_ms != null ? `<span>${meta.latency_ms}ms</span>` : '',
    sources,
  ].filter(Boolean);
  return `<div class="msg-meta">${parts.join('')}</div>`;
}

function setLoading(state) {
  loading = state;
  if (state) {
    const typing = document.createElement('div');
    typing.className = 'msg assistant typing-indicator';
    typing.innerHTML = `
      <div class="avatar">🛡️</div>
      <div class="bubble typing-bubble">
        <div class="typing-dots">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>`;
    messagesArea.appendChild(typing);
    messagesArea.scrollTop = messagesArea.scrollHeight;
  }
}

function removeTypingIndicator() {
  messagesArea.querySelector('.typing-indicator')?.remove();
}

// ─── Live stream panel ────────────────────────────────────────────────────────
function initLiveStream() {
  const toggle   = document.getElementById('liveToggle');
  const body     = document.getElementById('liveBody');
  const chevron  = document.getElementById('liveChevron');
  const frame    = document.getElementById('liveFrame');
  const select   = document.getElementById('liveChannelSelect');
  if (!toggle || !body || !frame) return;

  let open = false;

  function setChannel(val) {
    // val starts with "ch:" → channel-based live stream; otherwise it's a video ID
    const src = val.startsWith('ch:')
      ? `https://www.youtube.com/embed/live_stream?channel=${val.slice(3)}&autoplay=1&mute=1`
      : `https://www.youtube.com/embed/${val}?autoplay=1&mute=1`;
    frame.src = src;
  }

  toggle.addEventListener('click', () => {
    open = !open;
    body.classList.toggle('open', open);
    chevron.classList.toggle('open', open);
    if (open && frame.src === 'about:blank') {
      setChannel(select.value);
    }
    if (!open) {
      // Stop playback when collapsed (avoids audio continuing in background)
      frame.src = 'about:blank';
    }
  });

  select.addEventListener('change', () => {
    if (open) setChannel(select.value);
  });
}

// ─── Trending panel ───────────────────────────────────────────────────────────
let _trendCity = 'up';

function initTrending() {
  document.querySelectorAll('.trend-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.trend-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      _trendCity = btn.dataset.city;
      loadTrending();
    });
  });
  const refreshBtn = document.getElementById('trendRefresh');
  if (refreshBtn) refreshBtn.addEventListener('click', loadTrending);

  loadTrending();
  setInterval(loadTrending, 15 * 60 * 1000);
}

async function loadTrending() {
  const list = document.getElementById('trendingList');
  if (!list) return;
  list.innerHTML = '<div class="trend-loading">⟳ Loading…</div>';
  try {
    const res = await apiFetch(`/api/v2/trending?city=${_trendCity}`);
    if (!res.ok) throw new Error('fetch failed');
    const data = await res.json();
    renderTrending(data.items || []);
  } catch {
    list.innerHTML = '<div class="trend-empty">Unable to load</div>';
  }
}

function renderTrending(items) {
  const list = document.getElementById('trendingList');
  if (!list) return;
  if (!items.length) {
    list.innerHTML = '<div class="trend-empty">No trending items</div>';
    return;
  }
  const typeIcon = { social: '🐦', reddit: '💬', news: '📰' };
  list.innerHTML = items.map(item => `
    <div class="trend-item">
      <div class="trend-source">${typeIcon[item.source_type] || '📌'} ${escHtml(item.source)}</div>
      <div class="trend-title">${escHtml(item.title)}</div>
      ${item.pub_date ? `<div class="trend-time">${escHtml(item.pub_date)}</div>` : ''}
    </div>
  `).join('');
}

// ─── Utils ────────────────────────────────────────────────────────────────────
function apiFetch(path, opts = {}) {
  return fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`,
      ...(opts.headers || {}),
    },
    ...opts,
  });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatDate(iso) {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
  } catch (_) { return ''; }
}
