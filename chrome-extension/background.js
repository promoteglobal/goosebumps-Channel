// Save blueprint from content-suno.js after MP3 is clicked
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type !== 'SAVE_BLUEPRINT') return;
  chrome.downloads.download({
    url:      msg.url,
    filename: `blueprint_${Date.now()}.json`,  // timestamped — no conflict possible
    saveAs:   false
  });
});

// Redirect audio downloads to the correct genre subfolder
chrome.downloads.onDeterminingFilename.addListener((item, suggest) => {
  const isAudio = item.mime?.includes('audio') || item.url?.includes('.mp3') || item.filename?.endsWith('.mp3');
  if (!isAudio) { suggest(); return; }

  chrome.storage.local.get('sunoGenre', ({ sunoGenre }) => {
    if (!sunoGenre) { suggest(); return; }
    const base = (item.filename || `song-${Date.now()}.mp3`).split(/[\\/]/).pop();
    suggest({ filename: `${sunoGenre}/${base}`, conflictAction: 'uniquify' });
  });

  return true;
});
