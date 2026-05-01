"""
upload_youtube.py
Uploads a video to your Goosebumps YouTube channel.

First-time setup: run with --auth flag to authenticate.
After that, it uses the saved refresh token automatically.

Usage:
    python scripts/upload_youtube.py --auth          # one-time setup
    python scripts/upload_youtube.py output/video.mp4   # upload a video
    python scripts/upload_youtube.py --auto          # upload latest in /output
"""

import os
import sys
import json
import argparse
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
SECRETS_FILE = Path(__file__).parent.parent / "client_secrets.json"
TOKEN_FILE = Path(__file__).parent.parent / "youtube_token.json"


def authenticate():
    """Run the one-time OAuth flow to get a refresh token."""
    if not SECRETS_FILE.exists():
        print("ERROR: client_secrets.json not found.")
        print("\nTo get it:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create a project (or use existing)")
        print("3. Enable 'YouTube Data API v3'")
        print("4. Go to Credentials > Create > OAuth 2.0 Client ID")
        print("5. Application type: Desktop app")
        print("6. Download JSON and save as client_secrets.json in project root")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(SECRETS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"\nAuthentication successful!")
    print(f"Token saved to: {TOKEN_FILE}")
    print("\nCopy the contents of youtube_token.json into a GitHub secret")
    print("named YOUTUBE_TOKEN for automated uploads.")


def get_credentials():
    """Load credentials, refreshing if expired."""
    if not TOKEN_FILE.exists():
        raise FileNotFoundError(
            "youtube_token.json not found. Run: python scripts/upload_youtube.py --auth"
        )

    creds_data = json.loads(TOKEN_FILE.read_text())

    # Support GitHub Actions: token can also come from env var
    if os.environ.get("YOUTUBE_TOKEN"):
        creds_data = json.loads(os.environ["YOUTUBE_TOKEN"])

    creds = Credentials.from_authorized_user_info(creds_data, SCOPES)

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def upload_video(video_path: Path, blueprint: dict) -> str:
    """Upload video to YouTube. Returns the video URL."""

    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    title = blueprint.get("title", "Goosebumps Music")
    description = blueprint.get("description", "")
    tags = blueprint.get("tags", [])
    genre = blueprint.get("genre", "")
    frisson_score = blueprint.get("frisson_score", "")
    scientific_note = blueprint.get("scientific_note", "")

    # Append science credit and frisson score to description
    full_description = f"""{description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The Science: {scientific_note}
Frisson Score: {frisson_score}% (neuroscience-based goosebump prediction)

Genre: {genre}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All music on this channel is 100% original and royalty-free,
created using the neuroscience of musical frisson.

#Goosebumps #FrissonMusic #{genre.replace(' ', '')} #RoyaltyFree #MusicScience"""

    body = {
        "snippet": {
            "title": title,
            "description": full_description,
            "tags": tags + ["goosebumps", "frisson", "royalty free music", genre.lower(), "music science"],
            "categoryId": "10",  # Music category
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        }
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 5  # 5MB chunks
    )

    print(f"Uploading: {video_path.name}")
    print(f"Title: {title}")

    request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"  Upload progress: {pct}%")

    video_id = response["id"]
    url = f"https://www.youtube.com/watch?v={video_id}"
    print(f"\nUploaded successfully!")
    print(f"URL: {url}")

    return url


def find_latest_output() -> tuple:
    """Find the latest video + state file in /output."""
    output_dir = Path(__file__).parent.parent / "output"
    states = sorted(output_dir.glob("*_state.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    for state_path in states:
        # Skip already uploaded ones
        done_marker = state_path.with_suffix(".uploaded")
        if done_marker.exists():
            continue

        with open(state_path) as f:
            state = json.load(f)

        video_path = Path(state["video_path"])
        if video_path.exists():
            return video_path, state["blueprint"], state_path

    raise FileNotFoundError("No unuploaded videos found in output/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth", action="store_true", help="Run one-time OAuth setup")
    parser.add_argument("--auto", action="store_true", help="Upload latest video in /output")
    parser.add_argument("video", nargs="?", help="Path to MP4 to upload")
    args = parser.parse_args()

    if args.auth:
        authenticate()
        return

    if args.auto:
        video_path, blueprint, state_path = find_latest_output()
    elif args.video:
        video_path = Path(args.video)
        state_path = video_path.parent / f"{video_path.stem}_state.json"
        if not state_path.exists():
            print(f"State file not found: {state_path}")
            print("Run create_video.py first.")
            sys.exit(1)
        with open(state_path) as f:
            blueprint = json.load(f)["blueprint"]
    else:
        parser.print_help()
        sys.exit(1)

    url = upload_video(video_path, blueprint)

    # Mark as uploaded
    state_path.with_suffix(".uploaded").write_text(url)
    print(f"\nDone. Video live at: {url}")


if __name__ == "__main__":
    main()
