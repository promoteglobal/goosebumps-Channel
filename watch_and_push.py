"""
watch_and_push.py - Watches music folders and auto-pushes new MP3s to GitHub.

Run this in a separate terminal window and leave it running.
The moment you save an MP3 to any music/genre/ folder it automatically:
1. Detects which genre folder it's in
2. Git adds, commits, and pushes
3. GitHub Actions takes over (video + YouTube upload)

Usage: python watch_and_push.py
"""

import os
import time
import subprocess
from pathlib import Path

REPO_PATH = r"C:\Users\promo\OneDrive\Desktop\Goosbumps Channel\goosebumps-channel\goosebumps-channel"
MUSIC_PATH = Path(REPO_PATH) / "music"
CHECK_INTERVAL = 5  # Check every 5 seconds

def get_mp3s():
    """Get all MP3 files with their modification times."""
    mp3s = {}
    for mp3 in MUSIC_PATH.rglob("*.mp3"):
        mp3s[str(mp3)] = mp3.stat().st_mtime
    return mp3s

def git_push(mp3_path):
    """Auto git add, commit, push."""
    mp3 = Path(mp3_path)
    genre_folder = mp3.parent.name
    track_name = mp3.stem

    print(f"\n🎵 New MP3 detected: {track_name}")
    print(f"   Genre: {genre_folder}")
    print(f"   Auto-pushing to GitHub...")

    os.chdir(REPO_PATH)

    commands = [
        (["git", "add", f"music/{genre_folder}/"], "Adding files"),
        (["git", "commit", "-m", f"Add {genre_folder}: {track_name}"], "Committing"),
    ]

    for cmd, label in commands:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"   ✅ {label}")
        else:
            print(f"   ⚠️  {label}: {result.stderr.strip()}")

    # Pull then push
    subprocess.run(["git", "pull", "--no-edit"], capture_output=True)
    result = subprocess.run(["git", "push"], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"   ✅ Pushed!")
        print(f"   🚀 GitHub Actions will now create video and upload to YouTube!")
        print(f"   📺 Check: https://github.com/promoteglobal/goosebumps-Channel/actions")
    else:
        print(f"   ❌ Push failed: {result.stderr.strip()}")

def main():
    print("=" * 55)
    print("👀 GOOSEBUMPS CHANNEL - FILE WATCHER")
    print("=" * 55)
    print(f"Watching: {MUSIC_PATH}")
    print(f"Checking every {CHECK_INTERVAL} seconds...")
    print("Drop any MP3 into a music/genre/ folder and")
    print("it will auto-push to GitHub instantly!")
    print("\nPress Ctrl+C to stop.\n")

    # Get initial state
    known_mp3s = get_mp3s()
    print(f"Found {len(known_mp3s)} existing MP3s — watching for new ones...\n")

    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            current_mp3s = get_mp3s()

            # Find new MP3s
            new_mp3s = {
                path: mtime
                for path, mtime in current_mp3s.items()
                if path not in known_mp3s
            }

            if new_mp3s:
                for mp3_path in new_mp3s:
                    git_push(mp3_path)
                known_mp3s = current_mp3s

        except KeyboardInterrupt:
            print("\n\n👋 Watcher stopped.")
            break
        except Exception as e:
            print(f"⚠️  Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()