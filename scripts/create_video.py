"""
create_video.py - Genre-matched moving (Pexels) backgrounds with branded overlay.
Falls back to a solid themed gradient if Pexels is unavailable, so a video is
ALWAYS produced. Supports unicode filenames (Korean, Portuguese, Japanese, etc.)
"""
import subprocess, json, sys, os, random, urllib.request, urllib.parse, urllib.error
from pathlib import Path
from datetime import datetime

# Pexels (Cloudflare) returns 403 to the default Python urllib User-Agent — send a browser one.
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

WIDTH, HEIGHT, FPS = 1920, 1080, 24

THEMES = {
    "blues":         {"bg":"020818","w1":"4488ff","w2":"224488","tx":"cce0ff","ac":"4488ff"},
    "jazz":          {"bg":"120800","w1":"ff9933","w2":"cc7722","tx":"ffe0b0","ac":"ff9933"},
    "kpop":          {"bg":"0d0015","w1":"ff44ff","w2":"aa00ff","tx":"ffccff","ac":"ff44ff"},
    "classical":     {"bg":"080808","w1":"e8d5a0","w2":"c4a96e","tx":"fff8e7","ac":"e8d5a0"},
    "hiphop":        {"bg":"050505","w1":"ff4444","w2":"ff8800","tx":"ffffff","ac":"ff4444"},
    "ambient":       {"bg":"001510","w1":"44ffcc","w2":"00ccaa","tx":"ccffee","ac":"44ffcc"},
    "rock":          {"bg":"100000","w1":"ff2200","w2":"ff6600","tx":"ffffff","ac":"ff2200"},
    "gospel":        {"bg":"100f00","w1":"ffee44","w2":"ffcc00","tx":"fffff0","ac":"ffcc00"},
    "cinematic":     {"bg":"000510","w1":"4488ff","w2":"0044cc","tx":"cce0ff","ac":"4488ff"},
    "lofi":          {"bg":"080810","w1":"99aacc","w2":"667799","tx":"dde0ee","ac":"99aacc"},
    "afrobeat":      {"bg":"0a0500","w1":"ff8833","w2":"ff4400","tx":"ffe0cc","ac":"ff8833"},
    "latin":         {"bg":"100500","w1":"ff6633","w2":"ffcc00","tx":"ffe8cc","ac":"ffcc00"},
    "edm":           {"bg":"000a15","w1":"00ffff","w2":"ff00ff","tx":"ccffff","ac":"00ffff"},
    "rnb":           {"bg":"100008","w1":"ff44aa","w2":"cc0066","tx":"ffccee","ac":"ff44aa"},
    "folk":          {"bg":"0a0800","w1":"ccaa44","w2":"997733","tx":"fff0cc","ac":"ccaa44"},
    "celtic":        {"bg":"001008","w1":"44cc88","w2":"009944","tx":"ccffdd","ac":"44cc88"},
    "indianclassical":{"bg":"100500","w1":"ff6600","w2":"ffcc00","tx":"ffe8cc","ac":"ff6600"},
    "bollywood":     {"bg":"150500","w1":"ff6600","w2":"ffcc00","tx":"ffe8cc","ac":"ff6600"},
    "electronic":    {"bg":"000a15","w1":"00ffff","w2":"0088ff","tx":"ccffff","ac":"00ffff"},
    "country":       {"bg":"0d0800","w1":"ddaa44","w2":"aa7722","tx":"fff0cc","ac":"ddaa44"},
    "metal":         {"bg":"0a0000","w1":"ff2200","w2":"880000","tx":"ffffff","ac":"ff2200"},
    "reggae":        {"bg":"001200","w1":"44ff44","w2":"ffee00","tx":"ccffcc","ac":"44ff44"},
    "bossanova":     {"bg":"001008","w1":"44cc88","w2":"ffcc00","tx":"ccffdd","ac":"44cc88"},
    "synthwave":     {"bg":"0a0015","w1":"ff44ff","w2":"00ffff","tx":"ffccff","ac":"ff44ff"},
    "middleeastern": {"bg":"100800","w1":"ffcc44","w2":"ff8800","tx":"fff0cc","ac":"ffcc44"},
    "nordicfolk":    {"bg":"000810","w1":"aaccff","w2":"4488cc","tx":"ddeeff","ac":"aaccff"},
    "deephouse":     {"bg":"000510","w1":"4488ff","w2":"aa00ff","tx":"cce0ff","ac":"4488ff"},
    "tango":         {"bg":"100000","w1":"ff4444","w2":"ffcc00","tx":"ffe0cc","ac":"ff4444"},
    "jpop":          {"bg":"0d0015","w1":"ff88cc","w2":"aa44ff","tx":"ffccee","ac":"ff88cc"},
    "neosoul":       {"bg":"100008","w1":"ff88aa","w2":"cc4466","tx":"ffddee","ac":"ff88aa"},
    "flamenco":      {"bg":"100300","w1":"ff3300","w2":"ffaa00","tx":"ffe8cc","ac":"ff3300"},
    "world":         {"bg":"0a0510","w1":"dd88ff","w2":"8833cc","tx":"eeccff","ac":"dd88ff"},
    "default":       {"bg":"0a0a1a","w1":"7f77dd","w2":"5dcaa5","tx":"eeedfe","ac":"7f77dd"},
}

