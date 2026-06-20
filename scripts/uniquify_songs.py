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


def transcribe(mp3path):
    """Return (lyrics_text, is_instrumental). Best-effort; never raises."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, _info = model.transcribe(
            str(mp3path), beam_size=1, condition_on_previous_text=False)
        parts = []
        for seg in segments:
            # Skip segments Whisper thinks are non-speech (music/hallucination).
            if getattr(seg, "no_speech_prob", 1.0) < 0.5 and seg.text.strip():
                parts.append(seg.text.strip())
        text = re.sub(r"\s+", " ", " ".join(parts)).strip()
        # Heuristic: real lyrics have a decent amount of distinct words.
        distinct = len({w.lower() for w in re.findall(r"[A-Za-z']+", text)})
        instrumental = len(text) < 20 or distinct < 6
        return ("" if instrumental else text), instrumental
    except Exception as e:
        log(f"  transcription failed ({e}); treating as instrumental.")
        return "", True


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
    t = re.sub(r"[^A-Za-z0-9 ]", "", t)       # FFmpeg/file-safe; no ' : ,
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
        f"- Title Case, only letters/numbers/spaces (no quotes, colons, commas, emojis)\n"
        f"- Do NOT reuse any of these already-taken names: {avoid_list}\n\n"
        f"Reply with ONLY the title — no quotes, no explanation, nothing else."
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=32,
        messages=[{"role": "user", "content": prompt}],
    )
    text = next((b.text for b in msg.content if b.type == "text"), "")
    return clean_title(text)


def main():
    todo = []
    for mp3 in sorted(MUSIC.rglob("*.mp3")):
        jp = mp3.with_suffix(".json")
        if not jp.exists():
            continue
        try:
            bp = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        if bp.get("buffered") and not bp.get("final_title"):
            todo.append((mp3, jp, bp))

    if not todo:
        log("No buffered songs need processing.")
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    except Exception as e:
        log(f"Anthropic client unavailable ({e}); leaving songs as-is.")
        return

    used = existing_names()
    changed = False
    for mp3, jp, bp in todo:
        lyrics, instrumental = transcribe(mp3)
        bp["lyrics"]       = lyrics
        bp["instrumental"] = instrumental
        log(f"{mp3.name}: {'instrumental' if instrumental else str(len(lyrics)) + ' chars of lyrics'}")

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

    if not changed:
        return

    subprocess.run(["git", "config", "user.name", "goosebumps-bot"], cwd=ROOT)
    subprocess.run(["git", "config", "user.email", "bot@goosebumps-channel"], cwd=ROOT)
    subprocess.run(["git", "add", "-A", "music/"], cwd=ROOT)
    subprocess.run(["git", "commit", "-m", "Auto-rename buffered songs to unique titles (with transcription)"], cwd=ROOT)
    subprocess.run(["git", "pull", "--rebase", "--autostash"], cwd=ROOT)
    subprocess.run(["git", "push"], cwd=ROOT)
    log("Pushed renamed songs.")


if __name__ == "__main__":
    main()
