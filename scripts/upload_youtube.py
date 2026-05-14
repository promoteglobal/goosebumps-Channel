import os, json, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Genre folder → YouTube Playlist ID
PLAYLISTS = {
    "kpop":          "PL7e9dvJK1b-DOnkI7q6K-T0AIrzsUiQn6",
    "flamenco":      "PL7e9dvJK1b-CM9HbVWkO1IGYX_YlLCN3d",
    "bollywood":     "PL7e9dvJK1b-Ahmufy9mm6YlXFwpSMMM4N",
    "blues":         "PL7e9dvJK1b-Cc_LtNRXGSi5x4s8ghGluJ",
    "ambient":       "PL7e9dvJK1b-Bvnb770Ne0CYfsMLtxrtq-",
    "afrobeat":      "PL7e9dvJK1b-BUWXtjYbaPkYksWK8j1cVl",
    "cinematic":     "PL7e9dvJK1b-AZNF-cFvG1I4U0Ax79e7a4",
    "synthwave":     "PL7e9dvJK1b-BUErfB-VjBJcipnshdrQPG",
    "world":         "PL7e9dvJK1b-CXD6yC1RPDnV2zOy9kdIHo",
    "tango":         "PL7e9dvJK1b-AxqPtnCb1XNOjwCRFSEHPx",
    "rock":          "PL7e9dvJK1b-DwFGqvE81PMqRDb_05f0hi",
    "rnb":           "PL7e9dvJK1b-DNO1bFVwdBNguwWtkP_Vnm",
    "reggae":        "PL7e9dvJK1b-DAIenfF6X2KfW6kZbdSajG",
    "nordicfolk":    "PL7e9dvJK1b-D0gDQgK4ypZvsOl_9vYTZC",
    "neosoul":       "PL7e9dvJK1b-D-tba90c0A7_50LYcvdIek",
    "middleeastern": "PL7e9dvJK1b-AMvg-YDVqx077cWed_-WzK",
    "metal":         "PL7e9dvJK1b-AnE_KyTZMlDsAkxtnYmbJl",
    "lofi":          "PL7e9dvJK1b-BQBovkw_y420f7Nzi028Dc",
    "latin":         "PL7e9dvJK1b-DjLzqTFrA_El_5GNlo3m3O",
    "jpop":          "PL7e9dvJK1b-D-k4gmY48G34sIcFyb8HfU",
    "jazz":          "PL7e9dvJK1b-C5-YX6srTbT8dvL3Q9vPRs",
    "indianclassical":"PL7e9dvJK1b-BUD-rNdHb44vnqq7bgWNIl",
    "hiphop":        "PL7e9dvJK1b-CdF8P0hpR-LI6iqH-Kx5Mp",
    "gospel":        "PL7e9dvJK1b-D0n2sC-eEWCpNMAW2fE_Te",
    "folk":          "PL7e9dvJK1b-CQ3OXui9eVKqZnWID0X8H1",
    "electronic":    "PL7e9dvJK1b-CwTyBtyzWPJB4GJaHzbZno",
    "edm":           "PL7e9dvJK1b-ApOkTck8Q8FWh_GcoCZcgB",
    "deephouse":     "PL7e9dvJK1b-Amk5aqu5oV2zDvr38WVzTO",
    "classical":     "PL7e9dvJK1b-BvSDoHTeJbsFTNeMBAv-XS",
    "country":       "PL7e9dvJK1b-A1Tf__S_BOduCcQsgTrq5s",
    "celtic":        "PL7e9dvJK1b-C_S0ViL6uS_S9p_JUKz7TK",
    "bossanova":     "PL7e9dvJK1b-C4oc6qBCFEiE_q9enMBoqT",
    "dangdut":       "PL7e9dvJK1b-BRpXwXpAu4AcnDKRgh4N5F",
    "bluegrass":     "id will go here"
}

