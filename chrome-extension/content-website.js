// Runs on your Goosebumps website — adds "Open in Suno" button after generation

function genreToFolder(name) {
  return name.toLowerCase()
    .replace(/\s+/g, '')
    .replace(/-/g, '')
    .replace(/&/g, '')
    .replace(/\./g, '');
}

function addSunoButton() {
  const promptEl  = document.getElementById('spr');
  const actionRow = document.querySelector('.ar');
  if (!promptEl || !actionRow) return;
  if (document.getElementById('gb-suno-btn')) return;

  const btn = document.createElement('button');
  btn.id = 'gb-suno-btn';
  btn.className = 'ab cpb';
  btn.textContent = 'Open in Suno ↗';
  btn.style.cssText = 'background:#1a0a40;border-color:#a78bfa;';

  btn.onclick = () => {
    const prompt    = promptEl.textContent.trim();
    const genreName = document.getElementById('rg')?.textContent.trim() || 'music';
    const folder    = genreToFolder(genreName);

    const blueprint = {
      genre:               genreName,
      folder:              folder,
      frisson_score:       document.getElementById('sc')?.textContent.replace('%','').trim(),
      scientific_analysis: document.getElementById('sa')?.textContent.trim(),
      structure:           document.getElementById('ms')?.textContent.trim(),
      suno_prompt:         prompt,
      generated_at:        new Date().toISOString()
    };

    // Hand the job to the background coordinator. It decides whether to start
    // now or queue behind an in-flight job — so a 2nd generation can never
    // clobber the first. (Background also opens the Suno tab.)
    chrome.runtime.sendMessage(
      { type: 'ENQUEUE_JOB', job: { prompt, folder, blueprint } },
      (resp) => {
        if (resp && resp.queued) {
          btn.textContent = `Queued #${resp.position} — will run automatically`;
        } else {
          btn.textContent = 'Opening Suno...';
        }
        setTimeout(() => { btn.textContent = 'Open in Suno ↗'; }, 3000);
      }
    );
  };

  actionRow.appendChild(btn);

  // Auto-click after result is visible
  setTimeout(() => btn.click(), 1500);
}

// Watch for the result card to become visible
const observer = new MutationObserver(() => {
  const rc = document.getElementById('rc');
  if (rc && rc.classList.contains('show')) {
    addSunoButton();
  }
});

observer.observe(document.body, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: ['class']
});
