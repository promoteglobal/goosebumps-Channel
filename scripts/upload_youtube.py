import os, json, sys, pickle, subprocess
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

def get_youtube_client():
    token_data = os.environ.get("YOUTUBE_TOKEN")
    if token_data:
        creds_info = json.loads(token_data)
        creds = Credentials.from_authorized_user_info(creds_info)
    else:
        token_file = Path(__file__).parent.parent / "youtube_token.json"
        with open(token_file) as f:
            creds = Credentials.from_authorized_user_info(json.load(f))
    return build("youtube", "v3", credentials=creds)

def find_latest_state():
    output_dir = Path(__file__).parent.parent / "output"
    states = sorted(output_dir.glob("*_state.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for state in states:
        uploaded = state.with_suffix(".uploaded")
        if not uploaded.exists():
            return state
    return None

def upload_video(youtube, state_path):
    with open(state_path) as f:
        state = json.load(f)
    video_path = state["video_path"]
    bp = state.get("blueprint", {})
    title = bp.get("title", "Goosebumps Music")[:100]
    description = bp.get("description", "Engineered using the neuroscience of frisson.")
    tags = bp.get("tags", ["goosebumps", "frisson", "music"])
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
    print(f"Uploaded: https://youtube.com/watch?v={response['id']}")
    state_path.with_suffix(".uploaded").touch()
    return response["id"]

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