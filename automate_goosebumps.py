"""
automate_goosebumps.py - Full automation for Goosebumps Channel
Handles blueprint generation AND Suno automation via Claude in Chrome.

Usage:
  python automate_goosebumps.py --genre afrobeat
  python automate_goosebumps.py --random
  python automate_goosebumps.py --all
"""

import anthropic
import json
import os
import sys
import time
import random
import subprocess
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURATION
# ============================================================
REPO_PATH = r"C:\Users\promo\OneDrive\Desktop\Goosbumps Channel\goosebumps-channel\goosebumps-channel"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

GENRES = [
    {"name": "Blues",            "folder": "blues"},
    {"name": "Jazz",             "folder": "jazz"},
    {"name": "K-Pop",            "folder": "kpop"},
    {"name": "Classical",        "folder": "classical"},
    {"name": "Hip-Hop",          "folder": "hiphop"},
    {"name": "Ambient",          "folder": "ambient"},
    {"name": "Rock",             "folder": "rock"},
    {"name": "EDM",              "folder": "edm"},
    {"name": "R&B",              "folder": "rnb"},
    {"name": "Gospel",           "folder": "gospel"},
    {"name": "Cinematic",        "folder": "cinematic"},
    {"name": "Folk",             "folder": "folk"},
    {"name": "Lo-Fi",            "folder": "lofi"},
    {"name": "Afrobeat",         "folder": "afrobeat"},
    {"name": "Latin",            "folder": "latin"},
    {"name": "Celtic",           "folder": "celtic"},
    {"name": "Indian Classical", "folder": "indianclassical"},
    {"name": "Flamenco",         "folder": "flamenco"},
    {"name": "Reggae",           "folder": "reggae"},
    {"name": "Neo-Soul",         "folder": "neosoul"},
    {"name": "Country",          "folder": "country"},
    {"name": "Metal",            "folder": "metal"},
    {"name": "Bossa Nova",       "folder": "bossanova"},
    {"name": "Synthwave",        "folder": "synthwave"},
    {"name": "Middle Eastern",   "folder": "middleeastern"},
    {"name": "Nordic Folk",      "folder": "nordicfolk"},
    {"name": "Bollywood",        "folder": "bollywood"},
    {"name": "Deep House",       "folder": "deephouse"},
    {"name": "Tango",            "folder": "tango"},
    {"name": "J-Pop",            "folder": "jpop"},
]

TRIGGERS = [
    "unexpected harmonic shift to a distant chord",
    "sudden shift from silence to full sound",
    "melodic tension building then resolving",
    "tempo near 65 BPM matching heartbeat",
    "unexpected new instrument entering",
    "emotional peak at golden ratio of track",
    "long note resolving into lush harmony",
    "raw solo voice no accompaniment",
    "key change at emotional peak",
    "call and response between instruments",
]

