"""
create_video.py - Upgraded with Pexels backgrounds + 25 genre themes
"""
import subprocess, json, sys, os, urllib.request, urllib.parse, random
from pathlib import Path
from datetime import datetime

WIDTH, HEIGHT, FPS = 1920, 1080, 30

GENRE_THEMES = {
    "blues":("0a0a1a","4488ff","6699cc","cce0ff"),
    "jazz":("1a0a00","ff9933","cc7722","ffe0b0"),
    "kpop":("1a001a","ff44ff","aa00ff","ffccff"),
    "k-pop":("1a001a","ff44ff","aa00ff","ffccff"),
    "classical":("0d0d0d","e8d5a0","c4a96e","fff8e7"),
    "hiphop":("0a0a0a","ff4444","ff8800","ffffff"),
    "hip-hop":("0a0a0a","ff4444","ff8800","ffffff"),
    "ambient":("001a1a","44ffcc","00ccaa","ccffee"),
    "rock":("1a0000","ff2200","ff6600","ffffff"),
    "rnb":("1a000a","ff44aa","cc0066","ffccee"),
    "folk":("0d0a00","ccaa44","997733","fff0cc"),
    "gospel":("0a0a00","ffee44","ffcc00","fffff0"),
    "cinematic":("000a1a","4488ff","0044cc","cce0ff"),
    "lofi":("0a0a0a","99aacc","667799","dde0ee"),
    "afrobeat":("0a0500","ff8833","ff4400","ffe0cc"),
    "latin":("1a0500","ff6633","ffcc00","ffe8cc"),
    "celtic":("001a05","44cc88","009944","ccffdd"),
    "indian":("1a0a00","ff6600","ffcc00","ffe8cc"),
    "electronic":("000a1a","00ffff","0088ff","ccffff"),
    "edm":("000a1a","00ffff","ff00ff","ccffff"),
    "country":("0d0800","ddaa44","aa7722","fff0cc"),
    "metal":("0a0000","ff2200","880000","ffffff"),
    "reggae":("001a00","44ff44","ffee00","ccffcc"),
    "world":("0a0510","dd88ff","8833cc","eeccff"),
    "neosoul":("1a0510","ff88aa","cc4466","ffddee"),
    "indie":("0a0a15","aa88ff","7755cc","eeddff"),
    "flamenco":("1a0000","ff3300","ffaa00","ffe8cc"),
    "default":("0a0a1a","7f77dd","5dcaa5","eeedfe"),
}

GENRE_VISUALS = {
    "blues":["rain city night","smoky bar interior","rainy window night"],
    "jazz":["jazz club lights","city night lights","candlelight bokeh"],
    "kpop":["neon lights city","colorful lights bokeh","concert stage lights"],
    "classical":["concert hall","grand piano keys","moonlight forest"],
    "hiphop":["city night skyline","urban street lights","subway tunnel"],
    "ambient":["ocean waves slow","misty forest","aurora borealis"],
    "rock":["lightning storm","concert crowd","mountain storm"],
    "rnb":["city sunset","candle romance","rain window bokeh"],
    "folk":["autumn forest","campfire night","countryside sunset"],
    "gospel":["sunrise clouds","light through clouds","golden hour"],
    "cinematic":["galaxy space stars","milky way timelapse","northern lights"],
    "lofi":["rainy cafe window","cozy room night","city rain bokeh"],
    "afrobeat":["savanna sunset","african landscape","tropical nature"],
    "latin":["tropical beach sunset","ocean sunset","tropical flowers"],
    "celtic":["ireland green hills","misty mountains","forest waterfall"],
    "indian":["lotus flower water","himalaya mountains","colorful festival"],
    "electronic":["neon city aerial","abstract light trails","city lights aerial"],
    "edm":["concert laser lights","festival crowd","neon lights abstract"],
    "country":["farm sunset","rolling hills","wheat field golden"],
    "metal":["lightning dark sky","mountain fog","dark forest"],
    "reggae":["beach waves tropical","palm tree beach","caribbean ocean"],
    "world":["earth from space","mountain sunrise","cultural festival"],
    "neosoul":["city sunset bokeh","warm light interior","evening skyline"],
    "indie":["rainy street","vintage room","autumn walk"],
    "flamenco":["spain architecture","sunset orange sky","dramatic landscape"],
    "default":["galaxy space stars","ocean waves","northern lights"],
}

def get_theme(genre):
    k = genre.lower().replace(" ","-").replace("_","-")
    return GENRE_THEMES.get(k, GENRE_THEMES["default"])

