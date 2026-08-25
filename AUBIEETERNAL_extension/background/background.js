// background.js — AUBIEETERNAL Service Worker
// Handles context menu and cross-tab messaging

// ── Context menu setup ─────────────────────────────────────────────────────────
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id:       'aubie-analyze',
    title:    '🦅 Analyze with AUBIEETERNAL',
    contexts: ['selection', 'page'],
  });
  chrome.contextMenus.create({
    id:       'aubie-register-claim',
    title:    '📋 Register as Falsifiable Claim',
    contexts: ['selection'],
  });
  chrome.contextMenus.create({
    id:       'aubie-oracle',
    title:    '🔮 Ask Oracle about this',
    contexts: ['selection'],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const selected = info.selectionText?.trim() || '';

  if (info.menuItemId === 'aubie-analyze') {
    // Send to content script to show overlay
    try {
      await chrome.tabs.sendMessage(tab.id, {
        action: 'analyzeSelection',
        text:   selected,
      });
    } catch {
      // Content script not loaded — open popup
      chrome.action.openPopup();
    }
  }

  if (info.menuItemId === 'aubie-register-claim' && selected) {
    // Open popup with ledger tab and prefilled claim
    await chrome.storage.session.set({ prefillClaim: selected });
    chrome.action.openPopup();
  }

  if (info.menuItemId === 'aubie-oracle' && selected) {
    await chrome.storage.session.set({ prefillOracle: selected });
    chrome.action.openPopup();
  }
});

// ── Badge: show wonder index on icon ──────────────────────────────────────────
async function updateBadge() {
  try {
    const data = await chrome.storage.local.get('serverUrl');
    const url  = (data.serverUrl || 'http://100.105.81.27:8502') + '/status';
    const res  = await fetch(url, { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      const status = await res.json();
      const wonder = (status.wonder_index || 0).toFixed(1);
      chrome.action.setBadgeText({ text: wonder });
      chrome.action.setBadgeBackgroundColor({ color: '#f7931a' });
    } else {
      chrome.action.setBadgeText({ text: '?' });
      chrome.action.setBadgeBackgroundColor({ color: '#445577' });
    }
  } catch {
    chrome.action.setBadgeText({ text: '' });
  }
}

// Update badge every 5 minutes
updateBadge();
chrome.alarms.create('updateBadge', { periodInMinutes: 5 });
chrome.alarms.onAlarm.addListener(alarm => {
  if (alarm.name === 'updateBadge') updateBadge();
});

// ── Keyboard shortcut ──────────────────────────────────────────────────────────
chrome.commands.onCommand.addListener(async (command) => {
  if (command === 'analyze-selection') {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab) {
      chrome.tabs.sendMessage(tab.id, { action: 'analyzeSelection' });
    }
  }
});