# Genre -> Pexels search query. Chosen for awe/calm footage (vastness, light,
# nature) that amplifies frisson, per the psychology of goosebumps.
PEXELS_QUERIES = {
    "blues":          "rain window moody night",
    "jazz":           "rainy city night neon reflection",
    "kpop":           "neon city night lights",
    "classical":      "golden sunrise mountains aerial",
    "hiphop":         "city street night lights timelapse",
    "ambient":        "slow motion clouds time lapse sky",
    "rock":           "storm clouds dramatic sky",
    "gospel":         "sun rays through clouds heaven light",
    "cinematic":      "epic mountain landscape aerial drone",
    "lofi":           "cozy rain window night warm",
    "afrobeat":       "african savanna sunset wildlife",
    "latin":          "warm sunset ocean waves",
    "edm":            "abstract neon light motion",
    "rnb":            "purple smoke slow motion",
    "folk":           "misty forest mountains green",
    "celtic":         "misty green hills ireland landscape",
    "indianclassical":"himalaya sunrise temple mist",
    "bollywood":      "india temple golden sunrise",
    "electronic":     "abstract digital light motion",
    "country":        "countryside fields golden hour",
    "metal":          "dark storm lightning night",
    "reggae":         "tropical beach palm ocean sunset",
    "bossanova":      "calm beach sunset waves",
    "synthwave":      "retro neon grid sunset",
    "middleeastern":  "desert dunes sunset",
    "nordicfolk":     "northern lights aurora snow",
    "deephouse":      "city lights bokeh night",
    "tango":          "moody red light dance",
    "jpop":           "tokyo neon night city",
    "neosoul":        "warm bokeh lights slow motion",
    "flamenco":       "spanish sunset warm landscape",
    "world":          "earth nature aerial cinematic",
    "default":        "nature aerial cinematic landscape",
}

def get_theme(genre):
    key = genre.lower().replace(" ","").replace("-","").replace("_","")
    for k in THEMES:
        if key==k or (len(key)>=4 and len(k)>=4 and key[:4]==k[:4]):
            return THEMES[k]
    return THEMES["default"]

def normalize_blueprint(bp):
    if not bp.get("scientific_analysis") and bp.get("scientific_note"):
        bp["scientific_analysis"] = bp["scientific_note"]
    return bp

