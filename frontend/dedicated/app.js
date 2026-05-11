/**
 * PHQ Intelligence Bot — Dedicated Chat Page
 * Full GPT-like interface with session history.
 */
'use strict';

const API_BASE = window.PHQ_API_BASE || 'https://aibot.matrixupp.com';

function getToken() {
  // Matrix team: replace with however you store the JWT
  return localStorage.getItem('matrix_jwt')
    || sessionStorage.getItem('token')
    || sessionStorage.getItem('jwt')
    || '';
}

// ─── State ────────────────────────────────────────────────────────────────────
let currentSessionId = null;
let loading = false;

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

  // Sample query buttons
  document.querySelectorAll('.sample-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      queryInput.value = btn.textContent.trim();
      sendBtn.disabled = false;
      handleSend();
    });
  });
}

// ─── Sessions ─────────────────────────────────────────────────────────────────
async function loadSessions() {
  try {
    const res = await apiFetch('/api/v2/chat/sessions');
    const sessions = await res.json();
    renderSessions(sessions);
  } catch (_) { /* not logged in yet or no sessions */ }
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

  try {
    const res = await apiFetch(`/api/v2/chat/sessions/${sessionId}/messages`);
    const messages = await res.json();
    messagesArea.innerHTML = '';
    messages.forEach(msg => appendMessage(msg.role, msg.content, msg.meta));
    messagesArea.scrollTop = messagesArea.scrollHeight;

    // Update active state in sidebar
    document.querySelectorAll('.session-item').forEach(el => {
      el.classList.toggle('active', el.dataset.id === sessionId);
    });
  } catch (e) {
    console.error('Failed to load session:', e);
  }
}

function startNewChat() {
  currentSessionId = null;
  messagesArea.innerHTML = `
    <div class="welcome" id="welcomeScreen">
      <div class="welcome-icon">🤖</div>
      <h2 class="welcome-title">PHQ Intelligence Bot</h2>
      <p class="welcome-sub">
        Ask questions in <strong>Hindi or English</strong> about incidents,
        social media trends, and public sentiment across Uttar Pradesh.
      </p>
      <div class="sample-queries">
        <div class="sample-label">Sample queries:</div>
        <div class="sample-grid">
          <button class="sample-btn">Were there any violence incidents in Varanasi during Kawad Yatra in the last 5 years?</button>
          <button class="sample-btn">पिछले 30 दिनों में मथुरा में कौन से हादसे हुए?</button>
          <button class="sample-btn">What is public sentiment about the highway project in Lucknow?</button>
          <button class="sample-btn">Was there a stampede in any UP temple due to social media misinformation?</button>
        </div>
      </div>
    </div>`;
  document.querySelectorAll('.sample-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      queryInput.value = btn.textContent.trim();
      sendBtn.disabled = false;
      handleSend();
    });
  });
  document.querySelectorAll('.session-item').forEach(el => el.classList.remove('active'));
  chatTitle.textContent = 'PHQ Intelligence Bot';
  queryInput.focus();
}

// ─── Send message ─────────────────────────────────────────────────────────────
async function handleSend() {
  const text = queryInput.value.trim();
  if (!text || loading) return;

  // Remove welcome screen on first message
  document.getElementById('welcomeScreen')?.remove();

  queryInput.value = '';
  queryInput.style.height = 'auto';
  sendBtn.disabled = true;
  setLoading(true);

  appendMessage('user', text);

  try {
    const res = await apiFetch('/api/v2/chat/query', {
      method: 'POST',
      body: JSON.stringify({ query: text, session_id: currentSessionId }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    currentSessionId = data.session_id;

    removeTypingIndicator();
    appendMessage('assistant', data.answer, {
      confidence: data.confidence,
      evidence_count: data.evidence_count,
      sources: data.sources,
      latency_ms: data.latency_ms,
    });

    // Refresh session list & update title
    loadSessions();
    if (!chatTitle.textContent || chatTitle.textContent === 'PHQ Intelligence Bot') {
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

// ─── Render helpers ───────────────────────────────────────────────────────────
function appendMessage(role, text, meta) {
  const msg = document.createElement('div');
  msg.className = `msg ${role}`;
  msg.innerHTML = `
    <div class="avatar">${role === 'user' ? '👤' : '🤖'}</div>
    <div>
      <div class="bubble">${escHtml(text)}</div>
      ${meta ? renderMeta(meta) : ''}
    </div>`;
  messagesArea.appendChild(msg);
  messagesArea.scrollTop = messagesArea.scrollHeight;
}

function renderMeta(meta) {
  const conf = meta.confidence || 0;
  const confClass = conf >= 0.7 ? 'conf-high' : conf >= 0.4 ? 'conf-med' : 'conf-low';
  const parts = [
    `<span class="${confClass}">${Math.round(conf * 100)}% confidence</span>`,
    meta.evidence_count != null ? `<span>${meta.evidence_count} records</span>` : '',
    meta.latency_ms != null ? `<span>${meta.latency_ms}ms</span>` : '',
    meta.sources?.length ? `<span>${escHtml(meta.sources.join(', '))}</span>` : '',
  ].filter(Boolean);
  return `<div class="msg-meta">${parts.join('')}</div>`;
}

function setLoading(state) {
  loading = state;
  if (state) {
    const typing = document.createElement('div');
    typing.className = 'msg assistant typing-indicator';
    typing.innerHTML = `
      <div class="avatar">🤖</div>
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
