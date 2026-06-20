// Settings page — store GitHub token + repo so background.js can auto-push.

const $ = id => document.getElementById(id);

// Load existing values
chrome.storage.local.get(['ghToken', 'ghOwner', 'ghRepo'], ({ ghToken, ghOwner, ghRepo }) => {
  if (ghToken) $('token').value = ghToken;
  $('owner').value = ghOwner || 'promoteglobal';
  $('repo').value  = ghRepo  || 'goosebumps-Channel';
  if (ghToken) setStatus('Token is set — extension auto-push is ON.', 'ok');
});

function setStatus(msg, cls) {
  const el = $('status');
  el.textContent = msg;
  el.className = 'status ' + (cls || '');
}

$('save').onclick = () => {
  const token = $('token').value.trim();
  const owner = $('owner').value.trim() || 'promoteglobal';
  const repo  = $('repo').value.trim()  || 'goosebumps-Channel';
  if (!token) { setStatus('Enter a token, or use "Turn OFF" to clear.', 'err'); return; }
  chrome.storage.local.set({ ghToken: token, ghOwner: owner, ghRepo: repo }, () => {
    setStatus('Saved — auto-push is ON. Run a generation to test.', 'ok');
  });
};

$('clear').onclick = () => {
  chrome.storage.local.remove(['ghToken'], () => {
    $('token').value = '';
    setStatus('Token cleared — auto-push is OFF. The terminal watcher will handle uploads.', 'ok');
  });
};

// Buffer mode toggle — save songs to GitHub without posting (the daily bot posts them)
function updateBufStatus(on) {
  $('bufStatus').textContent = on
    ? 'Buffer mode ON — new songs are saved to GitHub and NOT posted. The daily bot posts them.'
    : 'Buffer mode OFF — new songs post to YouTube immediately.';
  $('bufStatus').className = 'status ' + (on ? 'ok' : '');
}

chrome.storage.local.get('gbBufferMode', ({ gbBufferMode }) => {
  $('buffer').checked = !!gbBufferMode;
  updateBufStatus(!!gbBufferMode);
});

$('buffer').onchange = () => {
  const on = $('buffer').checked;
  chrome.storage.local.set({ gbBufferMode: on }, () => updateBufStatus(on));
};
