"""
create_video.py - Fast static gradient visuals. Renders in under 2 minutes.
Each genre gets a unique color gradient background.
"""
import subprocess, json, sys
from pathlib import Path
from datetime import datetime

WIDTH, HEIGHT, FPS = 1920, 1080, 24

THEMES = {
    "blues":     {"bg":"020818","mid":"0a2a5e","w1":"4488ff","w2":"224488","tx":"cce0ff","ac":"4488ff"},
    "jazz":      {"bg":"120800","mid":"3d1a00","w1":"ff9933","w2":"cc7722","tx":"ffe0b0","ac":"ff9933"},
    "kpop":      {"bg":"0d0015","mid":"2a0040","w1":"ff44ff","w2":"aa00ff","tx":"ffccff","ac":"ff44ff"},
    "classical": {"bg":"080808","mid":"1a1a18","w1":"e8d5a0","w2":"c4a96e","tx":"fff8e7","ac":"e8d5a0"},
    "hiphop":    {"bg":"050505","mid":"1a0808","w1":"ff4444","w2":"ff8800","tx":"ffffff","ac":"ff4444"},
    "ambient":   {"bg":"001510","mid":"003328","w1":"44ffcc","w2":"00ccaa","tx":"ccffee","ac":"44ffcc"},
    "rock":      {"bg":"100000","mid":"2a0000","w1":"ff2200","w2":"ff6600","tx":"ffffff","ac":"ff2200"},
    "gospel":    {"bg":"100f00","mid":"2a2000","w1":"ffee44","w2":"ffcc00","tx":"fffff0","ac":"ffcc00"},
    "cinematic": {"bg":"000510","mid":"000f2a","w1":"4488ff","w2":"0044cc","tx":"cce0ff","ac":"4488ff"},
    "lofi":      {"bg":"080810","mid":"121225","w1":"99aacc","w2":"667799","tx":"dde0ee","ac":"99aacc"},
    "afrobeat":  {"bg":"0a0500","mid":"251000","w1":"ff8833","w2":"ff4400","tx":"ffe0cc","ac":"ff8833"},
    "latin":     {"bg":"100500","mid":"2a0f00","w1":"ff6633","w2":"ffcc00","tx":"ffe8cc","ac":"ffcc00"},
    "edm":       {"bg":"000a15","mid":"001530","w1":"00ffff","w2":"ff00ff","tx":"ccffff","ac":"00ffff"},
    "rnb":       {"bg":"100008","mid":"280015","w1":"ff44aa","w2":"cc0066","tx":"ffccee","ac":"ff44aa"},
    "folk":      {"bg":"0a0800","mid":"1a1400","w1":"ccaa44","w2":"997733","tx":"fff0cc","ac":"ccaa44"},
    "celtic":    {"bg":"001008","mid":"002a15","w1":"44cc88","w2":"009944","tx":"ccffdd","ac":"44cc88"},
    "indian":    {"bg":"100500","mid":"2a1000","w1":"ff6600","w2":"ffcc00","tx":"ffe8cc","ac":"ff6600"},
    "electronic":{"bg":"000a15","mid":"001530","w1":"00ffff","w2":"0088ff","tx":"ccffff","ac":"00ffff"},
    "country":   {"bg":"0d0800","mid":"1f1400","w1":"ddaa44","w2":"aa7722","tx":"fff0cc","ac":"ddaa44"},
    "metal":     {"bg":"0a0000","mid":"200000","w1":"ff2200","w2":"880000","tx":"ffffff","ac":"ff2200"},
    "reggae":    {"bg":"001200","mid":"002800","w1":"44ff44","w2":"ffee00","tx":"ccffcc","ac":"44ff44"},
    "world":     {"bg":"0a0510","mid":"150a20","w1":"dd88ff","w2":"8833cc","tx":"eeccff","ac":"dd88ff"},
    "default":   {"bg":"0a0a1a","mid":"15152a","w1":"7f77dd","w2":"5dcaa5","tx":"eeedfe","ac":"7f77dd"},
}

def get_theme(genre):
    key = genre.lower().replace(" ","").replace("-","").replace("_","")
    for k in THEMES:
        if key==k or (len(key)>=4 and len(k)>=4 and key[:4]==k[:4]):
            return THEMES[k]
    return THEMES["default"]

def find_blueprint(mp3_path):
    for qd in [mp3_path.parent.parent.parent/"queue", mp3_path.parent.parent/"queue"]:
        if qd.exists():
            bps = sorted(qd.glob("*.json"), key=lambda p:p.stat().st_mtime, reverse=True)
            for bp in bps:
                if not (bp.parent/f"processed_{bp.name}").exists():
                    with open(bp) as f: return json.load(f)
    genre = mp3_path.parent.name.title()
    if genre.lower() in ["music",""]: genre="Music"
    track = mp3_path.stem.encode("ascii","ignore").decode().replace("-"," ").replace("_"," ").strip() or "Goosebumps Track"
    print(f"No blueprint - genre: {genre}")
    return {
        "genre": genre,
        "title": f"{track} - Goosebumps Music",
        "frisson_score": 82,
        "scientific_note": "Engineered using the neuroscience of frisson to trigger goosebumps.",
        "description": f"{track} is crafted to give you chills using the science of musical frisson.\n\nSubscribe to the Goosebumps Channel for more.",
        "tags": ["goosebumps","frisson",genre.lower(),"royalty free music","chills"],
    }

def get_duration(mp3):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                        "-of","default=noprint_wrappers=1:nokey=1",str(mp3)],
                       capture_output=True,text=True)
    return float(r.stdout.strip())

def safe(text, n=55):
    t = str(text).encode("ascii","ignore").decode().strip()
    for c in ["'",'"',':',',','[',']','\\','%','`']: t=t.replace(c,' ')
    return (t[:n]+"...") if len(t)>n else t or "Goosebumps Music"

