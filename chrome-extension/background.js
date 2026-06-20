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

async function autoPushToGitHub(genre, mp3Url, mp3Filename) {
  const cfg = await getConfig();
  if (!cfg.token) {
    console.log('[GB] No GitHub token saved — extension push OFF (watcher handles it). MP3 url was:', mp3Url);
    return;  // no token: coordinator inactive, nothing to advance
  }

  try {
    console.log(`[GB] Auto-push starting: music/${genre}/${mp3Filename}`);

    // 1. Fetch the MP3 bytes from Suno's download URL (freshest at this moment)
    let base64Mp3;
    try {
      const r = await fetch(mp3Url);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      base64Mp3 = arrayBufferToBase64(await r.arrayBuffer());
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
    const { sunoBlueprint } = await chrome.storage.local.get('sunoBlueprint');
    if (sunoBlueprint) {
      const bpStr = JSON.stringify(sunoBlueprint, null, 2);
      await putFile(cfg, `music/${genre}/${trackName}.json`, strToBase64(bpStr), `Blueprint for ${genre}: ${trackName}`);
      await putFile(cfg, `music/${genre}/blueprint.json`,    strToBase64(bpStr), `Blueprint (latest) for ${genre}`);
      console.log(`[GB] ✅ Blueprint pushed (paired: ${trackName}.json).`);
    } else {
      console.warn('[GB] No blueprint in storage — video will use the fallback description.');
    }

    // 4. Trigger the YouTube workflow (input excludes the "music/" prefix — workflow adds it)
    await triggerWorkflow(cfg, `${genre}/${mp3Filename}`);
    console.log('[GB] ✅ Workflow triggered. Watch GitHub Actions — no terminal needed.');
  } finally {
    // Advance the serial queue whether the push succeeded or fell back.
    await finishActiveAndNext();
  }
}