def find_blueprint(mp3_path):
    # 1. Per-song blueprint paired by name (music/<genre>/<Song Name>.json) —
    #    this is the song's EXACT description, used by the posting bot so the
    #    description always matches the song.
    per_song = mp3_path.with_suffix(".json")
    if per_song.exists():
        with open(per_song, encoding="utf-8") as f:
            return normalize_blueprint(json.load(f))

    # 2. Per-genre blueprint (legacy / immediate-post fallback).
    local = mp3_path.parent / "blueprint.json"
    if local.exists():
        with open(local) as f:
            return normalize_blueprint(json.load(f))

    for qd in [mp3_path.parent.parent.parent/"queue", mp3_path.parent.parent/"queue"]:
        if qd.exists():
            bps = sorted(qd.glob("*.json"), key=lambda p:p.stat().st_mtime, reverse=True)
            for bp in bps:
                if not (bp.parent/f"processed_{bp.name}").exists():
                    with open(bp) as f: return normalize_blueprint(json.load(f))

    genre = mp3_path.parent.name.title()
    if genre.lower() in ["music",""]: genre = "Music"

    # Keep full unicode track name for YouTube title
    track_full = mp3_path.stem.replace("-"," ").replace("_"," ").strip() or "Goosebumps Track"

    print(f"No blueprint - genre: {genre} | track: {track_full}")
    return {
        "genre": genre,
        "title": f"{track_full} - Goosebumps Music",
        "frisson_score": 82,
        "scientific_note": "Engineered using the neuroscience of frisson to trigger goosebumps.",
        "description": f"{track_full} is crafted to give you chills using the science of musical frisson.\n\nSubscribe to the Goosebumps Channel for more.",
        "tags": ["goosebumps","frisson",genre.lower(),"royalty free music","chills"],
    }

def get_duration(mp3):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1",str(mp3)],
        capture_output=True, text=True)
    return float(r.stdout.strip())

def safe_ffmpeg(text, n=55):
    """Make text safe for an FFmpeg drawtext arg. Keeps unicode (Korean, Japanese,
    Hindi, ...) and only removes characters that would break the filtergraph."""
    t = str(text).strip()
    for c in ["'",'"',':',',','[',']','\\','%','`']: t = t.replace(c,' ')
    t = ' '.join(t.split())
    return (t[:n]+"...") if len(t)>n else t or "Goosebumps Music"

import glob as _glob
def _find_font(*names):
    for name in names:
        hits = sorted(_glob.glob(f"/usr/share/fonts/**/{name}", recursive=True))
        if hits:
            return hits[0]
    return None

# Fonts for non-Latin titles (installed in the workflow); fall back to DejaVu.
_DEJAVU_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_CJK  = _find_font("NotoSansCJK-Bold.ttc", "NotoSansCJK-Regular.ttc",
                       "NotoSansCJKkr-*.otf", "NotoSansCJK*.ttc")
FONT_DEVA = _find_font("NotoSansDevanagari-Bold.ttf",
                       "NotoSansDevanagari-Regular.ttf", "NotoSansDevanagari*.ttf")

def title_font(text):
    """Pick a font whose glyphs cover the title's script — so non-Latin titles
    (Korean, Japanese, Chinese, Hindi) render instead of showing empty boxes."""
    for ch in str(text):
        o = ord(ch)
        if (0xAC00 <= o <= 0xD7A3 or 0x1100 <= o <= 0x11FF or   # Korean Hangul
            0x3040 <= o <= 0x30FF or                             # Japanese kana
            0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF):     # CJK Han
            return FONT_CJK or _DEJAVU_BOLD
        if 0x0900 <= o <= 0x097F:                                # Devanagari (Hindi)
            return FONT_DEVA or _DEJAVU_BOLD
    return _DEJAVU_BOLD

# ── Animated text alpha (fade in/out) ───────────────────────────────────────
# Commas are escaped (\,) because the whole filtergraph is one ffmpeg arg.
def _fade(start, end, fin=1.2, fout=1.5):
    """One-shot alpha: invisible, fade in over `fin`, hold, fade out over `fout`."""
    s, e = start, end
    return (f"'if(lt(t\\,{s})\\,0\\,"
            f"if(lt(t\\,{s+fin})\\,(t-{s})/{fin}\\,"
            f"if(lt(t\\,{e-fout})\\,1\\,"
            f"if(lt(t\\,{e})\\,({e}-t)/{fout}\\,0))))'")

def _fade_cycle(cycle, on, off, fin=1.0, fout=1.2):
    """Repeating alpha: every `cycle`s, fade in at `on`, hold, fade out by `off`,
    then stay invisible until the next cycle (clean full-screen visuals)."""
    m = f"mod(t\\,{cycle})"
    s, e = on, off
    return (f"'if(lt({m}\\,{s})\\,0\\,"
            f"if(lt({m}\\,{s+fin})\\,({m}-{s})/{fin}\\,"
            f"if(lt({m}\\,{e-fout})\\,1\\,"
            f"if(lt({m}\\,{e})\\,({e}-{m})/{fout}\\,0))))'")

