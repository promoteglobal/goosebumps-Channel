// Save blueprint — uses msg.filename when provided (e.g. "neosoul/blueprint.json")
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type !== 'SAVE_BLUEPRINT') return;
  chrome.downloads.download({
    url:            msg.url,
    filename:       msg.filename || 'download.json',
    saveAs:         false,
    conflictAction: 'overwrite'
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
