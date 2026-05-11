/**
 * PHQ Intelligence Bot — Chat Widget
 * Embeds as a floating popup on any Matrix dashboard page.
 *
 * Usage (add to any Matrix HTML page):
 *   <script src="/ai-bot/widget/chat-widget.js"
 *           data-api="https://your-bot-server:8000"
 *           data-token-fn="getMatrixToken">   ← name of a global JS fn that returns JWT
 *   </script>
 *
 * Matrix team integration:
 *   1. Host these files on the same server as the bot API
 *   2. Include the <script> tag in your base template
 *   3. Implement window.getMatrixToken = () => localStorage.getItem('matrix_jwt')
 */

(function () {
  'use strict';

  const script = document.currentScript;
  const API_BASE = (script && script.dataset.api) || 'http://localhost:8000';
  const TOKEN_FN = (script && script.dataset.tokenFn) || 'getMatrixToken';

  function getToken() {
    if (typeof window[TOKEN_FN] === 'function') return window[TOKEN_FN]();
    // Fallback: read from common storage locations used by Matrix
    return localStorage.getItem('matrix_jwt')
      || sessionStorage.getItem('token')
      || sessionStorage.getItem('jwt')
      || '';
  }

  // ─── Inject styles ────────────────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    #phq-bot-trigger {
      position: fixed; bottom: 24px; right: 24px; z-index: 9998;
      width: 56px; height: 56px; border-radius: 50%;
      background: #1a56db; color: #fff; border: none; cursor: pointer;
      box-shadow: 0 4px 16px rgba(26,86,219,.45);
      display: flex; align-items: center; justify-content: center;
      font-size: 22px; transition: transform .2s;
    }
    #phq-bot-trigger:hover { transform: scale(1.08); }
    #phq-bot-trigger .phq-badge {
      position: absolute; top: 2px; right: 2px; width: 12px; height: 12px;
      background: #22c55e; border-radius: 50%; border: 2px solid #fff;
    }
    #phq-bot-panel {
      position: fixed; bottom: 90px; right: 24px; z-index: 9999;
      width: 380px; max-height: 560px;
      background: #fff; border-radius: 16px;
      box-shadow: 0 8px 40px rgba(0,0,0,.18);
      display: flex; flex-direction: column; overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px; transition: opacity .2s, transform .2s;
    }
    #phq-bot-panel.phq-hidden { opacity: 0; pointer-events: none; transform: translateY(12px); }
    .phq-header {
      background: #1a56db; color: #fff; padding: 14px 16px;
      display: flex; align-items: center; justify-content: space-between;
    }
    .phq-header-title { font-weight: 600; font-size: 15px; }
    .phq-header-sub { font-size: 11px; opacity: .8; margin-top: 2px; }
    .phq-header-actions { display: flex; gap: 8px; }
    .phq-header-btn {
      background: rgba(255,255,255,.2); border: none; color: #fff;
      width: 28px; height: 28px; border-radius: 6px; cursor: pointer;
      display: flex; align-items: center; justify-content: center; font-size: 13px;
    }
    .phq-header-btn:hover { background: rgba(255,255,255,.3); }
    .phq-messages {
      flex: 1; overflow-y: auto; padding: 12px; display: flex; flex-direction: column; gap: 10px;
    }
    .phq-msg { display: flex; gap: 8px; }
    .phq-msg.phq-user { justify-content: flex-end; }
    .phq-bubble {
      max-width: 85%; padding: 9px 13px; border-radius: 14px; line-height: 1.5;
      word-break: break-word; white-space: pre-wrap;
    }
    .phq-user .phq-bubble { background: #1a56db; color: #fff; border-radius: 14px 14px 4px 14px; }
    .phq-assistant .phq-bubble { background: #f3f4f6; color: #111; border-radius: 14px 14px 14px 4px; }
    .phq-meta {
      font-size: 10px; color: #9ca3af; margin-top: 5px;
      display: flex; gap: 8px; flex-wrap: wrap;
    }
    .phq-conf-high { color: #16a34a; } .phq-conf-med { color: #d97706; } .phq-conf-low { color: #dc2626; }
    .phq-typing { display: flex; align-items: center; gap: 4px; padding: 9px 13px; }
    .phq-dot { width: 7px; height: 7px; border-radius: 50%; background: #9ca3af; animation: phqBounce .9s infinite; }
    .phq-dot:nth-child(2) { animation-delay: .15s; } .phq-dot:nth-child(3) { animation-delay: .3s; }
    @keyframes phqBounce { 0%,60%,100%{transform:translateY(0)} 30%{transform:translateY(-6px)} }
    .phq-input-row {
      padding: 10px 12px; border-top: 1px solid #e5e7eb; display: flex; gap: 8px; align-items: flex-end;
    }
    .phq-input {
      flex: 1; border: 1px solid #d1d5db; border-radius: 10px;
      padding: 8px 12px; font-size: 13px; resize: none; outline: none;
      font-family: inherit; max-height: 80px; line-height: 1.4;
    }
    .phq-input:focus { border-color: #1a56db; }
    .phq-send {
      background: #1a56db; color: #fff; border: none; border-radius: 10px;
      padding: 8px 14px; cursor: pointer; font-size: 13px; font-weight: 500;
      white-space: nowrap; transition: background .2s;
    }
    .phq-send:disabled { background: #9ca3af; cursor: default; }
    .phq-send:not(:disabled):hover { background: #1e429f; }
    .phq-fullpage-link {
      text-align: center; padding: 6px; font-size: 11px; color: #6b7280;
      border-top: 1px solid #f3f4f6;
    }
    .phq-fullpage-link a { color: #1a56db; text-decoration: none; }
    .phq-fullpage-link a:hover { text-decoration: underline; }
  `;
  document.head.appendChild(style);

  // ─── DOM ──────────────────────────────────────────────────────────────────
  const trigger = document.createElement('button');
  trigger.id = 'phq-bot-trigger';
  trigger.innerHTML = '🤖<span class="phq-badge"></span>';
  trigger.title = 'PHQ Intelligence Bot';

  const panel = document.createElement('div');
  panel.id = 'phq-bot-panel';
  panel.classList.add('phq-hidden');
  panel.innerHTML = `
    <div class="phq-header">
      <div>
        <div class="phq-header-title">PHQ Intelligence Bot</div>
        <div class="phq-header-sub">UP Police Intelligence Assistant</div>
      </div>
      <div class="phq-header-actions">
        <button class="phq-header-btn" id="phq-fullpage-btn" title="Open full chat">⛶</button>
        <button class="phq-header-btn" id="phq-close-btn" title="Close">✕</button>
      </div>
    </div>
    <div class="phq-messages" id="phq-messages">
      <div class="phq-msg phq-assistant">
        <div class="phq-bubble">
          नमस्ते। आप UP के किसी भी district में incidents, social media trends,
          या public sentiment के बारे में Hindi या English में पूछ सकते हैं।
        </div>
      </div>
    </div>
    <div class="phq-input-row">
      <textarea class="phq-input" id="phq-input" rows="1"
        placeholder="Ask about incidents in any UP district…"></textarea>
      <button class="phq-send" id="phq-send">Send</button>
    </div>
    <div class="phq-fullpage-link">
      <a href="/ai-bot/" target="_blank">Open full chat with history →</a>
    </div>
  `;

  document.body.appendChild(trigger);
  document.body.appendChild(panel);

  // ─── State ────────────────────────────────────────────────────────────────
  let sessionId = null;
  let loading = false;

  // ─── Toggle ───────────────────────────────────────────────────────────────
  trigger.addEventListener('click', () => panel.classList.toggle('phq-hidden'));
  document.getElementById('phq-close-btn').addEventListener('click', () => panel.classList.add('phq-hidden'));
  document.getElementById('phq-fullpage-btn').addEventListener('click', () => {
    window.open('/ai-bot/', '_blank');
  });

  // ─── Auto-resize textarea ─────────────────────────────────────────────────
  const input = document.getElementById('phq-input');
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 80) + 'px';
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  document.getElementById('phq-send').addEventListener('click', sendMessage);

  // ─── Send ──────────────────────────────────────────────────────────────────
  async function sendMessage() {
    const text = input.value.trim();
    if (!text || loading) return;

    appendMessage('user', text);
    input.value = '';
    input.style.height = 'auto';
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/api/v2/chat/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${getToken()}`,
        },
        body: JSON.stringify({ query: text, session_id: sessionId }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      sessionId = data.session_id;
      appendMessage('assistant', data.answer, {
        confidence: data.confidence,
        evidence: data.evidence_count,
        latency: data.latency_ms,
        sources: data.sources,
      });
    } catch (err) {
      appendMessage('assistant', 'Sorry, an error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function appendMessage(role, text, meta) {
    const messages = document.getElementById('phq-messages');
    const msg = document.createElement('div');
    msg.className = `phq-msg phq-${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'phq-bubble';
    bubble.textContent = text;
    msg.appendChild(bubble);

    if (meta) {
      const metaEl = document.createElement('div');
      metaEl.className = 'phq-meta';
      const confClass = meta.confidence >= 0.7 ? 'phq-conf-high'
        : meta.confidence >= 0.4 ? 'phq-conf-med' : 'phq-conf-low';
      metaEl.innerHTML = `
        <span class="${confClass}">${Math.round(meta.confidence * 100)}% confidence</span>
        <span>${meta.evidence} records</span>
        <span>${meta.latency}ms</span>
        ${meta.sources?.length ? `<span>${meta.sources.join(', ')}</span>` : ''}
      `;
      msg.appendChild(metaEl);
    }

    // Remove typing indicator if present
    const typing = messages.querySelector('.phq-typing-wrapper');
    if (typing) typing.remove();

    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
  }

  function setLoading(state) {
    loading = state;
    document.getElementById('phq-send').disabled = state;
    const messages = document.getElementById('phq-messages');
    if (state) {
      const wrap = document.createElement('div');
      wrap.className = 'phq-msg phq-assistant phq-typing-wrapper';
      wrap.innerHTML = '<div class="phq-bubble phq-typing"><div class="phq-dot"></div><div class="phq-dot"></div><div class="phq-dot"></div></div>';
      messages.appendChild(wrap);
      messages.scrollTop = messages.scrollHeight;
    }
  }
})();