def _fade_rotate(cycle, n, idx, on, off, fin=1.0, fout=1.3):
    """Rotation alpha: across a period of n*cycle secs, message `idx` is the
    only one visible during its own cycle's [on,off] window (fades in/out)."""
    P = cycle * n
    m = f"mod(t\\,{P})"
    s = idx * cycle + on
    e = idx * cycle + off
    return (f"'if(lt({m}\\,{s})\\,0\\,"
            f"if(lt({m}\\,{s+fin})\\,({m}-{s})/{fin}\\,"
            f"if(lt({m}\\,{e-fout})\\,1\\,"
            f"if(lt({m}\\,{e})\\,({e}-{m})/{fout}\\,0))))'")

# Rotating, benefit-driven prompts (no ' : , so FFmpeg renders cleanly).
# Ordered by priority — earlier lines are guaranteed to show even on short
# songs; later ones only appear on longer tracks. {genre} auto-fills.
ROTATING_MESSAGES = [
    "Scientifically engineered to give you goosebumps",
    "The biggest chills hit near the peak - stay for it",
    "Subscribe for your daily dose of goosebumps",
    "No goosebumps yet? Turn up the volume",
    "Did you get goosebumps? Comment where you felt it",
    "Get real dopamine you can feel - not empty scrolling",
    "Comment for more {genre} and I will deliver",
]

def _best_mp4_link(video):
    """Pick the mp4 file whose width is closest to 1920 (>=1280)."""
    files = sorted(video.get("video_files", []),
                   key=lambda f: abs((f.get("width") or 0) - 1920))
    for f in files:
        if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 1280:
            return f.get("link")
    return None

def _load_analysis():
    """Load precise analysis (downbeats + sections) from the isolated analyzer."""
    for p in ["phrases.json", str(Path(__file__).parent.parent / "phrases.json")]:
        try:
            with open(p) as f:
                data = json.load(f)
            if data.get("downbeats") or data.get("segments"):
                return data
        except Exception:
            pass
    return {}

def _section_cuts(segments, downs, dur, target=20.0):
    """Cut on REAL section changes (snapped to the nearest downbeat). Within each
    section, re-anchor a musical phrase grid AT THE SECTION START and cut every
    8 bars (or 4 if 8 is too long), so cuts land on true phrase boundaries
    instead of a fixed grid drifting through the song."""
    import statistics
    downs = sorted(float(d) for d in downs if 0 <= d < dur)
    if len(downs) < 2:
        return None
    snap  = lambda t: min(downs, key=lambda d: abs(d - t))
    diffs = [downs[i+1] - downs[i] for i in range(len(downs) - 1)]
    bar   = statistics.median(diffs)
    # Prefer full 8-bar phrases when that's a sane scene length, else 4-bar.
    n_bars = 8 if 10.0 <= 8 * bar <= 34.0 else 4

    # Real section boundaries (where the music changes), snapped to a downbeat.
    bounds = sorted({0.0, float(dur)} | {
        round(snap(float(s.get("start", 0))), 3)
        for s in segments if 0 < float(s.get("start", 0)) < dur - 2.0})

    final = []
    for i in range(len(bounds) - 1):
        a, b = bounds[i], bounds[i + 1]
        final.append(round(a, 3))
        inside = [d for d in downs if a + 0.3 < d < b - 0.3]  # downbeats after the section start
        m = 1
        while m * n_bars - 1 < len(inside):
            t = inside[m * n_bars - 1]                        # start of the m-th phrase in the section
            if b - t > 3.0:
                final.append(round(t, 3))
            m += 1
    final.append(float(dur))

    # drop any scene shorter than 3s
    merged = [final[0]]
    for t in sorted(set(final))[1:]:
        if t - merged[-1] >= 3.0:
            merged.append(t)
    merged[-1] = float(dur)
    if len(merged) >= 3:
        print(f"allin1 sections+phrases: {len(merged)-1} scenes, {n_bars}-bar phrases "
              f"(~{bar:.2f}s/bar), {len(segments)} sections @ "
              + ", ".join(f"{c:.1f}" for c in merged))
        return merged
    return None

