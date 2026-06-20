"""
pick_next_song.py - Choose the next song for the daily auto-poster.

Picks a song from the GitHub catalog (music/<genre>/<Song>.mp3) that:
  1. has a PAIRED description file (music/<genre>/<Song>.json) so the description
     matches the song exactly,
  2. is NOT already on YouTube (YouTube is the source of truth — survives any
     local deletions), and
  3. isn't a Suno duplicate (same base name) of one already chosen.

Prints the chosen relative path like "reggae/Blue Horn Prayer.mp3" on stdout
(or nothing, so the workflow skips posting). Diagnostics go to stderr.
"""
import os, sys, json, re, random
from pathlib import Path

ROOT  = Path(__file__).parent.parent
MUSIC = ROOT / "music"


def log(msg):
    sys.stderr.write(msg + "\n")


def norm(s):
    """Normalize a song name / video title for matching."""
    s = s.lower()
    s = s.split(" - goosebumps")[0]      # drop the "- Goosebumps Music" suffix
    s = re.sub(r"\(\s*\d+\s*\)", "", s)   # drop " (1)" duplicate markers
    s = re.sub(r"[^\w]+", "", s)          # keep letters of all scripts (Korean, etc.)
    return s


def youtube_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    token = os.environ.get("YOUTUBE_TOKEN")
    if token:
        creds = Credentials.from_authorized_user_info(json.loads(token))
    else:
        with open(ROOT / "youtube_token.json") as f:
            creds = Credentials.from_authorized_user_info(json.load(f))
    return build("youtube", "v3", credentials=creds)


def uploaded_song_names(yt):
    """Normalized names of every video already on the channel."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    names, page = set(), None
    while True:
        r = yt.playlistItems().list(part="snippet", playlistId=uploads,
                                    maxResults=50, pageToken=page).execute()
        for it in r.get("items", []):
            names.add(norm(it["snippet"]["title"]))
        page = r.get("nextPageToken")
        if not page:
            break
    return names


def main():
    try:
        posted = uploaded_song_names(youtube_client())
        log(f"YouTube: {len(posted)} videos already uploaded.")
    except Exception as e:
        log(f"YouTube lookup failed ({e}); skipping auto-post for safety.")
        return  # print nothing -> workflow skips

    by_genre, seen = {}, set()
    paired = no_pair = already = 0
    for mp3 in sorted(MUSIC.rglob("*.mp3")):
        if not mp3.with_suffix(".json").exists():
            no_pair += 1
            continue                       # need the paired description
        paired += 1
        n = norm(mp3.stem)
        if n in posted:
            already += 1
            continue                       # already on YouTube
        if n in seen:
            continue                       # Suno duplicate of one chosen
        seen.add(n)
        by_genre.setdefault(mp3.parent.name, []).append(mp3)

    log(f"Catalog: {paired} paired, {no_pair} without a description, "
        f"{already} already posted, "
        f"{sum(len(v) for v in by_genre.values())} eligible to post.")

    if not by_genre:
        log("Nothing eligible to post today.")
        return

    # Variety: prefer genres with the fewest eligible (spread coverage), then
    # random within the chosen genre.
    genre = random.choice(list(by_genre.keys()))
    mp3   = random.choice(by_genre[genre])
    rel   = f"{mp3.parent.name}/{mp3.name}"
    log(f"Chosen: {rel}")
    print(rel)


if __name__ == "__main__":
    main()
