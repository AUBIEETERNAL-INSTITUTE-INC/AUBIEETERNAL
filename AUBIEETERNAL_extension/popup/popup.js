// popup.js — AUBIEETERNAL Extension Popup
// Communicates with the local API server (api_server.py on port 8502)

const DEFAULT_SERVER = 'http://100.105.81.27:8502';

// ── State ──────────────────────────────────────────────────────────────────────
let serverUrl = DEFAULT_SERVER;
let connected = false;

// ── Init ───────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  await loadSettings();
  await checkConnection();
  setupTabs();
  setupBridge();
  setupOracle();
  setupLedger();
  setupSettings();
  loadLedgerStats();
  loadRuneStatus();
  setupRune();
});

// ── Settings ───────────────────────────────────────────────────────────────────
async function loadSettings() {
  const data = await chrome.storage.local.get(['serverUrl','apiKey','autoAnalyze','showXButtons']);
  serverUrl = data.serverUrl || DEFAULT_SERVER;
  document.getElementById('serverUrl').value     = serverUrl;
  document.getElementById('appUrl').value         = data.appUrl || '';
  document.getElementById('apiKey').value         = data.apiKey || '';
  document.getElementById('autoAnalyze').checked  = data.autoAnalyze || false;
  document.getElementById('showXButtons').checked = data.showXButtons !== false;
}

function setupSettings() {
  document.getElementById('saveSettings').addEventListener('click', async () => {
    const settings = {
      serverUrl:     document.getElementById('serverUrl').value.trim(),
      appUrl:        document.getElementById('appUrl').value.trim(),
      apiKey:        document.getElementById('apiKey').value.trim(),
      autoAnalyze:   document.getElementById('autoAnalyze').checked,
      showXButtons:  document.getElementById('showXButtons').checked,
    };
    await chrome.storage.local.set(settings);
    serverUrl = settings.serverUrl;
    document.getElementById('settingsSaved').style.display = 'block';
    setTimeout(() => { document.getElementById('settingsSaved').style.display = 'none'; }, 2000);
    await checkConnection();
  });
}

// ── Connection check ───────────────────────────────────────────────────────────
async function checkConnection() {
  const dot = document.getElementById('statusDot');
  try {
    const res = await fetch(`${serverUrl}/status`, { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      const data = await res.json();
      connected = true;
      dot.className = 'status-dot online';
      updateStatusBar(data);
      document.getElementById('statusBar').style.display = 'flex';
      document.getElementById('notConnected').style.display = 'none';
      document.getElementById('bridgeConnected').style.display = 'block';
    } else {
      throw new Error('not ok');
    }
  } catch {
    connected = false;
    dot.className = 'status-dot offline';
    document.getElementById('statusBar').style.display = 'none';
    document.getElementById('notConnected').style.display = 'block';
    document.getElementById('bridgeConnected').style.display = 'none';
  }
}

function updateStatusBar(data) {
  document.getElementById('wonderVal').textContent = (data.wonder_index || 0).toFixed(4);
  document.getElementById('cohVal').textContent    = (data.coherence || 0).toFixed(6);
  document.getElementById('runeVal').textContent   = data.child_rune_confirmations || 0;
  document.getElementById('costVal').textContent   = (data.daily_cost || 0).toFixed(2);
}

document.getElementById('retryBtn')?.addEventListener('click', checkConnection);

// ── Tabs ───────────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`panel-${tab.dataset.panel}`).classList.add('active');
    });
  });
}

// ── X Bridge ───────────────────────────────────────────────────────────────────
function setupBridge() {
  document.getElementById('analyzeBtn').addEventListener('click', runBridge);
  document.getElementById('openAppBtn').addEventListener('click', async () => {
    // Open the Streamlit app, not the API server
    // Try stored app URL, fall back to StartOS default
    const data = await chrome.storage.local.get('appUrl');
    const appUrl = data.appUrl || 'https://painful-recess.local:62751';
    chrome.tabs.create({ url: appUrl });
  });

  // Use selected text from active tab
  document.getElementById('useSelectionBtn').addEventListener('click', async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection().toString().trim()
    });
    const sel = results[0]?.result || '';
    if (sel) {
      document.getElementById('bridgeInput').value = sel;
      runBridge();
    } else {
      document.getElementById('bridgeInput').placeholder = 'No text selected — paste text above instead';
    }
  });

  // Keyboard shortcut
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') {
      runBridge();
    }
  });
}

