"""
uniquify_songs.py - Transcribe each buffered song, then give it a unique,
catchy, original title based on what it's actually about.

For every song waiting in the buffer (paired .json has "buffered": true and no
"final_title" yet):
  1. Transcribe it with Whisper. A vocal track yields lyrics; an instrumental
     yields ~nothing, so we flag it instrumental.
  2. Store "lyrics" + "instrumental" in the .json (the footage matcher reuses
     this — lyric-matched visuals like "muddy boots").
  3. Ask Claude for an original, evocative, clickable title — from a vivid image
     in the lyrics for vocal tracks, or from the music's mood for instrumentals.
  4. Rename the MP3 + .json to that title and mark it done.

Only buffered songs are touched (a song posted immediately keeps its name).
Idempotent via the final_title marker. Needs ANTHROPIC_API_KEY.
"""
import os, sys, json, re, random, subprocess
from pathlib import Path

ROOT  = Path(__file__).parent.parent
MUSIC = ROOT / "music"
MODEL = "claude-opus-4-8"


def log(msg):
    sys.stderr.write(msg + "\n")


# Genres whose vocals are in a known language — pass it to Whisper so it
# transcribes sung Korean/Japanese/etc. far more accurately (and stops
# false-flagging vocals as instrumental).
GENRE_LANG = {
    "kpop": "ko", "kdrama": "ko", "trot": "ko",
    "jpop": "ja", "jrock": "ja", "citypop": "ja", "anime": "ja", "enka": "ja",
    "cpop": "zh", "mandopop": "zh", "cantopop": "zh",
    "bollywood": "hi", "bhangra": "pa",
    "dangdut": "id",
    "flamenco": "es", "reggaeton": "es",
    "chanson": "fr", "fado": "pt",
}


def lang_for_genre(genre):
    return GENRE_LANG.get(re.sub(r"[^a-z]", "", (genre or "").lower()))


