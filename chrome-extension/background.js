// Save blueprint from content-suno.js after MP3 is clicked
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type !== 'SAVE_BLUEPRINT') return;
  chrome.downloads.download({
    url:      msg.url,
    filename: `blueprint_${Date.now()}.json`,  // timestamped — no conflict possible
    saveAs:   false
  });
});

// ── Job coordinator (v1.6) ──────────────────────────────────────────────────
// Serial queue so a 2nd generation can NEVER clobber the first. Only one job
// is "active" at a time; extra generations wait in a queue and auto-start when
// the active one finishes. Active only in no-terminal (token) mode; with no
// token, each job starts immediately (unchanged v1.1-style behavior).

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type !== 'ENQUEUE_JOB') return;
  handleEnqueue(msg.job).then(sendResponse);
  return true;  // async response
});

async function handleEnqueue(job) {
  const { ghToken } = await chrome.storage.local.get('ghToken');

  // No token = watcher mode: behave like before — start immediately, no queue.
  if (!ghToken) {
    await startJob(job);
    return { queued: false };
  }

  const { gbActive, gbQueue = [] } = await chrome.storage.local.get(['gbActive', 'gbQueue']);
  const stale = gbActive && (Date.now() - gbActive.ts > 20 * 60 * 1000);

  if (!gbActive || stale) {
    await startJob(job);
    return { queued: false };
  }

  const q = [...gbQueue, job];
  await chrome.storage.local.set({ gbQueue: q });
  console.log(`[GB] Job queued (#${q.length}): ${job.folder} — waiting for active job to finish.`);
  return { queued: true, position: q.length };
}

async function startJob(job) {
  await chrome.storage.local.set({
    gbActive:      { folder: job.folder, ts: Date.now() },
    sunoPrompt:    job.prompt,
    sunoTimestamp: Date.now(),
    sunoGenre:     job.folder,
    sunoBlueprint: job.blueprint,
  });
  console.log(`[GB] Starting job: ${job.folder}`);
  chrome.tabs.create({ url: 'https://suno.com' });
}

async function finishActiveAndNext() {
  const { gbQueue = [] } = await chrome.storage.local.get('gbQueue');
  await chrome.storage.local.remove('gbActive');
  if (gbQueue.length > 0) {
    const [next, ...rest] = gbQueue;
    await chrome.storage.local.set({ gbQueue: rest });
    console.log(`[GB] Active job done — starting next queued: ${next.folder} (${rest.length} still waiting).`);
    await startJob(next);
  } else {
    console.log('[GB] Active job done — queue empty.');
  }
}

// Redirect audio downloads to the correct genre subfolder
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  const isAudio = item.mime?.includes('audio') || item.url?.includes('.mp3') || item.filename?.endsWith('.mp3');
  if (!isAudio) { suggest(); return; }

  chrome.storage.local.get('sunoGenre', ({ sunoGenre }) => {
    if (!sunoGenre) { suggest(); return; }
    const base = (item.filename || `song-${Date.now()}.mp3`).split(/[\\/]/).pop();
    suggest({ filename: `${sunoGenre}/${base}`, conflictAction: 'uniquify' });

    // Optional GitHub auto-push (v1.5). Inert unless a token is saved.
    autoPushToGitHub(sunoGenre, item.url, base)
      .catch(e => console.error('[GB] auto-push error:', e));
  });

  return true;
});

// ── GitHub auto-push (v1.5) ─────────────────────────────────────────────────
// All of this is a no-op until the user saves a token in the options page.

async function getConfig() {
  const { ghToken, ghOwner, ghRepo } = await chrome.storage.local.get(['ghToken', 'ghOwner', 'ghRepo']);
  return {
    token: ghToken || '',
    owner: ghOwner || 'promoteglobal',
    repo:  ghRepo  || 'goosebumps-Channel',
  };
}

function encodePath(p) {
  return p.split('/').map(encodeURIComponent).join('/');
}

