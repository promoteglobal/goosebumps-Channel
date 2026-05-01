# Goosebumps Channel — Automated YouTube Pipeline

Fully automated frisson music channel. Uses the neuroscience of goosebumps to
generate music blueprints, creates visualizer videos, and uploads to YouTube on a schedule.

---

## How it works

```
GitHub Actions (cron)
  → Claude API generates frisson blueprint + Suno prompt
  → You paste prompt into Suno, download MP3 (only manual step)
  → Push MP3 to /music folder in this repo
  → GitHub Actions automatically:
      - Creates animated waveform video with FFmpeg
      - Uploads to your Goosebumps YouTube channel
```

---

## One-time setup (do this once, then everything is automatic)

### Step 1 — Fork / clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/goosebumps-channel.git
cd goosebumps-channel
pip install -r requirements.txt
```

### Step 2 — Get your Anthropic API key

1. Go to https://console.anthropic.com/
2. Settings → API Keys → Create Key
3. Copy the key (starts with `sk-ant-...`)

### Step 3 — Set up YouTube API (takes ~10 min)

1. Go to https://console.cloud.google.com/
2. Create a new project called "Goosebumps Channel"
3. Search for "YouTube Data API v3" → Enable it
4. Go to **Credentials** → **+ Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Desktop app** → name it "Goosebumps Bot"
6. Click **Download JSON** → save as `client_secrets.json` in this project folder
7. Run the auth script (opens a browser, sign in to your Goosebumps YouTube account):

```bash
python scripts/upload_youtube.py --auth
```

8. After signing in, a file called `youtube_token.json` is created. Copy its contents.

> ⚠️ Never commit `client_secrets.json` or `youtube_token.json` to GitHub.
> They are already in `.gitignore`.

### Step 4 — Add GitHub Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these two secrets:

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key (`sk-ant-...`) |
| `YOUTUBE_TOKEN` | The full contents of `youtube_token.json` |

### Step 5 — Enable GitHub Actions

Go to your repo → **Actions** tab → click **Enable Actions**

That's it. Setup is complete.

---

## Daily workflow (after setup)

### Automatic (no action needed)
- Every Monday, Wednesday, Friday at 9am UTC:
  GitHub Actions generates a new frisson blueprint and saves it to `/queue`
- You get an email notification with the Suno prompt

### Your only manual step (~2 minutes, 3x per week)
1. Open the latest file in `/queue` folder on GitHub
2. Copy the `suno_prompt` text
3. Go to https://suno.com → paste prompt → generate
4. Download the MP3
5. Drag the MP3 into the `/music` folder in your repo and push

### Then fully automatic
- GitHub Actions detects the new MP3
- Creates animated video with FFmpeg (waveform + title + science note)
- Uploads to your YouTube channel with title, description, tags
- Marks as done

---

## Manual commands (run from VSCode terminal)

Generate a blueprint right now:
```bash
python scripts/generate_blueprint.py
```

Generate a specific genre:
```bash
GENRE="Jazz" python scripts/generate_blueprint.py
```

Create video from an MP3:
```bash
python scripts/create_video.py music/your_track.mp3
```

Upload latest video:
```bash
python scripts/upload_youtube.py --auto
```

---

## Folder structure

```
goosebumps-channel/
├── .github/
│   └── workflows/
│       ├── generate_blueprint.yml   # runs 3x/week, generates blueprints
│       └── upload_youtube.yml       # triggers on MP3 push, creates + uploads video
├── scripts/
│   ├── generate_blueprint.py        # Claude API → frisson blueprint
│   ├── create_video.py              # MP3 → MP4 with FFmpeg
│   └── upload_youtube.py            # MP4 → YouTube
├── music/                           # Drop your Suno MP3s here
├── queue/                           # Auto-generated blueprints wait here
├── output/                          # Created videos stored here
├── requirements.txt
├── client_secrets.json              # ← YOUR FILE, never commit (gitignored)
├── youtube_token.json               # ← YOUR FILE, never commit (gitignored)
└── README.md
```

---

## Changing the schedule

Edit `.github/workflows/generate_blueprint.yml` — the cron line:

```yaml
- cron: '0 9 * * 1,3,5'   # Mon, Wed, Fri at 9am UTC
```

Cron format: `minute hour day month weekday`
- Daily at 8am UTC: `0 8 * * *`
- Twice a week: `0 9 * * 1,4`

---

## Monetization (once you have subscribers)

- **YouTube Memberships** — enable at 500+ subscribers, earn $2–10/member/month
- **DistroKid ($22/year)** — distribute same tracks to Spotify, Apple Music for streaming royalties
- **Gumroad** — sell "Frisson Packs" (10-track albums) for $5–10 each
- **Patreon** — offer the science breakdown behind each track as bonus content

---

## Troubleshooting

**Blueprint generates but video fails:**
- Make sure FFmpeg is installed: `ffmpeg -version`
- On Mac: `brew install ffmpeg`
- On Ubuntu: `sudo apt install ffmpeg fonts-dejavu`

**YouTube upload fails with 403:**
- Your token may have expired. Run `python scripts/upload_youtube.py --auth` again
- Update the `YOUTUBE_TOKEN` secret in GitHub with the new token contents

**GitHub Actions not running:**
- Check Actions tab for error logs
- Make sure both secrets (`ANTHROPIC_API_KEY` and `YOUTUBE_TOKEN`) are set

---

## When Suno releases an official API

Edit `generate_blueprint.py` — add a call to the Suno API after generating the blueprint,
save the MP3 to `/music`, and push. The upload workflow will trigger automatically.
The whole thing becomes 100% hands-free.