def get_pexels_video(genre, duration_min=60):
    api_key = os.environ.get("PEXELS_API_KEY","")
    if not api_key:
        print("No PEXELS_API_KEY - using color background")
        return None
    k = genre.lower().replace(" ","").replace("-","").replace("&","")
    terms = GENRE_VISUALS.get(k, GENRE_VISUALS["default"])
    query = random.choice(terms)
    print(f"Searching Pexels: '{query}'")
    url = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=15&min_duration={duration_min}&orientation=landscape"
    req = urllib.request.Request(url, headers={"Authorization": api_key})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        videos = data.get("videos",[])
        if not videos:
            url2 = f"https://api.pexels.com/videos/search?query={urllib.parse.quote(query)}&per_page=15&orientation=landscape"
            req2 = urllib.request.Request(url2, headers={"Authorization": api_key})
            with urllib.request.urlopen(req2, timeout=15) as r2:
                data = json.loads(r2.read())
            videos = data.get("videos",[])
        if not videos: return None
        video = random.choice(videos[:8])
        hd = [f for f in video.get("video_files",[]) if f.get("width",0)>=1280]
        chosen = hd[0] if hd else video["video_files"][0]
        tmp = "/tmp/bg_video.mp4"
        print("Downloading Pexels background...")
        urllib.request.urlretrieve(chosen["link"], tmp)
        return tmp
    except Exception as e:
        print(f"Pexels failed: {e}")
        return None

def find_blueprint(mp3_path):
    stem = mp3_path.stem
    queue_dir = mp3_path.parent.parent.parent / "queue"
    if not queue_dir.exists():
        queue_dir = mp3_path.parent.parent / "queue"
    exact = queue_dir / f"{stem}.json"
    if exact.exists():
        with open(exact) as f: return json.load(f)
    if queue_dir.exists():
        bps = sorted(queue_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for bp in bps:
            if not (bp.parent / f"processed_{bp.name}").exists():
                with open(bp) as f: data = json.load(f)
                print(f"Using blueprint: {bp.name}")
                return data
    genre = mp3_path.parent.name.title()
    if genre.lower() == "music": genre = "Music"
    print(f"No blueprint - fallback genre: {genre}")
    track_name = stem.replace("-"," ").replace("_"," ").title()
    return {
        "genre": genre, "title": f"{track_name} - Goosebumps Music",
        "frisson_score": 82,
        "scientific_note": "Engineered using the neuroscience of frisson to trigger goosebumps.",
        "description": f"{track_name} is crafted to give you chills.\n\nSubscribe to the Goosebumps Channel for more.",
        "tags": ["goosebumps","frisson",genre.lower(),"royalty free music","chills"],
    }

def get_audio_duration(mp3_path):
    r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
        "-of","default=noprint_wrappers=1:nokey=1",str(mp3_path)],capture_output=True,text=True)
    return float(r.stdout.strip())