def transcribe(mp3path, lang_hint=None):
    """Return (lyrics_text, is_instrumental, segments). Best-effort; never raises.
    `segments` is a list of {start, end, text} for matching footage to words.
    lang_hint (e.g. 'ko' for kpop) makes Whisper much better at sung lyrics."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(
            str(mp3path), beam_size=1, condition_on_previous_text=False,
            language=lang_hint)   # None = auto-detect
        parts, segs = [], []
        for seg in segments:
            # Skip segments Whisper thinks are non-speech (music/hallucination).
            if getattr(seg, "no_speech_prob", 1.0) < 0.5 and seg.text.strip():
                txt = seg.text.strip()
                parts.append(txt)
                segs.append({"start": round(seg.start, 2),
                             "end":   round(seg.end, 2), "text": txt})
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        # Script-agnostic: count letters of ANY language (Korean, Japanese,
        # Latin, ...). The old check only counted Latin words, so it wrongly
        # marked fully-transcribed Korean songs as instrumental.
        letters = re.sub(r"[\W\d_]+", "", text, flags=re.UNICODE)
        instrumental = len(letters) < 12
        if instrumental:
            return "", True, []
        return text, False, segs
    except Exception as e:
        log(f"  transcription failed ({e}); treating as instrumental.")
        return "", True, []


def existing_names():
    used = set()
    for p in MUSIC.rglob("*.mp3"):
        used.add(p.stem.lower())
    for p in MUSIC.rglob("*.json"):
        if p.name == "blueprint.json":
            continue
        try:
            t = json.load(open(p, encoding="utf-8")).get("final_title")
            if t:
                used.add(t.lower())
        except Exception:
            pass
    return used


def clean_title(t):
    t = t.strip().strip('"').strip("'").strip()
    # Keep unicode letters (Korean, Japanese, Hindi, ...); drop only the chars
    # that break filenames or the FFmpeg drawtext filtergraph.
    t = re.sub(r'[\\/:*?"<>|\'`,%\[\]\n\r\t]', " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def generate_title(client, bp, lyrics, instrumental, avoid):
    genre     = bp.get("genre", "instrumental")
    avoid_list = ", ".join(sorted(avoid)[:50]) or "none yet"
    if instrumental:
        about = (f"This is an INSTRUMENTAL {genre} track with no lyrics.\n"
                 f"Its character: {(bp.get('structure') or '')[:500]}\n"
                 f"{(bp.get('scientific_analysis') or '')[:200]}\n"
                 f"Base the title on the mood and imagery the music evokes.")
    else:
        about = (f"This is a {genre} song. Its lyrics:\n{lyrics[:1500]}\n"
                 f"Base the title on a vivid, concrete image or theme from the lyrics.")
    prompt = (
        f"Invent ONE original song TITLE for a track engineered to give "
        f"listeners goosebumps.\n\n{about}\n\n"
        f"Requirements:\n"
        f"- 2 to 5 words, evocative and catchy — something a listener wants to click\n"
        f"- ORIGINAL: must NOT be the title of any known or famous song\n"
        f"- Write it in the language that fits the song: the lyrics' language for "
        f"vocal tracks (native script is great — Korean for K-pop, Japanese for "
        f"J-pop, Hindi for Bollywood), or the genre's natural language for instrumentals\n"
        f"- Only letters/numbers/spaces — no quotes, colons, commas, or emojis\n"
        f"- Do NOT reuse any of these already-taken names: {avoid_list}\n\n"
        f"Reply with ONLY the title — no quotes, no explanation, nothing else."
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=32,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return clean_title(text)


def dispatch_upload(rel):
    """Trigger the video+upload pipeline for an immediate-mode song (buffer off)."""
    pat = os.environ.get("DISPATCH_PAT", "")
    if not pat:
        log(f"No DISPATCH_PAT — cannot auto-post {rel}")
        return
    import urllib.request
    repo = os.environ.get("GITHUB_REPOSITORY", "promoteglobal/goosebumps-Channel")
    body = json.dumps({"ref": "main", "inputs": {"mp3_filename": rel}}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/upload_youtube.yml/dispatches",
        data=body, method="POST",
        headers={"Authorization": f"token {pat}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req)
        log(f"Auto-posting (immediate): {rel}")
    except Exception as e:
        log(f"Dispatch failed for {rel}: {e}")


def main():
    # Process every NEW song (has the buffered flag, not yet processed) — both
    # buffer-on and buffer-off go through the same transcribe + title + lyric
    # path. Old songs (no buffered flag) are left alone.
    todo = []
    for mp3 in sorted(MUSIC.rglob("*.mp3")):
        jp = mp3.with_suffix(".json")
        if not jp.exists():
            continue
        try:
            bp = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        if "buffered" in bp and not bp.get("final_title"):
            todo.append((mp3, jp, bp))

    if not todo:
        log("No songs need processing.")
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    except Exception as e:
        log(f"Anthropic client unavailable ({e}); posting immediate songs as-is.")
        for mp3, jp, bp in todo:           # buffer-off must never silently fail
            if not bp.get("buffered"):
                dispatch_upload(f"{mp3.parent.name}/{mp3.name}")
        return

    used = existing_names()
    changed = False
    immediate = []   # buffer-off songs -> auto-post once processed
    for mp3, jp, bp in todo:
        lyrics, instrumental, segs = transcribe(mp3, lang_for_genre(mp3.parent.name))
        bp["lyrics"]         = lyrics
        bp["instrumental"]   = instrumental
        bp["lyric_segments"] = segs        # timestamped, for footage matching
        log(f"{mp3.name}: {'instrumental' if instrumental else str(len(lyrics)) + ' chars of lyrics, ' + str(len(segs)) + ' segments'}")

        title = ""
        for _ in range(5):
            try:
                cand = generate_title(client, bp, lyrics, instrumental, used)
            except Exception as e:
                log(f"  title generation failed for {mp3.name} ({e})")
                cand = ""
            if cand and 2 <= len(cand) <= 60 and cand.lower() not in used:
                title = cand
                break
        if not title:
            title = f"{bp.get('genre', 'Goosebumps')} {random.randint(1000, 9999)}"
        used.add(title.lower())

        bp["final_title"] = title
        new_mp3  = mp3.parent / f"{title}.mp3"
        new_json = mp3.parent / f"{title}.json"
        os.rename(mp3, new_mp3)
        with open(new_json, "w", encoding="utf-8") as f:
            json.dump(bp, f, indent=2, ensure_ascii=False)
        if jp.exists() and jp != new_json:
            jp.unlink()
        log(f"Renamed: {mp3.name}  ->  {title}.mp3")
        changed = True
        if not bp.get("buffered"):
            immediate.append(f"{mp3.parent.name}/{title}.mp3")

    if not changed:
        return

    subprocess.run(["git", "config", "user.name", "goosebumps-bot"], cwd=ROOT)
    subprocess.run(["git", "config", "user.email", "bot@goosebumps-channel"], cwd=ROOT)
    subprocess.run(["git", "add", "-A", "music/"], cwd=ROOT)
    if subprocess.run(["git", "commit", "-m",
                       "Auto-rename buffered songs to unique titles"], cwd=ROOT).returncode != 0:
        log("Nothing to commit.")
        return
    pushed = False
    for attempt in range(3):
        subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=ROOT)
        if subprocess.run(["git", "push"], cwd=ROOT).returncode == 0:
            pushed = True
            break
        log(f"push attempt {attempt + 1} failed — retrying")
    log("Pushed renamed songs." if pushed else "WARNING: push failed after retries.")

    # Immediate-mode songs (buffer off): auto-post now that they're transcribed,
    # titled, and on GitHub. Buffered songs wait for the daily bot instead.
    if pushed:
        for rel in immediate:
            dispatch_upload(rel)


def dry_run(rel):
    """Read-only: transcribe one existing song and print the result. Renames
    nothing, pushes nothing, changes nothing — safe on any song, even posted."""
    mp3 = (ROOT / rel) if rel.startswith("music/") else (MUSIC / rel)
    if not mp3.exists():
        log(f"Not found: {mp3}")
        return
    lang = lang_for_genre(mp3.parent.name)
    log(f"DRY RUN — transcribing {mp3.name} (genre={mp3.parent.name}, lang hint={lang}) with the medium model...")
    lyrics, instrumental, segs = transcribe(mp3, lang)
    log(f"  instrumental: {instrumental}")
    log(f"  lyrics ({len(lyrics)} chars): {lyrics[:400]}")
    log(f"  segments: {len(segs)}")
    for s in segs[:10]:
        log(f"    [{s['start']:.0f}-{s['end']:.0f}s] {s['text']}")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--dry-run":
        dry_run(sys.argv[2])
    else:
        main()
