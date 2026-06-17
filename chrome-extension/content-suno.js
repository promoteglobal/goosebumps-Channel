// Goosebumps Helper — paste, create, library, watch, click 3-dots

const delay = ms => new Promise(r => setTimeout(r, ms));
let watching = false;

async function fullClick(el) {
  ['pointerover','pointerenter','mouseover','mouseenter'].forEach(e =>
    el.dispatchEvent(new MouseEvent(e, { bubbles: true, cancelable: true }))
  );
  await delay(150);
  el.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, isPrimary: true }));
  el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
  await delay(80);
  el.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, cancelable: true, isPrimary: true }));
  el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
  el.click();
}

function showBanner(msg, color = '#2d1b69') {
  document.querySelectorAll('.gb-banner').forEach(b => b.remove());
  const d = document.createElement('div');
  d.className = 'gb-banner';
  d.textContent = msg;
  d.style.cssText = `position:fixed;top:20px;right:20px;z-index:99999;
    background:${color};color:#e8deff;padding:14px 20px;border-radius:12px;
    font-size:14px;font-family:sans-serif;box-shadow:0 4px 24px rgba(0,0,0,.6);
    border:1px solid #7c5cbf;`;
  document.body.appendChild(d);
  setTimeout(() => { d.style.transition='opacity .5s'; d.style.opacity='0'; }, 4000);
  setTimeout(() => d.remove(), 4500);
}

// ── 1. Paste prompt ───────────────────────────────────────────────────────────

function findInput() {
  return document.querySelector('textarea[placeholder*="prompt" i]')
    || document.querySelector('textarea[placeholder*="describe" i]')
    || document.querySelector('textarea[placeholder*="song" i]')
    || document.querySelector('[contenteditable="true"]')
    || document.querySelector('textarea');
}

