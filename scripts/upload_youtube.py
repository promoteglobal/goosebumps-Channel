import os, json, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_youtube_client():
    token_data = os.environ.get("YOUTUBE_TOKEN")
    if token_data:
        creds = Credentials.from_authorized_user_info(json.loads(token_data))
    else:
        token_file = Path(__file__).parent.parent / "youtube_token.json"
        with open(token_file) as f:
            creds = Credentials.from_authorized_user_info(json.load(f))
    return build("youtube", "v3", credentials=creds)

def find_latest_state():
    output_dir = Path(__file__).parent.parent / "output"
    # Only look at state files that have NO matching .uploaded file
    states = sorted(output_dir.glob("*_state.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for state in states:
        uploaded = Path(str(state).replace("_state.json", "_state.uploaded"))
        if not uploaded.exists():
            return state
    return None

def build_description(bp):
    genre     = bp.get("genre", "Music")
    title     = bp.get("title", "").replace(" - Goosebumps Music", "").strip()
    score     = bp.get("frisson_score", "")
    analysis  = bp.get("scientific_analysis", "")
    structure = bp.get("structure", "")

    desc = f"{title} is crafted to give you chills using the science of musical frisson.\n\n"
    desc += "Subscribe to the Goosebumps Channel for more.\n\n"
    desc += "━" * 30 + "\n"
    desc += "The Science: Engineered using the neuroscience of frisson to trigger goosebumps.\n"

    if score:
        desc += f"Frisson Score: {score}% (neuroscience-based goosebump prediction)\n"
    if analysis:
        desc += f"\n{analysis}\n"
    if structure:
        desc += f"\n{structure}\n"

    desc += f"\nGenre: {genre}\n"
    desc += "━" * 30 + "\n\n"
    desc += "All music on this channel is 100% original and royalty-free, "
    desc += "created using the neuroscience of musical frisson.\n\n"
    desc += f"#Goosebumps #FrissonMusic #{genre.replace(' ','')} #RoyaltyFree #MusicScience"
    return desc

def upload_video(youtube, state_path):
    with open(state_path) as f:
        state = json.load(f)

    video_path = state["video_path"]
    bp = state.get("blueprint", {})

    # Build title from blueprint
    raw_title = bp.get("title", "")
    if raw_title:
        raw_title = raw_title.replace(" - Goosebumps Music", "").strip()
        title = f"{raw_title} - Goosebumps Music"
    else:
        # Fall back to video filename
        stem = Path(video_path).stem
        title = f"{stem} - Goosebumps Music"
    title = title[:100]

    description = build_description(bp)

    genre = bp.get("genre", "music").lower().replace(" ", "")
    tags = bp.get("tags", []) or [
        "goosebumps", "frisson", "music", genre,
        "royalty free music", "chills", "emotional music",
        "neuroscience", "dopamine"
    ]

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "10",
        },
        "status": {"privacyStatus": "public"},
    }

    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploading: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"Uploaded: https://youtube.com/watch?v={video_id}")

    # Mark as uploaded using correct path
    uploaded_path = Path(str(state_path).replace("_state.json", "_state.uploaded"))
    uploaded_path.touch()
    return video_id

def main():
    if "--auth" in sys.argv:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secrets.json",
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )
        creds = flow.run_local_server(port=0)
        with open("youtube_token.json", "w") as f:
            f.write(creds.to_json())
        print("Auth complete - youtube_token.json saved")
        return

    youtube = get_youtube_client()
    state = find_latest_state()
    if not state:
        print("No unuploaded videos found")
        return
    print(f"Uploading: {state}")
    upload_video(youtube, state)

if __name__ == "__main__":
    main()