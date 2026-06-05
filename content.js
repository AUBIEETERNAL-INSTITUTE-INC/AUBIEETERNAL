// content.js — AUBIEETERNAL Content Script
// Injects 🦅 Analyze buttons into X/Twitter posts and any page

const SERVER_URL = 'http://localhost:8502';
let settings = { showXButtons: true, autoAnalyze: false };

// ── Load settings ──────────────────────────────────────────────────────────────
chrome.storage.local.get(['showXButtons','autoAnalyze','serverUrl'], data => {
  settings.showXButtons = data.showXButtons !== false;
  settings.autoAnalyze  = data.autoAnalyze || false;
  if (data.serverUrl) settings.serverUrl = data.serverUrl;
  if (settings.showXButtons) init();
});

// ── Init ───────────────────────────────────────────────────────────────────────
function init() {
  injectStyles();
  if (isXPage()) {
    observeXPosts();
  }
  setupContextMenu();
}

function isXPage() {
  return location.hostname === 'x.com' || location.hostname === 'twitter.com';
}

// ── Inject global styles ───────────────────────────────────────────────────────
function injectStyles() {
  const style = document.createElement('style');
  style.textContent = `
    .aubie-btn {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 10px;
      border-radius: 12px;
      border: 1px solid rgba(247, 147, 26, 0.4);
      background: rgba(247, 147, 26, 0.08);
      color: #f7931a;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      margin-left: 6px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      user-select: none;
      text-decoration: none;
    }
    .aubie-btn:hover {
      background: rgba(247, 147, 26, 0.18);
      border-color: #f7931a;
      transform: scale(1.03);
    }
    .aubie-btn.loading {
      opacity: 0.6;
      pointer-events: none;
    }
    .aubie-btn.done-green {
      border-color: #00ff88;
      color: #00ff88;
      background: rgba(0,255,136,0.08);
    }
    .aubie-btn.done-red {
      border-color: #ff4444;
      color: #ff4444;
      background: rgba(255,68,68,0.08);
    }

    /* Result overlay */
    .aubie-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0,0,0,0.75);
      z-index: 999998;
      display: flex;
      align-items: center;
      justify-content: center;
      backdrop-filter: blur(4px);
    }
    .aubie-panel {
      background: #0a0e1a;
      border: 1px solid #1e2a3a;
      border-radius: 14px;
      width: 480px;
      max-height: 85vh;
      overflow-y: auto;
      box-shadow: 0 20px 60px rgba(0,0,0,0.8);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      color: #c8d8ff;
    }
    .aubie-panel-header {
      padding: 14px 18px 12px;
      border-bottom: 1px solid #1e2a3a;
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #0d1228;
      border-radius: 14px 14px 0 0;
    }
    .aubie-panel-title {
      font-weight: 700;
      color: #f7931a;
      font-size: 13px;
      letter-spacing: 0.05em;
    }
    .aubie-close {
      cursor: pointer;
      color: #445577;
      font-size: 18px;
      line-height: 1;
      padding: 2px 6px;
      border-radius: 4px;
      transition: color 0.2s;
    }
    .aubie-close:hover { color: #c8d8ff; }

    .aubie-section {
      padding: 14px 18px;
      border-bottom: 1px solid #1e2a3a;
    }
    .aubie-section:last-child { border-bottom: none; }
    .aubie-section-title {
      font-size: 10px;
      font-family: 'Courier New', monospace;
      letter-spacing: 0.12em;
      margin-bottom: 8px;
      font-weight: 600;
    }
    .aubie-green  { color: #00ff88; }
    .aubie-orange { color: #f7931a; }
    .aubie-purple { color: #a020f0; }
    .aubie-teal   { color: #00cfff; }
    .aubie-red    { color: #ff4444; }
    .aubie-dim    { color: #8899bb; }
    .aubie-text   { font-size: 13px; line-height: 1.65; }
    .aubie-label  { font-size: 10px; color: #445577; margin-bottom:3px; font-weight:600; letter-spacing:0.05em; }

    .aubie-bar {
      height: 4px; background: #1e2a3a; border-radius: 2px; margin: 6px 0;
    }
    .aubie-bar-fill { height: 100%; border-radius: 2px; }

    .aubie-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 10px;
      margin-top: 4px;
    }
    .aubie-attack-badge {
      background: #2a0a0a;
      border: 1px solid #ff4444;
      color: #ff4444;
    }
    .aubie-spinner {
      text-align: center;
      padding: 30px;
      color: #445577;
    }
    .aubie-spinner::before {
      content: '⚡';
      display: block;
      font-size: 28px;
      margin-bottom: 8px;
      animation: aubiePulse 1s infinite;
    }
    @keyframes aubiePulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  `;
  document.head.appendChild(style);
}