def create_video(mp3_path, output_dir):
    mp3_path = Path(mp3_path)
    bp = find_blueprint(mp3_path)
    genre = bp.get("genre","Music")
    title = bp.get("title","Goosebumps Music")
    note = bp.get("scientific_note","")
    score = bp.get("frisson_score","")
    duration = get_audio_duration(mp3_path)
    bg_color,wave1,wave2,text_color = get_theme(genre)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True,parents=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = genre.lower().replace(" ","_").replace("-","_")
    out = output_dir / f"{ts}_{slug}.mp4"
    def esc(t): return str(t).replace("'","").replace(":","").replace(",","")
    te = esc(title[:52]+"..." if len(str(title))>52 else title)
    ge = esc(genre.upper())
    ne = esc(note[:82]+"..." if len(str(note))>82 else note)
    se = esc(f"Frisson Score {score}%") if score else ""
    bg = get_pexels_video(genre, duration_min=int(duration*0.5))
    print(f"Creating: {out.name} | {genre} | {duration:.1f}s")
    if bg:
        fc=(f"[0:v]loop=loop=-1:size=9999,trim=duration={duration},scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},setsar=1[bv];"
            f"[bv]colorchannelmixer=rr=0.35:gg=0.35:bb=0.35[bd];"
            f"[1:a]showwaves=s={WIDTH}x{HEIGHT//4}:mode=cline:rate={FPS}:colors=#{wave1}|#{wave2}[wv];"
            f"[bd][wv]overlay=0:{HEIGHT//2-HEIGHT//8}:format=auto[ww];"
            f"[ww]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{te}':fontcolor=#{text_color}:fontsize=52:x=(w-text_w)/2:y=h*0.10:alpha='if(lt(t,1.5),t/1.5,1)':shadowcolor=black@0.8:shadowx=2:shadowy=2[wt];"
            f"[wt]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{ge}':fontcolor=#{wave1}:fontsize=26:x=(w-text_w)/2:y=h*0.21:alpha='if(lt(t,2),t/2,1)':shadowcolor=black@0.8:shadowx=1:shadowy=1[wg];"
            f"[wg]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf:text='{ne}':fontcolor=white@0.75:fontsize=20:x=(w-text_w)/2:y=h*0.88:alpha='if(lt(t,3),t/3,1)':shadowcolor=black@0.9:shadowx=1:shadowy=1[wn];"
            f"[wn]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='GOOSEBUMPS':fontcolor=#{wave1}@0.7:fontsize=16:x=w-text_w-25:y=25:shadowcolor=black@0.8:shadowx=1:shadowy=1[final]")
        if se: fc=fc.replace("[final]",f"[ps];[ps]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{se}':fontcolor=#{wave1}@0.85:fontsize=18:x=25:y=25:shadowcolor=black@0.8:shadowx=1:shadowy=1[final]")
        cmd=["ffmpeg","-y","-i",bg,"-i",str(mp3_path),"-filter_complex",fc,"-map","[final]","-map","1:a","-c:v","libx264","-preset","fast","-crf","20","-c:a","aac","-b:a","192k","-t",str(duration),"-pix_fmt","yuv420p","-movflags","+faststart",str(out)]
    else:
        fc=(f"[0:a]showwaves=s={WIDTH}x{HEIGHT//3}:mode=cline:rate={FPS}:colors=#{wave1}|#{wave2}[wv];"
            f"color=c=#{bg_color}:s={WIDTH}x{HEIGHT}:r={FPS}[bg];"
            f"[bg][wv]overlay=0:{HEIGHT//2-HEIGHT//6}[ww];"
            f"[ww]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='{te}':fontcolor=#{text_color}:fontsize=52:x=(w-text_w)/2:y=h*0.10:alpha='if(lt(t,1.5),t/1.5,1)':shadowcolor=black@0.5:shadowx=2:shadowy=2[wt];"
            f"[wt]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{ge}':fontcolor=#{wave1}:fontsize=26:x=(w-text_w)/2:y=h*0.21:alpha='if(lt(t,2),t/2,1)'[wg];"
            f"[wg]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf:text='{ne}':fontcolor=#{text_color}@0.7:fontsize=20:x=(w-text_w)/2:y=h*0.88:alpha='if(lt(t,3),t/3,1)'[wn];"
            f"[wn]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:text='GOOSEBUMPS':fontcolor=#{wave1}@0.6:fontsize=16:x=w-text_w-25:y=25[final]")
        if se: fc=fc.replace("[final]",f"[ps];[ps]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='{se}':fontcolor=#{wave1}@0.8:fontsize=18:x=25:y=25[final]")
        cmd=["ffmpeg","-y","-i",str(mp3_path),"-filter_complex",fc,"-map","[final]","-map","0:a","-c:v","libx264","-preset","fast","-crf","20","-c:a","aac","-b:a","192k","-shortest","-pix_fmt","yuv420p","-movflags","+faststart",str(out)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr[-3000:])
        raise RuntimeError("FFmpeg failed")
    print(f"Video created: {out}")
    return out, bp

def main():
    mp3_path = Path(sys.argv[1]) if len(sys.argv)>1 else Path("")
    if not mp3_path.name or not mp3_path.suffix:
        music_dir = Path(__file__).parent.parent / "music"
        mp3s = sorted(music_dir.rglob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not mp3s:
            print("No MP3 files in music/")
            sys.exit(1)
        mp3_path = mp3s[0]
        print(f"Auto-detected: {mp3_path}")
    if not mp3_path.exists():
        repo_root = Path(__file__).parent.parent
        mp3_path = repo_root / mp3_path
        if not mp3_path.exists():
            print(f"File not found: {mp3_path}")
            sys.exit(1)
    output_dir = Path(__file__).parent.parent / "output"
    video_path, bp = create_video(mp3_path, output_dir)
    state_path = output_dir / f"{video_path.stem}_state.json"
    with open(state_path,"w") as f:
        json.dump({"video_path":str(video_path),"mp3_path":str(mp3_path),"blueprint":bp},f,indent=2)
    print(f"State saved: {state_path}")
    print("Ready for upload.")

if __name__ == "__main__":
    main()
