"""
create_video.py - Real Pixabay video backgrounds. Falls back to gradient if API fails.
"""
import subprocess, json, sys, os, random, struct, zlib, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

WIDTH, HEIGHT, FPS = 1920, 1080, 24

GENRE_SEARCHES = {
    "blues":      ["rain street night", "stormy ocean waves", "mississippi river fog"],
    "jazz":       ["city lights night rain", "smoky bar lights", "new orleans street night"],
    "kpop":       ["neon city night", "colorful lights bokeh", "seoul cityscape night"],
    "classical":  ["concert hall lights", "dramatic sky clouds", "golden light rays"],
    "hiphop":     ["city skyline night", "urban street lights", "subway train night"],
    "ambient":    ["aurora borealis", "deep ocean underwater", "misty forest morning"],
    "rock":       ["lightning storm", "concert crowd lights", "thunder clouds"],
    "gospel":     ["golden light rays", "sunrise mountains", "light through clouds"],
    "cinematic":  ["galaxy milky way stars", "dramatic storm clouds", "mountain epic sunset"],
    "lofi":       ["rain window city", "cozy cafe", "autumn leaves falling"],
    "afrobeat":   ["sunset africa savanna", "colorful festival", "tropical sunset"],
    "latin":      ["tropical beach sunset", "carnival lights", "ocean sunset warm"],
    "edm":        ["laser light show", "festival crowd night", "colorful smoke"],
    "rnb":        ["city night lights bokeh", "romantic sunset", "purple sunset city"],
    "folk":       ["green forest path", "meadow wildflowers", "countryside sunrise"],
    "celtic":     ["ireland cliffs ocean", "green hills misty", "northern lights"],
    "indian":     ["golden temple sunset", "colorful festival", "ganges river sunrise"],
    "electronic": ["neon lights abstract", "digital city lights", "laser abstract"],
    "country":    ["country road sunset", "wheat field wind", "barn golden hour"],
    "metal":      ["lightning storm dark", "volcano eruption", "ocean storm waves"],
    "reggae":     ["tropical beach waves", "caribbean sunset", "palm trees ocean"],
    "world":      ["earth from space", "mountain sunrise", "ancient temple sunrise"],
    "neosoul":    ["golden hour city", "sunset reflection water", "warm bokeh lights"],
    "indie":      ["road trip sunrise", "flower field wind", "vintage summer light"],
    "flamenco":   ["sunset spain", "dramatic red sky", "flamenco dance"],
    "default":    ["aurora borealis", "milky way stars", "ocean waves sunset"],
}

GRADIENTS = {
    "blues":     ((2,8,24),   (15,45,100), "4488ff","224488","cce0ff","4488ff"),
    "jazz":      ((18,8,0),   (80,30,0),   "ff9933","cc7722","ffe0b0","ff9933"),
    "kpop":      ((13,0,21),  (60,0,90),   "ff44ff","aa00ff","ffccff","ff44ff"),
    "classical": ((8,8,8),    (30,28,24),  "e8d5a0","c4a96e","fff8e7","e8d5a0"),
    "hiphop":    ((5,5,5),    (30,8,8),    "ff4444","ff8800","ffffff","ff4444"),
    "ambient":   ((0,21,16),  (0,60,45),   "44ffcc","00ccaa","ccffee","44ffcc"),
    "rock":      ((16,0,0),   (50,0,0),    "ff2200","ff6600","ffffff","ff2200"),
    "gospel":    ((16,15,0),  (50,40,0),   "ffee44","ffcc00","fffff0","ffcc00"),
    "cinematic": ((0,5,16),   (0,20,55),   "4488ff","0044cc","cce0ff","4488ff"),
    "lofi":      ((8,8,16),   (20,20,40),  "99aacc","667799","dde0ee","99aacc"),
    "afrobeat":  ((10,5,0),   (40,18,0),   "ff8833","ff4400","ffe0cc","ff8833"),
    "latin":     ((16,5,0),   (50,20,0),   "ff6633","ffcc00","ffe8cc","ffcc00"),
    "edm":       ((0,10,21),  (0,25,55),   "00ffff","ff00ff","ccffff","00ffff"),
    "rnb":       ((16,0,8),   (45,0,25),   "ff44aa","cc0066","ffccee","ff44aa"),
    "folk":      ((10,8,0),   (30,22,0),   "ccaa44","997733","fff0cc","ccaa44"),
    "celtic":    ((0,16,8),   (0,45,22),   "44cc88","009944","ccffdd","44cc88"),
    "default":   ((10,10,26), (22,22,45),  "7f77dd","5dcaa5","eeedfe","7f77dd"),
}