def _phrase_cuts(downs, dur, target, source):
    """Group bar downbeats into 4/8-bar phrases and return cut times on the
    phrase boundaries (always a bar's beat 1)."""
    import statistics
    downs = sorted(d for d in downs if 0 <= d < dur)
    if not downs:
        return None
    if downs[0] > 0.4:
        downs = [0.0] + downs
    diffs = [downs[i+1] - downs[i] for i in range(len(downs) - 1)]
    if not diffs:
        return None
    bar = statistics.median(diffs)                       # seconds per bar
    n   = min([2, 4, 8], key=lambda k: abs(k * bar - target))  # bars per phrase
    cuts = [downs[i] for i in range(0, len(downs), n)]
    cuts = [c for c in cuts if c < dur - 2.0]
    if not cuts or cuts[0] > 0.1:
        cuts = [0.0] + cuts
    cuts.append(float(dur))
    cuts = sorted(set(cuts))
    if len(cuts) >= 3:
        print(f"{source}: {len(cuts)-1} phrase scenes, {n} bars/phrase "
              f"(~{bar:.2f}s/bar) @ " + ", ".join(f"{c:.1f}" for c in cuts))
        return cuts
    return None

def get_cut_points(mp3_path, dur, target=12.0):
    """Scene-cut times. Best: real section changes snapped to downbeats
    (all-in-one). Else: 4/8-bar phrase grid from precise downbeats. Else: a
    librosa downbeat estimate. Else: evenly spaced. Cuts always land on beat 1."""
    analysis = _load_analysis()
    downs = analysis.get("downbeats") or []
    segs  = analysis.get("segments") or []

    # 1. Best: cut where the music actually changes section, on a downbeat.
    if segs and downs:
        cuts = _section_cuts(segs, downs, dur)
        if cuts:
            return cuts

    # 2. Good: phrase grid from precise downbeats.
    if downs:
        cuts = _phrase_cuts([float(d) for d in downs], dur, target, "downbeat phrases")
        if cuts:
            return cuts

    # 3. Librosa downbeat estimate (less accurate; only if the analyzer absent).
    try:
        import librosa, numpy as np
        y, sr = librosa.load(str(mp3_path), sr=22050, mono=True)
        _t, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False, units="time")
        if len(beats) < 8:
            raise ValueError("too few beats")
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        bf    = np.clip(librosa.time_to_frames(beats, sr=sr), 0, len(onset_env) - 1)
        bstr  = onset_env[bf]
        phase = max(range(4), key=lambda p: float(bstr[p::4].sum()))
        downbeats = [float(t) for t in beats[phase::4]]
        cuts = _phrase_cuts(downbeats, dur, target, "librosa phrases")
        if cuts:
            return cuts
        raise ValueError("not enough cuts")
    except Exception as e:
        # 3. Even spacing.
        n = int(max(4, min(28, round(dur / target))))
        print(f"Cut analysis fell back to {n} even cuts ({e})")
        return [dur * i / n for i in range(n)] + [float(dur)]