# ============================================================
# STEP 1: Generate blueprint
# ============================================================
def generate_blueprint(genre_name):
    print(f"\n🎵 Generating blueprint for: {genre_name}")

    intensity = random.randint(6, 10)
    selected_triggers = random.sample(TRIGGERS, random.randint(3, 5))

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are a music neuroscience expert. Blueprint a royalty-free {genre_name} track for frisson.
Triggers: {', '.join(selected_triggers)}
Intensity: {intensity}/10
Respond ONLY valid JSON no markdown:
{{"frisson_score":<int 55-99>,"scientific_analysis":"<2 sentences>","structure":"<3 sentences key BPM instruments>","suno_prompt":"<65 words no words frisson or goosebumps>","title":"<creative track title 2-5 words>"}}"""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.replace("```json", "").replace("```", "").strip()
    blueprint = json.loads(raw)
    blueprint["genre"] = genre_name
    blueprint["intensity"] = intensity
    blueprint["scientific_note"] = "Engineered using the neuroscience of frisson to trigger goosebumps."

    print(f"  ✅ Score: {blueprint['frisson_score']}% | Title: {blueprint['title']}")
    print(f"  📝 Prompt: {blueprint['suno_prompt'][:80]}...")
    return blueprint

# ============================================================
# STEP 2: Automate Suno via Claude in Chrome MCP
# ============================================================
def automate_suno(blueprint, folder_path):
    """
    Uses Claude in Chrome to operate suno.com:
    1. Navigate to suno.com
    2. Click Create
    3. Paste the prompt
    4. Set the title
    5. Click Generate
    6. Wait for song to finish
    7. Download the MP3
    8. Save to the genre folder
    """
    suno_prompt = blueprint["suno_prompt"]
    title = blueprint["title"]
    genre = blueprint["genre"]
    folder = Path(folder_path)

    print(f"\n🤖 Starting Suno automation for: {title}")
    print(f"   Claude in Chrome will now operate suno.com...")

    # Use Claude in Chrome MCP server (runs locally)
    # This connects to your Chrome browser via the extension
    MCP_BASE = "http://localhost:3000"

    try:
        # Get available tabs
        resp = requests.post(f"{MCP_BASE}/tool", json={
            "name": "tabs_context_mcp",
            "input": {"createIfEmpty": True}
        }, timeout=10)

        if resp.status_code != 200:
            raise Exception("Claude in Chrome MCP not available")

        tab_data = resp.json()
        tabs = tab_data.get("availableTabs", [])
        tab_id = tabs[0]["tabId"] if tabs else None

        if not tab_id:
            raise Exception("No Chrome tab available")

        def chrome(tool, input_data):
            r = requests.post(f"{MCP_BASE}/tool", json={"name": tool, "input": input_data}, timeout=60)
            return r.json()

        # Navigate to Suno
        print("   → Opening suno.com...")
        chrome("navigate", {"tabId": tab_id, "url": "https://suno.com/create"})
        time.sleep(4)

        # Take screenshot to find the input field
        chrome("computer", {"action": "screenshot", "tabId": tab_id})
        time.sleep(1)

        # Click on the prompt input area
        print("   → Clicking prompt field...")
        chrome("computer", {"action": "left_click", "coordinate": [784, 400], "tabId": tab_id})
        time.sleep(1)

        # Select all and type the prompt
        chrome("computer", {"action": "key", "text": "ctrl+a", "tabId": tab_id})
        chrome("computer", {"action": "type", "text": suno_prompt, "tabId": tab_id})
        time.sleep(1)

        # Click Create/Generate button
        print("   → Clicking Generate...")
        chrome("computer", {"action": "key", "text": "Return", "tabId": tab_id})
        time.sleep(2)

        # Wait for generation (usually 30-60 seconds)
        print("   → Waiting for Suno to generate song (60 seconds)...")
        time.sleep(60)

        print("   → Song should be ready — checking...")
        time.sleep(10)

        print(f"\n⚠️  Suno automation needs your help for the download step.")
        print(f"   Chrome should be open on suno.com showing your generated song.")
        print(f"   Please:")
        print(f"   1. Click the three dots (...) on the song")
        print(f"   2. Click Download")
        print(f"   3. Save as MP3 to: {folder}")
        print(f"   4. Press ENTER here when done")
        input("\n   Press ENTER after downloading...")

    except Exception as e:
        print(f"\n⚠️  Chrome automation unavailable: {e}")
        print(f"   Falling back to manual mode...")
        print()

        # Copy to clipboard as fallback
        try:
            subprocess.run(['clip'], input=suno_prompt.encode(), check=True)
            print(f"   ✅ Suno prompt copied to clipboard!")
        except:
            print(f"   📋 Suno prompt: {suno_prompt}")

        print()
        print(f"   Please:")
        print(f"   1. Go to suno.com/create")
        print(f"   2. Paste the prompt (already in clipboard)")
        print(f"   3. Set title to: {title}")
        print(f"   4. Click Generate")
        print(f"   5. Download the MP3 to: {folder}")
        print(f"   6. Press ENTER here when done")
        input("\n   Press ENTER after downloading...")

    # Find the downloaded MP3
    mp3_files = [f for f in folder.glob("*.mp3") if f.name != ".gitkeep"]
    if not mp3_files:
        print("❌ No MP3 found. Skipping.")
        return None

    latest = max(mp3_files, key=lambda f: f.stat().st_mtime)
    print(f"  ✅ MP3 ready: {latest.name}")
    return latest

# ============================================================
# STEP 3: Save blueprint to queue
# ============================================================
def save_blueprint(blueprint, mp3_path):
    queue_dir = Path(REPO_PATH) / "queue"
    queue_dir.mkdir(exist_ok=True)

    blueprint_path = queue_dir / f"{mp3_path.stem}.json"

    blueprint["title"] = f"{blueprint['title']} - Goosebumps Music"
    blueprint["description"] = (
        f"Experience the science of musical goosebumps.\n\n"
        f"This {blueprint['genre']} track is engineered using frisson research — "
        f"unexpected harmonic shifts, dynamic contrast, and melodic tension "
        f"proven to trigger dopamine release and the physical sensation of goosebumps.\n\n"
        f"Frisson Score: {blueprint['frisson_score']}%\n\n"
        f"Subscribe to the Goosebumps Channel for more frisson-engineered music.\n"
        f"#goosebumps #frisson #{blueprint['genre'].lower().replace(' ','')} #royaltyfreemusic"
    )
    blueprint["tags"] = [
        "goosebumps", "frisson", "music",
        blueprint["genre"].lower().replace(" ", ""),
        "royalty free music", "chills", "emotional music",
        "neuroscience", "dopamine"
    ]

    with open(blueprint_path, "w") as f:
        json.dump(blueprint, f, indent=2)

    print(f"  ✅ Blueprint saved: {blueprint_path.name}")
    return blueprint_path

# ============================================================
# STEP 4: Git push
# ============================================================
def git_push(genre_name, mp3_path):
    print(f"\n📤 Pushing to GitHub...")
    os.chdir(REPO_PATH)

    steps = [
        ["git", "add", "music/", "queue/"],
        ["git", "commit", "-m", f"Add {genre_name}: {mp3_path.stem}"],
    ]

    for cmd in steps:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ⚠️  {result.stderr.strip()}")
        else:
            print(f"  ✅ {' '.join(cmd[:2])}")

    # Pull then push
    subprocess.run(["git", "pull", "--no-edit"], capture_output=True)
    result = subprocess.run(["git", "push"], capture_output=True, text=True)

    if result.returncode == 0:
        print(f"  ✅ Pushed!")
        print(f"\n🚀 GitHub Actions will now create the video and upload to YouTube!")
        print(f"   Check: https://github.com/promoteglobal/goosebumps-Channel/actions")
    else:
        print(f"  ❌ Push failed: {result.stderr}")

# ============================================================
# MAIN
# ============================================================
def process_genre(genre):
    genre_name = genre["name"]
    folder_path = Path(REPO_PATH) / "music" / genre["folder"]
    folder_path.mkdir(exist_ok=True)

    try:
        blueprint = generate_blueprint(genre_name)
        mp3_path = automate_suno(blueprint, folder_path)
        if not mp3_path:
            return False
        save_blueprint(blueprint, mp3_path)
        git_push(genre_name, mp3_path)
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Goosebumps Channel Automation")
    parser.add_argument("--genre", help="Genre folder name e.g. blues, afrobeat")
    parser.add_argument("--all", action="store_true", help="Process all 30 genres")
    parser.add_argument("--random", action="store_true", help="Pick one random genre")
    args = parser.parse_args()

    if not ANTHROPIC_API_KEY:
        print("❌ Set your Anthropic API key:")
        print("   $env:ANTHROPIC_API_KEY = 'sk-ant-...'")
        sys.exit(1)

    print("=" * 60)
    print("🎵 GOOSEBUMPS CHANNEL AUTOMATION")
    print(f"   {datetime.now().strftime('%A %Y-%m-%d %H:%M')}")
    print("=" * 60)

    if args.genre:
        genre = next((g for g in GENRES if g["folder"] == args.genre), None)
        if not genre:
            print(f"❌ Genre '{args.genre}' not found")
            print(f"   Available: {', '.join(g['folder'] for g in GENRES)}")
            sys.exit(1)
        process_genre(genre)

    elif args.all:
        print(f"Processing all {len(GENRES)} genres...")
        for i, genre in enumerate(GENRES):
            print(f"\n[{i+1}/{len(GENRES)}] {genre['name']}")
            process_genre(genre)
            if i < len(GENRES) - 1:
                print("⏳ Waiting 60 seconds before next genre...")
                time.sleep(60)

    else:
        # Default or --random: pick one random genre
        genre = random.choice(GENRES)
        print(f"🎲 Random genre selected: {genre['name']}")
        process_genre(genre)

if __name__ == "__main__":
    main()