def get_searches(genre):
    key = genre.lower().replace(" ","").replace("-","").replace("_","")
    for k in GENRE_SEARCHES:
        if key==k or (len(key)>=4 and len(k)>=4 and key[:4]==k[:4]):
            return GENRE_SEARCHES[k]
    return GENRE_SEARCHES["default"]

def get_gradient(genre):
    key = genre.lower().replace(" ","").replace("-","").replace("_","")
    for k in GRADIENTS:
        if key==k or (len(key)>=4 and len(k)>=4 and key[:4]==k[:4]):
            return GRADIENTS[k]
    return GRADIENTS["default"]

def make_gradient_png(path, top_rgb, bot_rgb):
    def write_chunk(t, d):
        c = t+d
        return struct.pack('>I',len(d))+c+struct.pack('>I',zlib.crc32(c)&0xffffffff)
    def lerp(a,b,t): return int(a+(b-a)*t)
    rows=[]
    for y in range(HEIGHT):
        t=y/(HEIGHT-1)
        r,g,b=lerp(top_rgb[0],bot_rgb[0],t),lerp(top_rgb[1],bot_rgb[1],t),lerp(top_rgb[2],bot_rgb[2],t)
        rows.append(bytes([0]+[r,g,b]*WIDTH))
    compressed=zlib.compress(b''.join(rows),6)
    png=(b'\x89PNG\r\n\x1a\n'
         +write_chunk(b'IHDR',struct.pack('>IIBBBBB',WIDTH,HEIGHT,8,2,0,0,0))
         +write_chunk(b'IDAT',compressed)
         +write_chunk(b'IEND',b''))
    with open(path,'wb') as f: f.write(png)
    print(f"Gradient PNG created: {path}")

def download_pixabay_video(genre, out_path, api_key):
    searches = get_searches(genre)
    random.shuffle(searches)
    for query in searches:
        try:
            q = urllib.parse.quote(query)
            url = f"https://pixabay.com/api/videos/?key={api_key}&q={q}&per_page=20&min_width=1280&video_type=film&safesearch=true&order=popular"
            print(f"Searching Pixabay: '{query}'")
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            hits = data.get("hits",[])
            if not hits:
                print(f"No results for: {query}")
                continue
            random.shuffle(hits)
            for hit in hits:
                for size in ["large","medium"]:
                    v = hit.get("videos",{}).get(size,{})
                    video_url = v.get("url","")
                    if video_url and v.get("width",0)>=1280:
                        print(f"Downloading Pixabay video: {query} ({size})")
                        req2 = urllib.request.Request(video_url, headers={"User-Agent":"Mozilla/5.0"})
                        with urllib.request.urlopen(req2, timeout=60) as vr:
                            with open(out_path,'wb') as f: f.write(vr.read())
                        print(f"Video downloaded: {out_path}")
                        return True
        except Exception as e:
            print(f"Pixabay error for '{query}': {e}")
    return False

