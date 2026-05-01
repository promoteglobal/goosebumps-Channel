"""
create_video.py
Takes an MP3 file and its matching blueprint JSON, then creates
a YouTube-ready MP4 with animated waveform + title card.

Usage:
    python scripts/create_video.py music/20240101_120000_blues.mp3
"""

import subprocess
import json
import sys
import os
from pathlib import Path
from datetime import datetime


# Video settings
WIDTH = 1920
HEIGHT = 1080
FPS = 30
FONT = "DejaVuSans"

# Colors — deep space purple palette for goosebumps brand
BG_COLOR = "0a0a1a"
WAVE_COLOR = "7f77dd"
WAVE_COLOR2 = "5dcaa5"
TITLE_COLOR = "eeedfe"
SUBTITLE_COLOR = "afa9ec"
ACCENT_COLOR = "534ab7"


def find_blueprint(mp3_path: Path) -> dict:
    """Find the matching blueprint JSON for an MP3 file."""
    stem = mp3_path.stem
    queue_dir = mp3_path.parent.parent / "queue"

    # Try exact name match first
    exact = queue_dir / f"{stem}.json"
    if exact.exists():
        with open(exact) as f:
            return json.load(f)

    # Find most recent unprocessed blueprint
    blueprints = sorted(queue_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for bp_path in blueprints:
        if not (bp_path.parent / f"processed_{bp_path.name}").exists():
            with open(bp_path) as f:
                data = json.load(f)
            print(f"Using blueprint: {bp_path.name}")
            return data

    raise FileNotFoundError("No matching blueprint found in queue/")


def get_audio_duration(mp3_path: Path) -> float:
    """Get duration of audio file in seconds."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def create_video(mp3_path: Path, output_dir: Path) -> Path:
    """Create animated waveform video from MP3 + blueprint."""

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

    # Escape text for FFmpeg drawtext filter
    def esc(text):
        return text.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

    title_esc = esc(title)
    genre_esc = esc(genre.upper())
    note_esc = esc(scientific_note[:80] + "..." if len(scientific_note) > 80 else scientific_note)
    score_esc = esc(f"Frisson Score: {frisson_score}%") if frisson_score else ""

    # FFmpeg filter complex:
    # - Solid dark background
    # - Dual animated waveform (mirrored)
    # - Subtle glow effect on waveform
    # - Title text fade in
    # - Genre badge
    # - Scientific note at bottom
    # - Goosebumps channel watermark

    filter_complex = (
        f"[0:a]showwaves=s={WIDTH}x{HEIGHT//3}:mode=cline:rate={FPS}"
        f":colors=#{WAVE_COLOR}|#{WAVE_COLOR2}[wave];"

        f"color=c=#{BG_COLOR}:s={WIDTH}x{HEIGHT}:r={FPS}[bg];"

        # Position waveform in center-lower area
        f"[bg][wave]overlay=0:{HEIGHT//2 - HEIGHT//6}[with_wave];"

        # Title text (fades in over 1.5s)
        f"[with_wave]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":text='{title_esc}'"
        f":fontcolor=#{TITLE_COLOR}"
        f":fontsize=52"
        f":x=(w-text_w)/2"
        f":y=h*0.12"
        f":alpha='if(lt(t,1.5),t/1.5,1)'[with_title];"

        # Genre badge
        f"[with_title]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        f":text='{genre_esc}'"
        f":fontcolor=#{SUBTITLE_COLOR}"
        f":fontsize=28"
        f":x=(w-text_w)/2"
        f":y=h*0.22"
        f":alpha='if(lt(t,2),t/2,1)'[with_genre];"

        # Scientific note at bottom
        f"[with_genre]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"
        f":text='{note_esc}'"
        f":fontcolor=#{SUBTITLE_COLOR}@0.7"
        f":fontsize=22"
        f":x=(w-text_w)/2"
        f":y=h*0.88"
        f":alpha='if(lt(t,3),t/3,1)'[with_note];"

        # Channel watermark
        f"[with_note]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        f":text='GOOSEBUMPS'"
        f":fontcolor=#{ACCENT_COLOR}@0.6"
        f":fontsize=18"
        f":x=w-text_w-30"
        f":y=30[final]"
    )

    # Add frisson score if available
    if score_esc:
        filter_complex = filter_complex.replace(
            "[final]",
            f"[prescore];[prescore]drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
            f":text='{score_esc}'"
            f":fontcolor=#{WAVE_COLOR}@0.8"
            f":fontsize=20"
            f":x=30:y=30[final]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(mp3_path),
        "-filter_complex", filter_complex,
        "-map", "[final]",
        "-map", "0:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path)
    ]

    print(f"Creating video: {output_path.name}")
    print(f"Duration: {duration:.1f}s")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print("FFmpeg error:")
        print(result.stderr[-2000:])
        raise RuntimeError("FFmpeg failed")

    print(f"Video created: {output_path}")
    return output_path, blueprint


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/create_video.py music/yourfile.mp3")
        sys.exit(1)

    mp3_path = Path(sys.argv[1])
    if not mp3_path.exists():
        print(f"File not found: {mp3_path}")
        sys.exit(1)

    output_dir = Path(__file__).parent.parent / "output"
    video_path, blueprint = create_video(mp3_path, output_dir)

    # Save video path + blueprint for next step
    state_path = output_dir / f"{video_path.stem}_state.json"
    with open(state_path, "w") as f:
        json.dump({
            "video_path": str(video_path),
            "mp3_path": str(mp3_path),
            "blueprint": blueprint
        }, f, indent=2)

    print(f"\nState saved: {state_path}")
    print("Ready for upload step.")


if __name__ == "__main__":
    main()