# Native language taglines per genre for YouTube geo-targeting
NATIVE_TAGLINES = {
    "kpop":          "🇰🇷 이 음악은 소름을 유발하도록 과학적으로 설계되었습니다. 구독하고 전율을 경험하세요.",
    "jpop":          "🇯🇵 この音楽は鳥肌を立てるように科学的に設計されています。チャンネル登録してください。",
    "bollywood":     "🇮🇳 यह संगीत रोमांच पैदा करने के लिए वैज्ञानिक रूप से तैयार किया गया है। सब्सक्राइब करें।",
    "indianclassical":"🇮🇳 यह संगीत रोमांच पैदा करने के लिए वैज्ञानिक रूप से तैयार किया गया है। सब्सक्राइब करें।",
    "flamenco":      "🇪🇸 Esta música está científicamente diseñada para provocar escalofríos. Suscríbete.",
    "latin":         "🇲🇽 Esta música está científicamente diseñada para provocar escalofríos. Suscríbete.",
    "tango":         "🇦🇷 Esta música está científicamente diseñada para provocar escalofríos. Suscríbete.",
    "bossanova":     "🇧🇷 Esta música foi cientificamente projetada para provocar arrepios. Inscreva-se.",
    "afrobeat":      "🌍 Orin yii jẹ apẹrẹ imọ-jinlẹ lati fa iwariri. Subscribe ki o ni iriri.",
    "reggae":        "🇯🇲 Dis music scientifically engineer fi give yuh di chills. Subscribe and feel di vibes, bredren.",
    "celtic":        "🇮🇪 Tá an ceol seo deartha go heolaíoch chun creatha a spreagadh. Sínigh suas.",
    "nordicfolk":    "🇸🇪 Denna musik är vetenskapligt utformad för att ge dig gåshud. Prenumerera.",
    "middleeastern": "🌙 هذه الموسيقى مصممة علمياً لإثارة القشعريرة. اشترك وجرب التجربة.",
    "classical":     "🎻 Diese Musik ist wissenschaftlich entwickelt, um Gänsehaut zu erzeugen. Abonnieren.",
    "dangdut":       "🇮🇩 Musik ini dirancang secara ilmiah untuk memberi Anda merinding. Subscribe dan rasakan getarannya!",
    "jazz":          "🎺 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "blues":         "🎸 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "gospel":        "🙏 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "hiphop":        "🎤 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "rock":          "⚡ This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "metal":         "🔥 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "ambient":       "🌊 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "lofi":          "☕ This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "edm":           "💫 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "deephouse":     "🎧 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "synthwave":     "🌈 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "rnb":           "❤️ This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "neosoul":       "🌟 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "country":       "🤠 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "folk":          "🪕 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "electronic":    "💡 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "cinematic":     "🎬 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "world":         "🌍 This music is scientifically engineered to give you chills. Subscribe and feel it.",
    "bluegrass":     "🪕 This track was scientifically designed to give you goosebumps. Subscribe and feel the chill!",
}

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
    states = sorted(output_dir.glob("*_state.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for state in states:
        uploaded = Path(str(state).replace("_state.json", "_state.uploaded"))
        if not uploaded.exists():
            return state
    return None

def get_native_tagline(genre_folder):
    key = genre_folder.lower().replace(" ", "").replace("-", "")
    if key in NATIVE_TAGLINES:
        return NATIVE_TAGLINES[key]
    for k in NATIVE_TAGLINES:
        if len(key) >= 4 and key[:4] == k[:4]:
            return NATIVE_TAGLINES[k]
    return "🎵 This music is scientifically engineered to give you chills. Subscribe and feel it."

def build_description(bp, mp3_path=""):
    genre    = bp.get("genre", "Music")
    title    = bp.get("title", "").replace(" - Goosebumps Music", "").strip()
    score    = bp.get("frisson_score", "")
    analysis = bp.get("scientific_analysis", "")
    structure= bp.get("structure", "")

    genre_folder = Path(mp3_path).parent.name if mp3_path else genre.lower()
    native = get_native_tagline(genre_folder)

    desc  = f"{title} is scientifically engineered to give you chills and trigger a natural dopamine release.\n\n"
    if score:
        desc += f"🥶 Frisson Score: {score}% — neuroscience-based goosebump prediction\n\n"
    desc += f"{native}\n\n"
    desc += "━" * 30 + "\n"
    desc += "🧠 THE SCIENCE OF GOOSEBUMPS\n\n"
    desc += "Musical frisson — the chills you feel from music — triggers real dopamine release "
    desc += "in the brain's pleasure center (nucleus accumbens). Research shows this can:\n\n"
    desc += "✅ Elevate mood and reduce symptoms of mild depression\n"
    desc += "✅ Lower cortisol (stress hormone) levels\n"
    desc += "✅ Support emotional processing and release\n"
    desc += "✅ Provide mild natural pain relief\n"
    desc += "✅ Strengthen feelings of connection and empathy\n\n"
    if analysis:
        desc += f"🔬 Track Analysis: {analysis}\n\n"
    if structure:
        desc += f"🎵 Music Structure: {structure}\n\n"
    desc += "━" * 30 + "\n"
    desc += f"Genre: {genre}\n\n"
    desc += "All music on this channel is 100% original and exclusively owned by "
    desc += "Feel the Music – Goosebumps Challenge. All rights reserved.\n\n"
    desc += f"#Goosebumps #FrissonMusic #{genre.replace(' ','')} #OriginalMusic "
    desc += "#AIGeneratedMusic #CopyrightProtected #DopamineMusic #StressRelief "
    desc += "#MoodBoost #MentalWellness #MusicScience"
    return desc

def get_playlist_id(bp, mp3_path):
    genre_key = None
    if mp3_path:
        try:
            folder = Path(mp3_path).parent.name.lower()
            if folder in PLAYLISTS:
                genre_key = folder
        except:
            pass
    if not genre_key:
        genre = bp.get("genre", "").lower().replace(" ", "").replace("-", "")
        for k in PLAYLISTS:
            if genre == k or (len(genre) >= 4 and genre[:4] == k[:4]):
                genre_key = k
                break
    if genre_key and genre_key in PLAYLISTS:
        print(f"Playlist: {genre_key} → {PLAYLISTS[genre_key]}")
        return PLAYLISTS[genre_key]
    print(f"No playlist found for genre: {bp.get('genre','')}")
    return None

def add_to_playlist(youtube, video_id, playlist_id):
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body={"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        ).execute()
        print(f"Added to playlist: {playlist_id}")
    except Exception as e:
        print(f"Playlist add failed: {e}")

def upload_video(youtube, state_path):
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    video_path = state["video_path"]
    mp3_path   = state.get("mp3_path", "")
    bp         = state.get("blueprint", {})

    raw_title = bp.get("title", "")
    if raw_title:
        raw_title = raw_title.replace(" - Goosebumps Music", "").strip()
        title = f"{raw_title} - Goosebumps Music"
    else:
        title = f"{Path(video_path).stem} - Goosebumps Music"
    title = title[:100]

    description = build_description(bp, mp3_path)
    genre = bp.get("genre", "music").lower().replace(" ", "")
    tags = bp.get("tags", []) or [
        "goosebumps", "frisson", "music", genre,
        "original music", "AI generated music", "chills",
        "dopamine music", "stress relief", "mood boost",
        "mental wellness", "music science", "emotional music"
    ]

    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": "10"},
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

    playlist_id = get_playlist_id(bp, mp3_path)
    if playlist_id:
        add_to_playlist(youtube, video_id, playlist_id)

    uploaded_path = Path(str(state_path).replace("_state.json", "_state.uploaded"))
    uploaded_path.touch()
    return video_id

def main():
    if "--auth" in sys.argv:
        from google_auth_oauthlib.flow import InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(
            "client_secrets.json",
            scopes=["https://www.googleapis.com/auth/youtube"]
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