async function runBridge() {
  const text = document.getElementById('bridgeInput').value.trim();
  if (!text || text.length < 5) return;

  setLoading('bridge', true);
  hideResults();

  try {
    const res = await fetch(`${serverUrl}/bridge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal: AbortSignal.timeout(60000)
    });

    if (!res.ok) throw new Error(`Server error ${res.status}`);
    const data = await res.json();

    renderEpistemic(data.epistemic || {});
    renderLesson(data.family || {});
    renderSim(data.simulation || {});

  } catch (err) {
    showError('bridge', err.message.includes('fetch') ?
      'AUBIEETERNAL server not reachable. Is launcher.py running?' :
      `Error: ${err.message}`);
  } finally {
    setLoading('bridge', false);
  }
}

function renderEpistemic(ep) {
  const result = document.getElementById('epistemicResult');
  const header = document.getElementById('epistemicHeader');
  const body   = document.getElementById('epistemicBody');

  const attack  = ep.narrative_attack_detected;
  const quality = ep.epistemic_quality || 'unknown';
  const coh     = (ep.coherence || 0).toFixed(2);
  const action  = ep.recommended_action || 'verify';

  header.className = `result-header ${attack ? 'red' : 'green'}`;
  result.className = `result ${attack ? 'tag-red' : 'tag-green'} visible`;
  header.textContent = `EPISTEMIC · Coherence ${coh} · ${quality.toUpperCase()} · → ${action.toUpperCase()}`;

  body.innerHTML = `
    <div style="margin-bottom:6px">
      <div style="color:#888;font-size:10px;margin-bottom:2px">STEELMAN</div>
      <div style="color:#c8d8ff">${ep.steelman || '—'}</div>
    </div>
    <div style="margin-bottom:6px">
      <div style="color:#888;font-size:10px;margin-bottom:2px">COUNTER</div>
      <div style="color:#8899bb">${ep.steel_against || '—'}</div>
    </div>
    <div style="color:#aabbcc;font-style:italic">"${ep.one_sentence_truth || ''}"</div>
    ${attack ? `<div class="attack-badge">⚠️ ${(ep.narrative_attack_type||'').toUpperCase()} ATTACK DETECTED</div>` : ''}
  `;
}

function renderLesson(fl) {
  const result = document.getElementById('lessonResult');
  const header = document.getElementById('lessonHeader');
  const body   = document.getElementById('lessonBody');

  result.className = 'result tag-purple visible';
  header.textContent = `FAMILY LESSON — ${fl.lesson_title || 'Untitled'} · +${fl.xp || 20} XP`;

  body.innerHTML = `
    <div class="lesson-section">
      <div class="lesson-label">👧 FOR KIDS</div>
      <div class="lesson-text">${fl.kid_explanation || '—'}</div>
    </div>
    <div class="lesson-section" style="margin-top:8px">
      <div class="lesson-label">👨‍👩 FOR PARENTS</div>
      <div class="lesson-text">${fl.parent_insight || '—'}</div>
    </div>
    <div class="lesson-section" style="margin-top:8px">
      <div class="lesson-label">🎯 ACTIVITY</div>
      <div class="lesson-text">${fl.family_activity || '—'}</div>
    </div>
  `;
}

function renderSim(sim) {
  const result = document.getElementById('simResult');
  const header = document.getElementById('simHeader');
  const body   = document.getElementById('simBody');
  const score  = sim.stress_score || 5;
  const color  = score >= 7 ? '#00ff88' : score >= 4 ? '#ff9500' : '#ff4444';

  result.className = 'result tag-teal visible';
  header.textContent = `INTEGRITY: ${sim.sim_integrity || '?'} · Stress ${score}/10 — ${sim.stress_label || ''}`;

  const barWidth = Math.round(score * 10);
  body.innerHTML = `
    <div class="score-bar">
      <div class="score-fill" style="width:${barWidth}%;background:${color}"></div>
    </div>
    <div style="color:#8899bb;font-size:11px;margin-bottom:6px">${sim.observer_note || ''}</div>
    ${(sim.anomalies||[]).length > 0
      ? `<div style="color:#ff9500;font-size:10px">⚠️ ${sim.anomalies.join(', ')}</div>`
      : '<div style="color:#00ff88;font-size:10px">✅ No anomalies detected</div>'
    }
    <div style="color:#c8d8ff;margin-top:6px;font-size:11px">${sim.recommendation || ''}</div>
  `;
}

function hideResults() {
  ['epistemicResult','lessonResult','simResult'].forEach(id => {
    document.getElementById(id).className = 'result';
  });
}

function setLoading(section, loading) {
  document.getElementById(`${section}Spinner`).className = loading ? 'spinner active' : 'spinner';
  if (section === 'bridge') {
    document.getElementById('analyzeBtn').disabled = loading;
  }
}

function showError(section, msg) {
  // show error in epistemic card
  const result = document.getElementById('epistemicResult');
  result.className = 'result tag-red visible';
  document.getElementById('epistemicHeader').className = 'result-header red';
  document.getElementById('epistemicHeader').textContent = 'ERROR';
  document.getElementById('epistemicBody').innerHTML = `<div style="color:#ff6666">${msg}</div>`;
}

// ── Oracle ─────────────────────────────────────────────────────────────────────
function setupOracle() {
  document.getElementById('oracleBtn').addEventListener('click', runOracle);
  document.getElementById('oracleInput').addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) runOracle();
  });
}

async function runOracle() {
  const question = document.getElementById('oracleInput').value.trim();
  if (!question) return;

  setLoading('oracle', true);
  document.getElementById('oracleResponse').className = 'oracle-response';

  try {
    const stored = await chrome.storage.local.get('apiKey');
    const res = await fetch(`${serverUrl}/oracle`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, api_key: stored.apiKey || '' }),
      signal: AbortSignal.timeout(60000)
    });
    const data = await res.json();
    const resp = document.getElementById('oracleResponse');
    resp.textContent = data.answer || 'No response.';
    resp.className = 'oracle-response visible';
  } catch (err) {
    const resp = document.getElementById('oracleResponse');
    resp.textContent = `Error: ${err.message}`;
    resp.className = 'oracle-response visible';
    resp.style.borderColor = '#ff4444';
  } finally {
    setLoading('oracle', false);
  }
}

// ── Truth Debt Ledger ─────────────────────────────────────────────────────────
function setupLedger() {
  document.getElementById('registerClaimBtn').addEventListener('click', registerClaim);
}

async function loadLedgerStats() {
  try {
    const res = await fetch(`${serverUrl}/ledger/stats`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return;
    const data = await res.json();
    document.getElementById('ledgerTotal').textContent    = data.total || 0;
    document.getElementById('ledgerVerified').textContent = data.verified || 0;
    document.getElementById('ledgerRefuted').textContent  = data.refuted || 0;
    document.getElementById('ledgerAccuracy').textContent = data.accuracy_rate ? `${data.accuracy_rate}%` : 'N/A';
  } catch { /* server not available */ }
}

async function registerClaim() {
  const claim = document.getElementById('claimInput').value.trim();
  const type  = document.getElementById('claimType').value;
  if (!claim) return;

  try {
    const res = await fetch(`${serverUrl}/ledger/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ claim, claim_type: type, source: 'extension' }),
      signal: AbortSignal.timeout(10000)
    });
    const data = await res.json();
    const success = document.getElementById('claimSuccess');
    success.textContent = `✅ Registered — ID: ${data.claim_id} · Falsifiability: ${data.falsifiability} · Check by: ${data.verification_deadline}`;
    success.style.display = 'block';
    document.getElementById('claimInput').value = '';
    setTimeout(() => { success.style.display = 'none'; }, 5000);
    await loadLedgerStats();
  } catch (err) {
    const success = document.getElementById('claimSuccess');
    success.style.background = '#2a0a0a';
    success.style.borderColor = '#ff4444';
    success.style.color = '#ff6666';
    success.textContent = `Error: ${err.message}`;
    success.style.display = 'block';
  }
}