function arrayBufferToBase64(buf) {
  let binary = '';
  const bytes = new Uint8Array(buf);
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function strToBase64(str) {
  return btoa(unescape(encodeURIComponent(str)));  // utf-8 safe
}

async function gh(cfg, path, opts = {}) {
  return fetch(`https://api.github.com/repos/${cfg.owner}/${cfg.repo}${path}`, {
    ...opts,
    headers: {
      'Authorization': `token ${cfg.token}`,
      'Accept': 'application/vnd.github+json',
      'Content-Type': 'application/json',
      ...(opts.headers || {}),
    },
  });
}

async function getSha(cfg, repoPath) {
  const res = await gh(cfg, `/contents/${encodePath(repoPath)}?ref=main`);
  if (res.status === 200) return (await res.json()).sha;
  return null;  // 404 = file doesn't exist yet
}

async function putFile(cfg, repoPath, base64Content, message) {
  const sha = await getSha(cfg, repoPath);
  const body = { message, content: base64Content, branch: 'main' };
  if (sha) body.sha = sha;
  const res = await gh(cfg, `/contents/${encodePath(repoPath)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PUT ${repoPath} → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function triggerWorkflow(cfg, mp3RepoRelative) {
  const res = await gh(cfg, `/actions/workflows/upload_youtube.yml/dispatches`, {
    method: 'POST',
    body: JSON.stringify({ ref: 'main', inputs: { mp3_filename: mp3RepoRelative } }),
  });
  if (!res.ok) throw new Error(`workflow dispatch → ${res.status}: ${await res.text()}`);
}

// Get the MP3 as base64. Direct fetch for https/CDN URLs; for blob: URLs (which
// only exist inside the Suno page) ask the Suno content script to read them —
// it shares the page's origin and CAN fetch the blob.
async function fetchMp3Base64(mp3Url) {
  if (!mp3Url.startsWith('blob:')) {
    const r = await fetch(mp3Url);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return arrayBufferToBase64(await r.arrayBuffer());
  }
  // Inject a fresh fetch into the Suno tab's page (MAIN world, where the blob
  // was created). Injecting on demand works even if the tab is old/stale —
  // no reliance on a pre-loaded content script (which can be orphaned after an
  // extension reload, giving "Receiving end does not exist").
  const tabs = await chrome.tabs.query({ url: 'https://suno.com/*' });
  if (!tabs.length) throw new Error('blob URL but no Suno tab open to read it');
  let lastErr = 'no Suno tab could read it';
  for (const tab of tabs) {
    try {
      const [res] = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        world: 'MAIN',
        args: [mp3Url],
        func: async (url) => {
          const r = await fetch(url);
          if (!r.ok) throw new Error('HTTP ' + r.status);
          const bytes = new Uint8Array(await r.arrayBuffer());
          let binary = '';
          const chunk = 0x8000;
          for (let i = 0; i < bytes.length; i += chunk) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
          }
          return btoa(binary);
        },
      });
      if (res && res.result) {
        console.log('[GB] Read blob via injected fetch.');
        return res.result;
      }
    } catch (e) {
      lastErr = e.message;
    }
  }
  throw new Error(`Suno tab could not read the blob (${lastErr})`);
}

async function autoPushToGitHub(genre, mp3Url, mp3Filename) {
  const cfg = await getConfig();
  if (!cfg.token) {
    console.log('[GB] No GitHub token saved — extension push OFF (watcher handles it). MP3 url was:', mp3Url);
    return;  // no token: coordinator inactive, nothing to advance
  }

  try {
    console.log(`[GB] Auto-push starting: music/${genre}/${mp3Filename}`);

    // 1. Fetch the MP3 bytes. A normal https CDN URL the service worker can fetch
    //    directly; a blob: URL is scoped to the Suno page, so the service worker
    //    cannot read it — hand that case to the Suno content script.
    let base64Mp3;
    try {
      base64Mp3 = await fetchMp3Base64(mp3Url);
    } catch (e) {
      console.error(`[GB] Could NOT fetch MP3 bytes (${e.message}). url=${mp3Url}`);
      console.error('[GB] Falling back: leave watch_and_push.py to push this one.');
      return;  // finally still advances the queue
    }

    // 2. Push the MP3
    const trackName = mp3Filename.replace(/\.mp3$/i, '');
    await putFile(cfg, `music/${genre}/${mp3Filename}`, base64Mp3, `Add ${genre}: ${trackName}`);
    console.log('[GB] ✅ MP3 pushed.');

    // 3. Push the blueprint PAIRED WITH THE SONG by name — music/<genre>/<Song>.json
    //    so the posting bot can later use this song's EXACT description. (Also
    //    write blueprint.json for the immediate-post path / backward compat.)
    //    Tag with buffered=true when not posting now, so the auto-renamer only
    //    renames songs waiting in the buffer (never one being posted live).
    const { gbBufferMode } = await chrome.storage.local.get('gbBufferMode');
    const { sunoBlueprint } = await chrome.storage.local.get('sunoBlueprint');
    if (sunoBlueprint) {
      const bp = { ...sunoBlueprint, buffered: !!gbBufferMode };
      const bpStr = JSON.stringify(bp, null, 2);
      await putFile(cfg, `music/${genre}/${trackName}.json`, strToBase64(bpStr), `Blueprint for ${genre}: ${trackName}`);
      await putFile(cfg, `music/${genre}/blueprint.json`,    strToBase64(bpStr), `Blueprint (latest) for ${genre}`);
      console.log(`[GB] ✅ Blueprint pushed (paired: ${trackName}.json, buffered=${!!gbBufferMode}).`);
    } else {
      console.warn('[GB] No blueprint in storage — video will use the fallback description.');
    }

    // 4. Post now — UNLESS Buffer mode is on, then just leave it in GitHub for
    //    the daily auto-poster bot to pick up later.
    if (gbBufferMode) {
      console.log('[GB] 🪣 Buffer mode ON — saved to GitHub, NOT posting. The daily bot will post it.');
    } else {
      await triggerWorkflow(cfg, `${genre}/${mp3Filename}`);
      console.log('[GB] ✅ Workflow triggered. Watch GitHub Actions — no terminal needed.');
    }
  } finally {
    // Advance the serial queue whether the push succeeded or fell back.
    await finishActiveAndNext();
  }
}