def _pexels_candidates(query, api_key, page):
    """Return [(mp4_link, duration), ...] landscape candidates from Pexels."""
    api = (f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}"
           f"&per_page=80&orientation=landscape&page={page}")
    req = urllib.request.Request(api, headers={
        "Authorization": api_key.strip(), "User-Agent": BROWSER_UA,
        "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        videos = json.loads(resp.read().decode()).get("videos", [])
    out = []
    for v in videos:
        dur_v = v.get("duration") or 0
        link  = _best_mp4_link(v)
        if link and dur_v > 0:
            out.append((link, float(dur_v), "Pexels"))
    return out

def _pixabay_candidates(query, api_key, page):
    """Return [(mp4_link, duration), ...] landscape candidates from Pixabay."""
    api = (f"https://pixabay.com/api/videos/?key={api_key.strip()}"
           f"&q={urllib.parse.quote(query)}&per_page=60&page={page}")
    req = urllib.request.Request(api, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        hits = json.loads(resp.read().decode()).get("hits", [])
    out = []
    for h in hits:
        dur = h.get("duration") or 0
        v   = h.get("videos", {})
        f   = v.get("large") or v.get("medium") or v.get("small")
        if f and f.get("url") and dur > 0:
            w, ht = f.get("width") or 0, f.get("height") or 0
            if w >= ht and w >= 1280:          # landscape, decent resolution
                out.append((f["url"], float(dur), "Pixabay"))
    return out

def get_clips(query, pexels_key, pixabay_key, out_dir, ts, n_clips, min_dur=0.0):
    """Gather candidates from BOTH Pexels and Pixabay into ONE pool, prefer clips
    long enough to fill a scene, take the longest n_clips, and download them.
    Random page per source varies footage song-to-song. Returns [(path, dur)]."""
    cands = []
    if pexels_key:
        try:
            pg = random.randint(1, 4)
            c  = _pexels_candidates(query, pexels_key, pg)
            if not c and pg != 1:
                c = _pexels_candidates(query, pexels_key, 1)
            print(f"Pexels: {len(c)} candidates (p{pg}) for '{query}'")
            cands += c
        except Exception as e:
            print(f"Pexels fetch failed ({e})")
    if pixabay_key:
        try:
            pg = random.randint(1, 3)
            c  = _pixabay_candidates(query, pixabay_key, pg)
            if not c and pg != 1:
                c = _pixabay_candidates(query, pixabay_key, 1)
            print(f"Pixabay: {len(c)} candidates (p{pg}) for '{query}'")
            cands += c
        except Exception as e:
            print(f"Pixabay fetch failed ({e})")
    if not cands:
        return []

    # Prefer clips long enough to fill a scene; then take the longest available.
    long_enough = [c for c in cands if c[1] >= min_dur]
    pool = long_enough if len(long_enough) >= n_clips else cands
    random.shuffle(pool)                              # variety among eligible
    pool.sort(key=lambda c: c[1], reverse=True)       # longest first
    picked = pool[:n_clips]

    clips = []
    src_count = {"Pexels": 0, "Pixabay": 0}
    for i, (link, dur_v, source) in enumerate(picked):
        p = out_dir / f"bg_{ts}_{i}.mp4"
        try:
            dreq = urllib.request.Request(link, headers={"User-Agent": BROWSER_UA})
            with urllib.request.urlopen(dreq, timeout=120) as r, open(p, "wb") as fh:
                fh.write(r.read())
            clips.append((p, dur_v))
            src_count[source] = src_count.get(source, 0) + 1
        except Exception as e:
            print(f"  clip {i} download failed ({e}) — skipping")
    print(f"Downloaded {len(clips)} clip(s) from a pool of {len(cands)} "
          f"-> {src_count.get('Pexels',0)} Pexels + {src_count.get('Pixabay',0)} Pixabay")
    return clips

def create_video(mp3_path, output_dir):
    mp3_path = Path(mp3_path)
    bp = find_blueprint(mp3_path)

    # Always use the folder name — it's always correct and never stale
    genre = mp3_path.parent.name.title()
    genre_folder = mp3_path.parent.name.lower()

    # Use MP3 filename as title fallback (blueprint from website has no title field)
    stem = mp3_path.stem.replace("-", " ").replace("_", " ").strip() or "Goosebumps Track"
    full_title = bp.get("title") or f"{stem} - Goosebumps Music"

    # ASCII-safe overlay text (FFmpeg drawtext can't render unicode)
    ffmpeg_title = safe_ffmpeg(full_title, 48)
    score        = bp.get("frisson_score","")
    score_txt    = safe_ffmpeg(f"FRISSON SCORE  {score}%") if score else "FRISSON SCORE"
    brand        = safe_ffmpeg(f"GOOSEBUMPS MUSIC    |    {genre.upper()}", 50)

    dur = get_duration(mp3_path)
    T = get_theme(genre)
    bg, ac = T["bg"], T["ac"]

    output_dir.mkdir(exist_ok=True, parents=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = genre.lower().replace(" ","_")[:12]
    out  = output_dir / f"{ts}_{slug}.mp4"

    fb = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    fr = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    # Analyze the audio for downbeat-aligned scene cut points.
    cuts     = get_cut_points(mp3_path, dur)
    seg_durs = [cuts[i+1] - cuts[i] for i in range(len(cuts) - 1)]
    n_segs   = len(seg_durs)
    longest_scene = max(seg_durs) if seg_durs else dur

    # One genre-matched clip per section, pulled from a combined Pexels+Pixabay
    # pool (either key optional — works with whichever is set).
    pexels_key  = os.environ.get("PEXELS_API_KEY", "")
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
    bg_clips = []
    if pexels_key or pixabay_key:
        query = PEXELS_QUERIES.get(genre_folder, PEXELS_QUERIES["default"])
        try:
            bg_clips = get_clips(query, pexels_key, pixabay_key, output_dir, ts,
                                 n_segs, min_dur=longest_scene + 1.0)
        except Exception as e:
            print(f"Footage fetch failed ({e}) — using gradient fallback")
            bg_clips = []
    else:
        print("No PEXELS_API_KEY / PIXABAY_API_KEY — using gradient fallback")

    # Animated text overlay — clean outline + soft shadow (no blocky boxes),
    # fading in/out so it grabs attention, with stretches of NO text so the
    # full visuals breathe. Each CYCLE: score+brand appear early; a ROTATING
    # benefit-driven subscribe prompt appears mid (cycles through the messages);
    # then a clean window. Title shows once at the start.
    CYCLE = 30
    style    = "borderw=4:bordercolor=black@0.85:shadowcolor=black@0.5:shadowx=2:shadowy=2"
    cta_style = f"borderw=5:bordercolor=0x{ac}@0.95:shadowcolor=black@0.5:shadowx=2:shadowy=2"
    a_title = _fade(0.5, 12.0, fin=1.4, fout=1.6)   # intro identity, once
    a_score = _fade_cycle(CYCLE, 0.5, 8.0)          # top-left, early in cycle
    a_brand = _fade_cycle(CYCLE, 0.5, 8.0)          # bottom, pairs with score
    n_msgs  = len(ROTATING_MESSAGES)

    def overlay_chain(src):
        parts = [
            f"[{src}]drawtext=fontfile={fb}:text='{score_txt}':fontcolor=white:fontsize=50"
            f":x=50:y=48:{style}:alpha={a_score}[s]",
            f"[s]drawtext=fontfile={title_font(ffmpeg_title)}:text='{ffmpeg_title}':fontcolor=white:fontsize=56"
            f":x=(w-text_w)/2:y=150:{style}:alpha={a_title}[t1]",
        ]
        prev = "t1"
        # Rotating subscribe prompts (lower-center, accent outline to grab the eye)
        for i, msg in enumerate(ROTATING_MESSAGES):
            lbl = f"r{i}"
            a   = _fade_rotate(CYCLE, n_msgs, i, 14.0, 23.0)
            txt = safe_ffmpeg(msg.replace("{genre}", genre), 60)
            parts.append(
                f"[{prev}]drawtext=fontfile={fb}:text='{txt}':fontcolor=white:fontsize=44"
                f":x=(w-text_w)/2:y=h-180:{cta_style}:alpha={a}[{lbl}]")
            prev = lbl
        parts.append(
            f"[{prev}]drawtext=fontfile={fr}:text='{brand}':fontcolor=white:fontsize=34"
            f":x=(w-text_w)/2:y=h-90:{style}:alpha={a_brand}[vout]")
        return ";".join(parts)

    if bg_clips:
        # One unique clip per scene. Assign the longest clips to the longest
        # scenes. NEVER loop/repeat: if a clip is long enough, trim it to the
        # scene length; if it's a touch short, slow it slightly (setpts) to fill
        # the scene exactly. Either way every scene is one distinct clip and
        # every cut lands on a downbeat.
        order_long = sorted(range(n_segs), key=lambda i: seg_durs[i], reverse=True)
        clips_long = sorted(bg_clips, key=lambda c: c[1], reverse=True)
        assign = [None] * n_segs
        for rank, seg_i in enumerate(order_long):
            assign[seg_i] = clips_long[rank % len(clips_long)][0]

        # Actual on-disk durations (Pexels' reported duration is rounded).
        clip_dur = {}
        for p in set(assign):
            try: clip_dur[p] = get_duration(p)
            except Exception: clip_dur[p] = 0.0

        cmd = ["ffmpeg", "-y"]
        for i in range(n_segs):
            cmd += ["-i", str(assign[i])]
        cmd += ["-i", str(mp3_path)]

        pre, labels = "", ""
        for i in range(n_segs):
            sd   = seg_durs[i]
            cdur = clip_dur.get(assign[i], 0.0)
            base = (f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                    f"crop={WIDTH}:{HEIGHT},setsar=1")
            if cdur >= sd + 0.05:
                # long enough: play at normal speed, trim to the scene length
                pre += f"{base},fps={FPS},trim=duration={sd:.3f},setpts=PTS-STARTPTS[v{i}];"
            else:
                # slightly short: stretch the whole clip to fill the scene (no loop)
                factor = sd / max(cdur, 0.1)
                pre += f"{base},setpts={factor:.5f}*(PTS-STARTPTS),fps={FPS}[v{i}];"
            labels += f"[v{i}]"
        pre += f"{labels}concat=n={n_segs}:v=1:a=0[cat];[cat]eq=brightness=-0.06[bgv];"
        fc = pre + overlay_chain("bgv")

        cmd += ["-filter_complex", fc,
                "-map","[vout]","-map",f"{n_segs}:a",
                "-c:v","libx264","-preset","veryfast","-crf","23",
                "-c:a","aac","-b:a","192k",
                "-t",str(dur),"-pix_fmt","yuv420p",
                "-movflags","+faststart", str(out)]
    else:
        fc = (
            f"color=c=0x{bg}:s={WIDTH}x{HEIGHT}:r={FPS}[bgv];"
            + overlay_chain("bgv")
        )
        cmd = [
            "ffmpeg","-y","-i",str(mp3_path),
            "-filter_complex", fc,
            "-map","[vout]","-map","0:a",
            "-c:v","libx264","-preset","veryfast","-crf","23",
            "-c:a","aac","-b:a","192k",
            "-t",str(dur),"-pix_fmt","yuv420p",
            "-movflags","+faststart", str(out)
        ]

    print(f"Creating: {out.name} | {genre} | {dur:.1f}s | "
          f"{f'{n_segs} sections x Pexels' if bg_clips else 'gradient'}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFmpeg error:"); print(r.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    for p, _d in bg_clips:
        try: Path(p).unlink()
        except: pass

    # Save full unicode title in state for YouTube upload
    bp["title"] = full_title
    print(f"Done: {out}")
    return out, bp

def get_already_uploaded(output_dir):
    done = set()
    for sf in output_dir.glob("*_state.json"):
        try:
            with open(sf) as f:
                data = json.load(f)
                mp3 = data.get("mp3_path","")
                if mp3: done.add(mp3)
        except: pass
    return done

def main():
    mp3_path = Path(sys.argv[1]) if len(sys.argv)>1 else Path("")

    if not mp3_path.name or not mp3_path.suffix:
        music_dir  = Path(__file__).parent.parent / "music"
        output_dir = Path(__file__).parent.parent / "output"
        all_mp3s = sorted(music_dir.rglob("*.mp3"), key=lambda p:p.stat().st_mtime, reverse=True)
        already_done = get_already_uploaded(output_dir)
        mp3s = [p for p in all_mp3s if str(p) not in already_done]
        if not mp3s:
            print("No new MP3s found - all already uploaded")
            raise SystemExit(0)
        mp3_path = mp3s[0]
        print(f"Auto-detected: {mp3_path}")

    if not mp3_path.exists():
        alt = Path(__file__).parent.parent / mp3_path
        if alt.exists(): mp3_path = alt
        else: print(f"Not found: {mp3_path}"); raise SystemExit(1)

    output_dir = Path(__file__).parent.parent / "output"
    video_path, bp = create_video(mp3_path, output_dir)

    state = output_dir / f"{video_path.stem}_state.json"
    with open(state,"w", encoding="utf-8") as f:
        json.dump({"video_path":str(video_path),"mp3_path":str(mp3_path),"blueprint":bp},f,indent=2,ensure_ascii=False)
    print(f"State: {state}\nReady for upload.")

if __name__=="__main__":
    main()