def find_blueprint(mp3_path):
    for qd in [mp3_path.parent.parent.parent/"queue", mp3_path.parent.parent/"queue"]:
        if qd.exists():
            bps = sorted(qd.glob("*.json"),key=lambda p:p.stat().st_mtime,reverse=True)
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
    note   = safe(bp.get("scientific_note","Engineered using the neuroscience of frisson to trigger goosebumps."),90)
    score  = bp.get("frisson_score","")
    score_txt = safe(f"Frisson Score  {score}%") if score else ""

    dur = get_duration(mp3_path)
    grad = get_gradient(genre)
    top_rgb, bot_rgb, w1, w2, tx, ac = grad

    output_dir.mkdir(exist_ok=True, parents=True)
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = genre.lower().replace(" ","_")[:12]
    out  = output_dir/f"{ts}_{slug}.mp4"

    api_key = os.environ.get("PIXABAY_API_KEY") or os.environ.get("PEXELS_API_KEY","")
    bg_video = output_dir/f"{ts}_bg.mp4"
    bg_png   = output_dir/f"{ts}_bg.png"

    use_video = False
    if api_key:
        use_video = download_pixabay_video(genre, str(bg_video), api_key)
    else:
        print("No API key found - using gradient fallback")

    make_gradient_png(str(bg_png), top_rgb, bot_rgb)

    bg_input = str(bg_video) if use_video else str(bg_png)
    print(f"Using {'Pixabay video' if use_video else 'gradient'} background")

    fb="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    fr="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    fi="/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
    gu=safe(genre.upper(),20)

    if use_video:
        bg_filter=(f"[1:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                   f"crop={WIDTH}:{HEIGHT},loop=loop=-1:size=250:start=0,"
                   f"trim=duration={dur},setpts=PTS-STARTPTS[bg];")
    else:
        bg_filter=(f"[1:v]loop=loop=-1:size=1:start=0,"
                   f"trim=duration={dur},setpts=PTS-STARTPTS[bg];")

    fc=(
        bg_filter+
        f"color=c=black@0.40:s={WIDTH}x{HEIGHT}:r={FPS}[ov];"
        f"[bg][ov]overlay=0:0:format=auto[bgd];"
        f"[0:a]showwaves=s={WIDTH}x{int(HEIGHT*0.25)}:mode=cline:rate={FPS}"
        f":colors=#{w1}@0.95|#{w2}@0.8[wave];"
        f"[bgd][wave]overlay=0:{int(HEIGHT*0.62)}:format=auto[v1];"
        f"[v1]drawbox=x=0:y=0:w={WIDTH}:h=5:color=0x{ac}@0.9:t=fill[v1b];"
        f"[v1b]drawbox=x=0:y={HEIGHT-5}:w={WIDTH}:h=5:color=0x{ac}@0.6:t=fill[v1c];"
        f"[v1c]drawtext=fontfile={fb}:text='{title}'"
        f":fontcolor=#{tx}:fontsize=58:x=(w-text_w)/2:y=h*0.10"
        f":alpha='if(lt(t\\,1.5)\\,t/1.5\\,1)':shadowcolor=black@0.95:shadowx=3:shadowy=3[v2];"
        f"[v2]drawtext=fontfile={fr}:text='{gu}'"
        f":fontcolor=#{ac}:fontsize=26:x=(w-text_w)/2:y=h*0.22"
        f":alpha='if(lt(t\\,2)\\,t/2\\,1)':shadowcolor=black@0.95:shadowx=2:shadowy=2[v3];"
        f"[v3]drawtext=fontfile={fi}:text='{note}'"
        f":fontcolor=#{tx}@0.9:fontsize=22:x=(w-text_w)/2:y=h*0.89"
        f":alpha='if(lt(t\\,3)\\,t/3\\,1)':shadowcolor=black@0.95:shadowx=2:shadowy=2[v4];"
        f"[v4]drawtext=fontfile={fb}:text='GOOSEBUMPS'"
        f":fontcolor=#{ac}@0.7:fontsize=16:x=w-text_w-30:y=20"
        f":shadowcolor=black@0.8:shadowx=1:shadowy=1[vout]"
    )

    if score_txt:
        fc=fc.replace("[vout]",
            f"[vpre];[vpre]drawtext=fontfile={fr}:text='{score_txt}'"
            f":fontcolor=#{w1}@0.85:fontsize=18:x=28:y=20"
            f":shadowcolor=black@0.8:shadowx=1:shadowy=1[vout]")

    cmd=["ffmpeg","-y",
         "-i",str(mp3_path),"-i",bg_input,
         "-filter_complex",fc,
         "-map","[vout]","-map","0:a",
         "-c:v","libx264","-preset","ultrafast","-crf","23",
         "-c:a","aac","-b:a","192k",
         "-t",str(dur),"-pix_fmt","yuv420p",
         "-movflags","+faststart",str(out)]

    print(f"Creating: {out.name} | {genre} | {dur:.1f}s")
    r=subprocess.run(cmd,capture_output=True,text=True)

    for f in [bg_video,bg_png]:
        try: f.unlink()
        except: pass

    if r.returncode!=0:
        print("FFmpeg error:"); print(r.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    print(f"Done: {out}")
    return out, bp

def main():
    mp3_path=Path(sys.argv[1]) if len(sys.argv)>1 else Path("")
    if not mp3_path.name or not mp3_path.suffix:
        music_dir=Path(__file__).parent.parent/"music"
        mp3s=sorted(music_dir.rglob("*.mp3"),key=lambda p:p.stat().st_mtime,reverse=True)
        if not mp3s: print("No MP3s found"); raise SystemExit(1)
        mp3_path=mp3s[0]
        print(f"Auto-detected: {mp3_path}")
    if not mp3_path.exists():
        alt=Path(__file__).parent.parent/mp3_path
        if alt.exists(): mp3_path=alt
        else: print(f"Not found: {mp3_path}"); raise SystemExit(1)
    output_dir=Path(__file__).parent.parent/"output"
    video_path,bp=create_video(mp3_path,output_dir)
    state=output_dir/f"{video_path.stem}_state.json"
    with open(state,"w") as f:
        json.dump({"video_path":str(video_path),"mp3_path":str(mp3_path),"blueprint":bp},f,indent=2)
    print(f"State: {state}\nReady for upload.")

if __name__=="__main__":
    main()