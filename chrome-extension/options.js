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
