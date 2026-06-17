"""
create_video.py - Genre-matched moving (Pexels) backgrounds with branded overlay.
Falls back to a solid themed gradient if Pexels is unavailable, so a video is
ALWAYS produced. Supports unicode filenames (Korean, Portuguese, Japanese, etc.)
"""
import subprocess, json, sys, os, random, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

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
    """Strip to ASCII for FFmpeg drawtext — FFmpeg can't render unicode."""
    t = str(text).encode("ascii","ignore").decode().strip()
    for c in ["'",'"',':',',','[',']','\\','%','`']: t = t.replace(c,' ')
    t = ' '.join(t.split())
    return (t[:n]+"...") if len(t)>n else t or "Goosebumps Music"

def get_pexels_background(query, api_key, out_path):
    """Search Pexels for a landscape video and download a ~1080p mp4. Returns
    the path on success, or None on any failure (caller falls back to gradient)."""
    api = ("https://api.pexels.com/videos/search?query="
           + urllib.parse.quote(query) + "&per_page=15&orientation=landscape")
    req = urllib.request.Request(api, headers={"Authorization": api_key})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    videos = data.get("videos", [])
    if not videos:
        return None
    random.shuffle(videos)  # variety across runs of the same genre
    for v in videos:
        # pick the mp4 file whose width is closest to 1920 (>=1280)
        files = sorted(v.get("video_files", []),
                       key=lambda f: abs((f.get("width") or 0) - 1920))
        for f in files:
            if f.get("file_type") == "video/mp4" and (f.get("width") or 0) >= 1280:
                link = f.get("link")
                if link:
                    urllib.request.urlretrieve(link, out_path)
                    return out_path
    return None

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
    cta          = "SUBSCRIBE for your daily dose of goosebumps"

    dur = get_duration(mp3_path)
    T = get_theme(genre)
    bg, ac = T["bg"], T["ac"]

    output_dir.mkdir(exist_ok=True, parents=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = genre.lower().replace(" ","_")[:12]
    out  = output_dir / f"{ts}_{slug}.mp4"

    fb = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    fr = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

    # Try a genre-matched moving background from Pexels (key is optional)
    api_key  = os.environ.get("PEXELS_API_KEY", "")
    bg_video = None
    if api_key:
        query = PEXELS_QUERIES.get(genre_folder, PEXELS_QUERIES["default"])
        try:
            bg_video = get_pexels_background(query, api_key, output_dir / f"bg_{ts}.mp4")
            print(f"Pexels '{query}' -> {'downloaded' if bg_video else 'no results'}")
        except Exception as e:
            print(f"Pexels fetch failed ({e}) — using gradient fallback")
            bg_video = None
    else:
        print("No PEXELS_API_KEY — using gradient fallback")

    # Branded text overlay — white text in dark/accent boxes so it's readable
    # over ANY footage. Score (top-left), Title (top-center, fades in),
    # CTA (accent box), brand line (bottom).
    def overlay_chain(src):
        return (
            f"[{src}]drawtext=fontfile={fb}:text='{score_txt}':fontcolor=white:fontsize=50"
            f":x=50:y=45:box=1:boxcolor=black@0.6:boxborderw=20[s];"
            f"[s]drawtext=fontfile={fb}:text='{ffmpeg_title}':fontcolor=white:fontsize=52"
            f":x=(w-text_w)/2:y=160:box=1:boxcolor=black@0.5:boxborderw=16"
            f":alpha='if(lt(t\\,1.5)\\,t/1.5\\,1)'[t1];"
            f"[t1]drawtext=fontfile={fb}:text='{cta}':fontcolor=white:fontsize=42"
            f":x=(w-text_w)/2:y=h-175:box=1:boxcolor=0x{ac}@0.85:boxborderw=18[t2];"
            f"[t2]drawtext=fontfile={fr}:text='{brand}':fontcolor=white:fontsize=34"
            f":x=(w-text_w)/2:y=h-85:box=1:boxcolor=black@0.55:boxborderw=14[vout]"
        )

    if bg_video:
        fc = (
            f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS},eq=brightness=-0.06[bgv];"
            + overlay_chain("bgv")
        )
        cmd = [
            "ffmpeg","-y","-stream_loop","-1","-i",str(bg_video),"-i",str(mp3_path),
            "-filter_complex", fc,
            "-map","[vout]","-map","1:a",
            "-c:v","libx264","-preset","veryfast","-crf","23",
            "-c:a","aac","-b:a","192k",
            "-t",str(dur),"-pix_fmt","yuv420p",
            "-movflags","+faststart", str(out)
        ]
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

    print(f"Creating: {out.name} | {genre} | {dur:.1f}s | bg={'Pexels' if bg_video else 'gradient'}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFmpeg error:"); print(r.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    if bg_video:
        try: Path(bg_video).unlink()
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