def create_video(mp3_path, output_dir):
    mp3_path = Path(mp3_path)
    bp = find_blueprint(mp3_path)
    genre  = bp.get("genre","Music")
    title  = safe(bp.get("title","Goosebumps Music"))
    note   = safe(bp.get("scientific_note","Engineered using the neuroscience of frisson to trigger goosebumps."), 90)
    score  = bp.get("frisson_score","")
    score_txt = safe(f"Frisson Score  {score}%") if score else ""

    dur = get_duration(mp3_path)
    T = get_theme(genre)
    bg,mid = T["bg"],T["mid"]
    w1,w2,tx,ac = T["w1"],T["w2"],T["tx"],T["ac"]

    output_dir.mkdir(exist_ok=True, parents=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = genre.lower().replace(" ","_")[:12]
    out  = output_dir / f"{ts}_{slug}.mp4"

    fb = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    fr = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    fi = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
    gu = safe(genre.upper(), 20)

    # KEY CHANGE: use a static gradient image generated once
    # then loop it as video - MUCH faster than animated filters
    filter_complex = (
        # Static gradient background - generated ONCE, looped
        f"color=c=0x{bg}:s={WIDTH}x{HEIGHT}:r={FPS}[bg];"

        # Waveform from audio
        f"[0:a]showwaves=s={WIDTH}x{HEIGHT//4}:mode=cline:rate={FPS}"
        f":colors=#{w1}@0.95|#{w2}@0.75[wave];"

        # Horizontal accent line at top of waveform area
        f"[bg]drawbox=x=0:y={int(HEIGHT*0.60)}:w={WIDTH}:h=2:color=0x{w1}@0.4:t=fill[bgline];"

        # Overlay waveform
        f"[bgline][wave]overlay=0:{int(HEIGHT*0.61)}:format=auto[v1];"

        # Large genre color block at top for visual identity
        f"[v1]drawbox=x=0:y=0:w={WIDTH}:h=8:color=0x{ac}@0.9:t=fill[v1b];"

        # Bottom accent line
        f"[v1b]drawbox=x=0:y={HEIGHT-8}:w={WIDTH}:h=8:color=0x{ac}@0.6:t=fill[v1c];"

        # Title
        f"[v1c]drawtext=fontfile={fb}:text='{title}'"
        f":fontcolor=#{tx}:fontsize=58:x=(w-text_w)/2:y=h*0.10"
        f":alpha='if(lt(t\\,1.5)\\,t/1.5\\,1)':shadowcolor=black@0.9:shadowx=3:shadowy=3[v2];"

        # Genre badge
        f"[v2]drawtext=fontfile={fr}:text='{gu}'"
        f":fontcolor=#{ac}:fontsize=26:x=(w-text_w)/2:y=h*0.22"
        f":alpha='if(lt(t\\,2)\\,t/2\\,1)':shadowcolor=black@0.9:shadowx=2:shadowy=2[v3];"

        # Scientific note
        f"[v3]drawtext=fontfile={fi}:text='{note}'"
        f":fontcolor=#{tx}@0.85:fontsize=22:x=(w-text_w)/2:y=h*0.89"
        f":alpha='if(lt(t\\,3)\\,t/3\\,1)':shadowcolor=black@0.9:shadowx=2:shadowy=2[v4];"

        # Watermark
        f"[v4]drawtext=fontfile={fb}:text='GOOSEBUMPS'"
        f":fontcolor=#{ac}@0.7:fontsize=16:x=w-text_w-30:y=20"
        f":shadowcolor=black@0.8:shadowx=1:shadowy=1[vout]"
    )

    if score_txt:
        filter_complex = filter_complex.replace("[vout]",
            f"[vpre];[vpre]drawtext=fontfile={fr}:text='{score_txt}'"
            f":fontcolor=#{w1}@0.85:fontsize=18:x=28:y=20"
            f":shadowcolor=black@0.8:shadowx=1:shadowy=1[vout]")

    cmd = [
        "ffmpeg","-y","-i",str(mp3_path),
        "-filter_complex", filter_complex,
        "-map","[vout]","-map","0:a",
        "-c:v","libx264","-preset","ultrafast","-crf","23",
        "-c:a","aac","-b:a","192k",
        "-t",str(dur),"-pix_fmt","yuv420p",
        "-movflags","+faststart", str(out)
    ]

    print(f"Creating: {out.name} | {genre} | {dur:.1f}s")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFmpeg error:")
        print(r.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    print(f"Done: {out}")
    return out, bp

def main():
    mp3_path = Path(sys.argv[1]) if len(sys.argv)>1 else Path("")
    if not mp3_path.name or not mp3_path.suffix:
        music_dir = Path(__file__).parent.parent/"music"
        mp3s = sorted(music_dir.rglob("*.mp3"), key=lambda p:p.stat().st_mtime, reverse=True)
        if not mp3s: print("No MP3s found"); raise SystemExit(1)
        mp3_path = mp3s[0]
        print(f"Auto-detected: {mp3_path}")
    if not mp3_path.exists():
        alt = Path(__file__).parent.parent/mp3_path
        if alt.exists(): mp3_path=alt
        else: print(f"Not found: {mp3_path}"); raise SystemExit(1)

    output_dir = Path(__file__).parent.parent/"output"
    video_path, bp = create_video(mp3_path, output_dir)
    state = output_dir/f"{video_path.stem}_state.json"
    with open(state,"w") as f:
        json.dump({"video_path":str(video_path),"mp3_path":str(mp3_path),"blueprint":bp},f,indent=2)
    print(f"State: {state}\nReady for upload.")

if __name__=="__main__":
    main()