// ── Shield Rune / Rune Memory ──────────────────────────────────────────────
async function loadRuneStatus() {
  try {
    const res = await fetch(`${serverUrl}/rune/status`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return;
    const data = await res.json();
    const el = (id) => document.getElementById(id);
    if (el('totalSeals'))   el('totalSeals').textContent   = data.total_seals || 0;
    if (el('btcAnchored'))  el('btcAnchored').textContent  = data.bitcoin_anchored || 0;
    if (el('pendingMerges')) el('pendingMerges').textContent = data.pending_merges || 0;
  } catch { /* server not available */ }
}

function setupRune() {
  document.getElementById('recordMemoryBtn')?.addEventListener('click', async () => {
    const content = document.getElementById('memoryInput')?.value?.trim();
    if (!content) return;
    try {
      const res = await fetch(`${serverUrl}/rune/record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, source: 'extension' }),
        signal: AbortSignal.timeout(15000)
      });
      const data = await res.json();
      showRuneResult(`✅ Recorded — ID: ${data.entry_id}\nContent preserved at Level 1 (GitHub).\nUse the ID above to seal with Shield Rune.`);
      document.getElementById('memoryInput').value = '';
      document.getElementById('sealIdInput').value = data.entry_id || '';
      loadRuneStatus();
    } catch (err) {
      showRuneResult(`❌ Error: ${err.message}`);
    }
  });

  document.getElementById('sealBtn')?.addEventListener('click', async () => {
    const seal_id = document.getElementById('sealIdInput')?.value?.trim();
    const note    = document.getElementById('sealNote')?.value?.trim() || '';
    if (!seal_id) return;
    try {
      const res = await fetch(`${serverUrl}/rune/seal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entry_id: seal_id, note }),
        signal: AbortSignal.timeout(20000)
      });
      const data = await res.json();
      showRuneResult(
        `🛡️ SEALED\n` +
        `Seal ID: ${data.seal_id || '?'}\n` +
        `Level: ${data.level || '?'} ${data.level >= 3 ? '— BITCOIN ANCHORED 🔒' : '— Nostr broadcast'}\n` +
        `Hash: ${(data.seal_hash||'').slice(0,32)}...\n` +
        `Anchor: ${(data.bitcoin_txid||'pending').slice(0,40)}\n\n` +
        `This memory cannot be erased without rewriting Bitcoin.`
      );
      document.getElementById('sealIdInput').value = '';
      loadRuneStatus();
    } catch (err) {
      showRuneResult(`❌ Seal error: ${err.message}`);
    }
  });
}

function showRuneResult(msg) {
  const el = document.getElementById('runeResult');
  if (!el) return;
  el.textContent = msg;
  el.style.display = 'block';
  setTimeout(() => { el.style.display = 'none'; }, 8000);
}