// ── X / Twitter integration ────────────────────────────────────────────────────
function observeXPosts() {
  // Find existing posts
  document.querySelectorAll('article[data-testid="tweet"]').forEach(addButton);

  // Watch for new posts (infinite scroll)
  const observer = new MutationObserver(mutations => {
    mutations.forEach(m => {
      m.addedNodes.forEach(node => {
        if (node.nodeType === 1) {
          const tweets = node.querySelectorAll
            ? node.querySelectorAll('article[data-testid="tweet"]')
            : [];
          tweets.forEach(addButton);
          if (node.matches?.('article[data-testid="tweet"]')) addButton(node);
        }
      });
    });
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

function addButton(tweet) {
  // Don't add twice
  if (tweet.querySelector('.aubie-btn')) return;

  // Find the action bar (like, retweet, etc.)
  const actionBar = tweet.querySelector('[role="group"]');
  if (!actionBar) return;

  const btn = document.createElement('button');
  btn.className = 'aubie-btn';
  btn.innerHTML = '🦅 Analyze';
  btn.title = 'Analyze with AUBIEETERNAL';
  btn.setAttribute('aria-label', 'Analyze with AUBIEETERNAL');

  btn.addEventListener('click', async e => {
    e.stopPropagation();
    e.preventDefault();

    // Get tweet text
    const tweetText = tweet.querySelector('[data-testid="tweetText"]')?.innerText?.trim()
      || tweet.querySelector('[lang]')?.innerText?.trim()
      || '';

    if (!tweetText) {
      btn.innerHTML = '⚠️ No text';
      return;
    }

    btn.innerHTML = '⚡ Analyzing...';
    btn.classList.add('loading');

    try {
      const result = await analyzeText(tweetText);
      btn.classList.remove('loading');

      const attack = result.epistemic?.narrative_attack_detected;
      const score  = result.simulation?.stress_score || 5;

      if (attack) {
        btn.innerHTML = '⚠️ Attack';
        btn.classList.add('done-red');
      } else if (score >= 7) {
        btn.innerHTML = `✅ ${score}/10`;
        btn.classList.add('done-green');
      } else {
        btn.innerHTML = `🦅 ${score}/10`;
      }

      showResultOverlay(tweetText, result);

    } catch (err) {
      btn.classList.remove('loading');
      btn.innerHTML = '❌ Error';
      console.error('AUBIEETERNAL:', err);
    }
  });

  // Append after the last action button
  actionBar.appendChild(btn);
}

// ── Analyze text via local server ──────────────────────────────────────────────
async function analyzeText(text) {
  const url = (settings.serverUrl || SERVER_URL) + '/bridge';
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) throw new Error(`Server error ${res.status}`);
  return res.json();
}

// ── Result overlay ─────────────────────────────────────────────────────────────
function showResultOverlay(text, result) {
  const ep  = result.epistemic  || {};
  const fl  = result.family     || {};
  const sim = result.simulation || {};

  const score  = sim.stress_score || 5;
  const color  = score >= 7 ? '#00ff88' : score >= 4 ? '#ff9500' : '#ff4444';
  const attack = ep.narrative_attack_detected;

  const overlay = document.createElement('div');
  overlay.className = 'aubie-overlay';
  overlay.innerHTML = `
    <div class="aubie-panel">
      <div class="aubie-panel-header">
        <div class="aubie-panel-title">🦅 AUBIEETERNAL ANALYSIS</div>
        <div class="aubie-close" id="aubieClose">✕</div>
      </div>

      <!-- Original text -->
      <div class="aubie-section">
        <div class="aubie-label">POST</div>
        <div class="aubie-text aubie-dim">${text.slice(0, 200)}${text.length > 200 ? '…' : ''}</div>
      </div>

      <!-- Epistemic -->
      <div class="aubie-section">
        <div class="aubie-section-title ${attack ? 'aubie-red' : 'aubie-green'}">
          EPISTEMIC · Coherence ${(ep.coherence||0).toFixed(2)} · ${(ep.epistemic_quality||'?').toUpperCase()}
        </div>
        <div class="aubie-label">STEELMAN</div>
        <div class="aubie-text" style="margin-bottom:8px">${ep.steelman || '—'}</div>
        <div class="aubie-label">ONE-SENTENCE TRUTH</div>
        <div class="aubie-text aubie-dim" style="font-style:italic">"${ep.one_sentence_truth || ''}"</div>
        ${attack ? `<div class="aubie-badge aubie-attack-badge">⚠️ ${(ep.narrative_attack_type||'').toUpperCase()} ATTACK</div>` : ''}
      </div>

      <!-- Family lesson -->
      <div class="aubie-section">
        <div class="aubie-section-title aubie-purple">FAMILY LESSON — ${fl.lesson_title || ''}</div>
        <div class="aubie-label">FOR KIDS</div>
        <div class="aubie-text" style="margin-bottom:8px">${fl.kid_explanation || '—'}</div>
        <div class="aubie-label">ACTIVITY</div>
        <div class="aubie-text aubie-dim">${fl.family_activity || '—'}</div>
      </div>

      <!-- Sim score -->
      <div class="aubie-section">
        <div class="aubie-section-title aubie-teal">
          SIMULATION INTEGRITY: ${sim.sim_integrity || '?'} · ${score}/10
        </div>
        <div class="aubie-bar">
          <div class="aubie-bar-fill" style="width:${score*10}%;background:${color}"></div>
        </div>
        <div class="aubie-text aubie-dim">${sim.recommendation || ''}</div>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // Close on X or backdrop
  document.getElementById('aubieClose')?.addEventListener('click', () => overlay.remove());
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') overlay.remove(); }, { once: true });
}

// ── Context menu handler (listens for messages from background) ────────────────
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === 'analyzeSelection') {
    const selection = window.getSelection().toString().trim();
    if (selection) {
      analyzeText(selection)
        .then(result => showResultOverlay(selection, result))
        .catch(err => console.error('AUBIEETERNAL:', err));
    }
    sendResponse({ ok: true });
  }
});

// Setup context menu observation
function setupContextMenu() {
  // Right-click context handled by background.js
}
