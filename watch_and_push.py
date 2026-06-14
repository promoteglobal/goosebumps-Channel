"""
watch_and_push.py - Watches music folders, pushes new MP3s, and directly
triggers the GitHub Actions workflow with the exact filename.
"""

import os, time, subprocess, urllib.request, json
from pathlib import Path

REPO_PATH    = r"C:\Users\promo\OneDrive\Desktop\Goosbumps Channel\goosebumps-channel\goosebumps-channel"
MUSIC_PATH   = Path(REPO_PATH) / "music"
CHECK_INTERVAL = 5

GITHUB_OWNER = "promoteglobal"
GITHUB_REPO  = "goosebumps-Channel"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

def get_mp3s():
    return {str(p): p.stat().st_mtime for p in MUSIC_PATH.rglob("*.mp3")}

def trigger_workflow(genre, filename):
    if not GITHUB_TOKEN or GITHUB_TOKEN == "PUT_YOUR_TOKEN_HERE":
        print("   ⚠️  No GitHub token — set GITHUB_TOKEN in code!")
        return False
    try:
        data = json.dumps({
            "ref": "main",
            "inputs": {"mp3_filename": f"{genre}/{filename}"}
        }).encode()
        url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/upload_youtube.yml/dispatches"
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        })
        urllib.request.urlopen(req, timeout=15)
        print(f"   ✅ Workflow triggered: {genre}/{filename}")
        return True
    except Exception as e:
        print(f"   ⚠️  API trigger failed: {e}")
        return False

def git_push(mp3_path):
    mp3   = Path(mp3_path)
    genre = mp3.parent.name
    name  = mp3.name
    stem  = mp3.stem

    print(f"\n🎵 New MP3: {stem}")
    print(f"   Genre: {genre}")
    print(f"   Pushing to GitHub...")

    os.chdir(REPO_PATH)

    # Copy blueprint.json from music/ root into the genre folder if present
    root_bp  = MUSIC_PATH / "blueprint.json"
    genre_bp = MUSIC_PATH / genre / "blueprint.json"
    if root_bp.exists():
        import shutil
        shutil.copy2(root_bp, genre_bp)
        print(f"   📋 Copied blueprint.json → music/{genre}/")

    subprocess.run(["git", "add", f"music/{genre}/"], capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", f"Add {genre}: {stem}"],
        capture_output=True, text=True
    )
    print(f"   ✅ Committed" if result.returncode == 0 else f"   ⚠️  Commit: {result.stderr.strip()}")

    subprocess.run(["git", "pull", "--no-edit"], capture_output=True)
    result = subprocess.run(["git", "push"], capture_output=True, text=True)
    print(f"   ✅ Pushed!" if result.returncode == 0 else f"   ❌ Push failed: {result.stderr.strip()}")

    time.sleep(3)
    trigger_workflow(genre, name)

def main():
    print("=" * 55)
    print("👀 GOOSEBUMPS CHANNEL - FILE WATCHER")
    print("=" * 55)
    print(f"Watching: {MUSIC_PATH}")
    if GITHUB_TOKEN and GITHUB_TOKEN != "PUT_YOUR_TOKEN_HERE":
        print("✅ GitHub token found - workflow will auto-trigger!")
    else:
        print("⚠️  No GitHub token - edit GITHUB_TOKEN in watch_and_push.py")
    print("\nPress Ctrl+C to stop.\n")

    known = get_mp3s()
    print(f"Found {len(known)} existing MP3s — watching for new ones...\n")

    while True:
        try:
            time.sleep(CHECK_INTERVAL)
            current = get_mp3s()
            new = {p: t for p, t in current.items() if p not in known}
            if new:
                for mp3_path in new:
                    git_push(mp3_path)
                known = current
        except KeyboardInterrupt:
            print("\n\n👋 Watcher stopped.")
            break
        except Exception as e:
            print(f"⚠️  Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()