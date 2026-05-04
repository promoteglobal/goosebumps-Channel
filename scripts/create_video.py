"""
create_video.py
Takes an MP3 file and creates a YouTube-ready MP4 with animated waveform + title card.
Works with or without a blueprint JSON in the /queue folder.

Usage:
    python scripts/create_video.py music/yourfile.mp3
"""

import subprocess
import json
import sys
import os
from pathlib import Path
from datetime import datetime

WIDTH = 1920
HEIGHT = 1080
FPS = 30

BG_COLOR = "0a0a1a"
WAVE_COLOR = "7f77dd"
WAVE_COLOR2 = "5dcaa5"
TITLE_COLOR = "eeedfe"
SUBTITLE_COLOR = "afa9ec"
ACCENT_COLOR = "534ab7"


def find_blueprint(mp3_path: Path) -> dict:
    """Find the matching blueprint JSON, or generate fallback metadata from filename."""
    stem = mp3_path.stem
    queue_dir = mp3_path.parent.parent / "queue"

    exact = queue_dir / f"{stem}.json"
    if exact.exists():
        with open(exact) as f:
            return json.load(f)

    if queue_dir.exists():
        blueprints = sorted(queue_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for bp_path in blueprints:
            if not (bp_path.parent / f"processed_{bp_path.name}").exists():
                with open(bp_path) as f:
                    data = json.load(f)
                print(f"Using blueprint: {bp_path.name}")
                return data

    print("No blueprint found in queue/ — using fallback metadata from filename.")
    track_name = mp3_path.stem.replace("-", " ").replace("_", " ").title()
    return {
        "genre": "Music",
        "title": f"{track_name} — Goosebumps Music",
        "frisson_score": 80,
        "scientific_note": "Music engineered to trigger frisson — the neuroscience of goosebumps.",
        "description": (
            f"{track_name} is a carefully crafted piece of music designed to give you goosebumps.\n\n"
            "Our tracks use the neuroscience of frisson — the physical sensation of chills caused by music — "
            "to create deeply emotional listening experiences.\n\n"
            "Subscribe to the Goosebumps Channel for more frisson-engineered music."
        ),
        "tags": ["goosebumps", "frisson", "royalty free music", "chills", "emotional music"],
    }


def get_audio_duration(mp3_path: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def create_video(mp3_path: Path, output_dir: Path):
    mp3_path = Path(mp3_path)
    blueprint = find_blueprint(mp3_path)

    genre = blueprint.get("genre", "Music")
    title = blueprint.get("title", "Goosebumps Music")
    scientific_note = blueprint.get("scientific_note", "")
    frisson_score = blueprint.get("frisson_score", "")

    duration = get_audio_duration(mp3_path)

    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    genre_slug = genre.lower().replace(" ", "_")
    output_path = output_dir / f"{timestamp}_{genre_slug}.mp4"

    def esc(text):
        return str(text).replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

    title_esc = esc(title)
    genre_esc = esc(genre.upper())
    note_esc = esc(scientific_note[:80] + "..." if len(str(scientific_note)) > 80 else scientific_note)
    score_esc = esc(f"Frisson Score: {frisson_score}%") if frisson_score else ""

    filter_complex = (
        f"[0:a]showwaves=s={WIDTH}x{HEIGHT//3}:mode=cline:rate={FPS}"
        f":colors=#{WAVE_COLOR}|#{WAVE_COLOR2}[wave];"
        f"color=c=#{BG_COLOR}:s={WIDTH}x{HEIGHT}:r={FPS}[bg];"
        f"[bg][wave]overlay=0:{HEIGHT//2 - HEIGHT//6}[with_wave];"
        f"[with_wave]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":text='{title_esc}':fontcolor=#{TITLE_COLOR}:fontsize=52"
        f":x=(w-text_w)/2:y=h*0.12:alpha='if(lt(t,1.5),t/1.5,1)'[with_title];"
        f"[with_title]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f":text='{genre_esc}':fontcolor=#{SUBTITLE_COLOR}:fontsize=28"
        f":x=(w-text_w)/2:y=h*0.22:alpha='if(lt(t,2),t/2,1)'[with_genre];"
        f"[with_genre]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
        f":text='{note_esc}':fontcolor=#{SUBTITLE_COLOR}@0.7:fontsize=22"
        f":x=(w-text_w)/2:y=h*0.88:alpha='if(lt(t,3),t/3,1)'[with_note];"
        f"[with_note]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":text='GOOSEBUMPS':fontcolor=#{ACCENT_COLOR}@0.6:fontsize=18"
        f":x=w-text_w-30:y=30[final]"
    )

    if score_esc:
        filter_complex = filter_complex.replace(
            "[final]",
            f"[prescore];[prescore]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            f":text='{score_esc}':fontcolor=#{WAVE_COLOR}@0.8:fontsize=20:x=30:y=30[final]"
        )

    cmd = [
        "ffmpeg", "-y", "-i", str(mp3_path),
        "-filter_complex", filter_complex,
        "-map", "[final]", "-map", "0:a",
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        str(output_path)
    ]

    print(f"Creating video: {output_path.name} ({duration:.1f}s)")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    print(f"Video created: {output_path}")
    return output_path, blueprint


def main():
    mp3_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("")

    if not mp3_path.name or not mp3_path.suffix:
        music_dir = Path(__file__).parent.parent / "music"
        mp3s = sorted(music_dir.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not mp3s:
            print("No MP3 files found in music/ folder")
            sys.exit(1)
        mp3_path = mp3s[0]
        print(f"Auto-detected latest MP3: {mp3_path.name}")

    if not mp3_path.exists():
        repo_root = Path(__file__).parent.parent
        mp3_path = repo_root / mp3_path
        if not mp3_path.exists():
            print(f"File not found: {mp3_path}")
            sys.exit(1)

    output_dir = Path(__file__).parent.parent / "output"
    video_path, blueprint = create_video(mp3_path, output_dir)

    state_path = output_dir / f"{video_path.stem}_state.json"
    with open(state_path, "w") as f:
        json.dump({"video_path": str(video_path), "mp3_path": str(mp3_path), "blueprint": blueprint}, f, indent=2)

    print(f"State saved: {state_path}")
    print("Ready for upload.")


if __name__ == "__main__":
    main()