function pasteIntoInput(el, text) {
  el.focus();
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')?.set;
  if (setter) setter.call(el, text);
  el.dispatchEvent(new Event('input',  { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}

// ── 2. Click Create ───────────────────────────────────────────────────────────

function clickCreate() {
  const btn = [...document.querySelectorAll('button')]
    .find(b => /^create$/i.test(b.textContent.trim()) || /^generate$/i.test(b.textContent.trim()))
    || document.querySelector('button[type="submit"]');

  if (btn) {
    btn.click();
    showBanner('🎵 Create clicked — going to Library in 2s...', '#052e16');
    setTimeout(clickLibrary, 2000);
  } else {
    showBanner('⚠️ Create button not found — click it manually then go to Library.', '#7f1d1d');
  }
}

// ── 3. Click Library ──────────────────────────────────────────────────────────

function clickLibrary() {
  const btn = [...document.querySelectorAll('a, button')].find(el =>
    /^library$/i.test(el.textContent.trim()) ||
    /library/i.test(el.getAttribute('aria-label') || '') ||
    /\/library/i.test(el.getAttribute('href') || '')
  );
  if (btn) {
    btn.click();
    showBanner('📚 Library — watching for 2 new songs to finish...', '#1e1040');
  } else {
    showBanner('⚠️ Library button not found — click it manually.', '#7f1d1d');
  }
  // Start watching regardless — works on current page
  setTimeout(startWatching, 3000);
}

// ── 4. Watch for songs to complete ───────────────────────────────────────────

function startWatching() {
  if (watching) return;
  watching = true;

  // Only track TOP-LEVEL completed clips (not nested children of another clip)
  function topLevelClips() {
    return [...document.querySelectorAll('[data-clip-status="complete"]')]
      .filter(el => !el.parentElement?.closest('[data-clip-status="complete"]'));
  }

  // Snapshot ALL clips in any state (complete, generating, queued) so that
  // in-progress songs from previous sessions can't count as new when they finish
  const knownAtStart = new Set(document.querySelectorAll('[data-clip-status]'));

  const seen     = new Set(topLevelClips());
  const newSongs = [];

  showBanner(`👀 Watching — ignoring ${seen.size} complete + ${knownAtStart.size} known clips...`, '#1e1040');

  const iv = setInterval(async () => {
    topLevelClips().forEach(clip => {
      if (!seen.has(clip) && !knownAtStart.has(clip)) {
        seen.add(clip);
        newSongs.push(clip);
        if (newSongs.length === 1) showBanner('⏳ 1st song done — waiting for 2nd...', '#1e1040');
      }
    });

    if (newSongs.length >= 2) {
      clearInterval(iv);
      watching = false;

      const clip  = newSongs[1];
      const label = clip.getAttribute('aria-label') || '2nd song';
      showBanner(`🎶 Both done! Opening 3-dots on: "${label}"`, '#052e16');
      await delay(600);

      // Find 3-dots button — search clip and its parent in case clip is not the root card
      const card = clip.closest('[role="group"]') || clip;
      const btn  = card.querySelector('button[aria-label="More options"]')
               || card.querySelector('button[data-context-menu-trigger="true"]')
               || card.querySelector('button.context-menu-button');

      if (btn) {
        // Fire full event sequence so React registers the interaction
        ['pointerover','pointerenter','mouseover','mouseenter'].forEach(e =>
          btn.dispatchEvent(new MouseEvent(e, { bubbles: true, cancelable: true }))
        );
        await delay(150);
        btn.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, cancelable: true, isPrimary: true }));
        btn.dispatchEvent(new MouseEvent('mousedown',  { bubbles: true, cancelable: true }));
        await delay(80);
        btn.dispatchEvent(new PointerEvent('pointerup',   { bubbles: true, cancelable: true, isPrimary: true }));
        btn.dispatchEvent(new MouseEvent('mouseup',    { bubbles: true, cancelable: true }));
        btn.click();
        showBanner('🔵 Menu opened — finding Download...', '#1e1040');
        await delay(1000);

        // Step 2 — click Download (5th item, triggers MP3 submenu)
        const downloadBtn = [...document.querySelectorAll('div.context-menu-item button')]
          .find(b => b.textContent.includes('Download') && b.offsetHeight > 0);

        if (!downloadBtn) {
          showBanner('⚠️ Menu open but Download not found — click Download → MP3 manually.', '#7f1d1d');
          return;
        }

        showBanner('🔵 Hovering Download...', '#1e1040');
        ['pointerover','pointerenter','mouseover','mouseenter'].forEach(e =>
          downloadBtn.dispatchEvent(new MouseEvent(e, { bubbles: true, cancelable: true }))
        );
        await delay(1200);

        // Step 3 — click MP3 (first item in Download submenu)
        // Don't check offsetHeight — submenu may be CSS-hidden until hover
        const mp3Btn =
          [...document.querySelectorAll('div.context-menu-item button')]
            .find(b => /^mp3$/i.test(b.textContent.trim()))
          || [...document.querySelectorAll('button, li, a, span')]
            .find(b => /^mp3$/i.test(b.textContent.trim()))
          || [...document.querySelectorAll('button, li, a, span')]
            .find(b => b.textContent.trim().toLowerCase().startsWith('mp3'));

        if (mp3Btn) {
          showBanner('🔵 Clicking MP3...', '#1e1040');
          await fullClick(mp3Btn);
          await delay(600);

          // Save blueprint.json to the same genre folder
          const { sunoGenre, sunoBlueprint } = await chrome.storage.local.get(['sunoGenre', 'sunoBlueprint']);
          if (sunoGenre && sunoBlueprint) {
            const json = JSON.stringify(sunoBlueprint, null, 2);
            const url  = 'data:application/json,' + encodeURIComponent(json);
            chrome.runtime.sendMessage({
              type:     'SAVE_BLUEPRINT',
              url,
              filename: `${sunoGenre}/blueprint.json`
            });
            showBanner(`✅ Saving blueprint.json → ${sunoGenre}/blueprint.json`, '#052e16');
          } else {
            showBanner('⚠️ Missing genre or blueprint data — blueprint.json not saved.', '#7f1d1d');
          }
        } else {
          showBanner('⚠️ Download hovered but MP3 not found — click MP3 manually.', '#7f1d1d');
        }
      } else {
        showBanner('⚠️ 3-dots button not found in card — click it manually.', '#7f1d1d');
      }
    }
  }, 3000);

  // 10 min timeout
  setTimeout(() => {
    clearInterval(iv);
    watching = false;
    showBanner('⚠️ Timed out — click 3-dots → Download → MP3 manually.', '#7f1d1d');
  }, 10 * 60 * 1000);
}

// ── Entry point ───────────────────────────────────────────────────────────────

async function tryPaste() {
  const { sunoPrompt, sunoTimestamp } = await chrome.storage.local.get(['sunoPrompt', 'sunoTimestamp']);
  if (!sunoPrompt || Date.now() - sunoTimestamp > 15 * 60 * 1000) return;

  showBanner('⏳ Finding Suno input...');
  let tries = 0;
  const iv = setInterval(() => {
    const input = findInput();
    if (input) {
      clearInterval(iv);
      pasteIntoInput(input, sunoPrompt);
      chrome.storage.local.remove(['sunoPrompt', 'sunoTimestamp']);
      showBanner('✅ Pasted! Clicking Create...', '#052e16');
      setTimeout(clickCreate, 1200);
      return;
    }
    if (++tries >= 30) { clearInterval(iv); showBanner('⚠️ Input not found — paste manually.', '#7f1d1d'); }
  }, 1000);
}

setTimeout(tryPaste, 1500);
