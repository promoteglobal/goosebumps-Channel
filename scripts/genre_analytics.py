"""
genre_analytics.py - Rank the channel's genres by viewership and email a daily
"post this genre today" reminder.

Reads the channel's own uploads via the YouTube Data API (YOUTUBE_TOKEN), maps
each video to its genre (from the tags create_video.py sets), ranks genres by
AVERAGE views per video (the signal: lean into what's performing), and emails
the top genre as today's pick plus a short leaderboard.

This never posts or changes anything — it only reads stats and sends one email.

Env:
  YOUTUBE_TOKEN       OAuth creds JSON (same secret the rest of the pipeline uses)
  GMAIL_ADDRESS       sender Gmail         (default: promoteglobal@gmail.com)
  GMAIL_APP_PASSWORD  Gmail 16-char app password (REQUIRED to actually send)
  EMAIL_TO            recipient            (default: GMAIL_ADDRESS)
  GENERATOR_URL       link put in the email (default: the GitHub Pages site)
Flags:
  --dry-run           print the report to the terminal, do NOT send the email
"""
import os, sys, json, smtplib, ssl
from collections import defaultdict
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).parent.parent
MUSIC = ROOT / "music"

# Show times in the user's timezone (override with POST_TZ / POST_TZ_LABEL).
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo(os.environ.get("POST_TZ", "America/New_York"))
except Exception:
    TZ = None
TZ_LABEL = os.environ.get("POST_TZ_LABEL", "ET")

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]
DAYPARTS = [("morning (~6-11am)", 6, 12), ("afternoon (~12-5pm)", 12, 18),
            ("evening (~6-11pm)", 18, 24), ("late night (~12-5am)", 0, 6)]

GENERATOR_URL = os.environ.get(
    "GENERATOR_URL", "https://promoteglobal.github.io/goosebumps-Channel/")

# Canonical genres (display names) exactly as the generator offers them. Used to
# give the email a clean "generate THIS" instruction and to bucket videos.
GENRES = [
    "Blues", "Jazz", "K-Pop", "Classical", "Hip-Hop", "Ambient", "Rock", "EDM",
    "R&B", "Gospel", "Cinematic", "Folk", "Lo-Fi", "Afrobeat", "Latin", "Celtic",
    "Indian Classical", "Flamenco", "Reggae", "Neo-Soul", "Country", "Metal",
    "Bossa Nova", "Synthwave", "Middle Eastern", "Nordic Folk", "Bollywood",
    "Deep House", "Tango", "J-Pop", "Electronic", "World", "Dangdut Koplo",
    "Bluegrass",
]


def norm(s):
    """Loose key: lowercase, letters+digits only. 'K-Pop' -> 'kpop'."""
    return "".join(c for c in (s or "").lower() if c.isalnum())


# normalized tag/word -> canonical display name
GENRE_BY_KEY = {norm(g): g for g in GENRES}


def log(msg):
    sys.stderr.write(msg + "\n")


def youtube_client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_info(json.loads(os.environ["YOUTUBE_TOKEN"]))
    return build("youtube", "v3", credentials=creds)


def genre_of(video):
    """Best-effort genre for one video: first a matching tag, else scan the
    title for a known genre. Returns a canonical display name or None."""
    for tag in (video.get("snippet", {}).get("tags") or []):
        g = GENRE_BY_KEY.get(norm(tag))
        if g:
            return g
    title = video.get("snippet", {}).get("title", "")
    tkey = norm(title)
    # Longest genre key first so 'indianclassical' wins over 'classical'.
    for key in sorted(GENRE_BY_KEY, key=len, reverse=True):
        if key and key in tkey:
            return GENRE_BY_KEY[key]
    return None


def collect_videos(yt):
    """Every uploaded video with its stats. Returns a list of dicts."""
    ch = yt.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, page = [], None
    while True:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                    maxResults=50, pageToken=page).execute()
        ids += [it["contentDetails"]["videoId"] for it in r.get("items", [])]
        page = r.get("nextPageToken")
        if not page:
            break
    videos = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics",
                             id=",".join(ids[i:i + 50])).execute()
        videos += r.get("items", [])
    return videos


def rank_genres(videos):
    """Aggregate per genre. Returns a sorted list of row dicts (best first)."""
    agg = defaultdict(lambda: {"n": 0, "views": 0, "likes": 0, "comments": 0})
    unknown = 0
    for v in videos:
        g = genre_of(v)
        if not g:
            unknown += 1
            continue
        s = v.get("statistics", {})
        a = agg[g]
        a["n"] += 1
        a["views"]    += int(s.get("viewCount", 0) or 0)
        a["likes"]    += int(s.get("likeCount", 0) or 0)
        a["comments"] += int(s.get("commentCount", 0) or 0)
    rows = []
    for g, a in agg.items():
        rows.append({
            "genre": g, "videos": a["n"], "views": a["views"],
            "avg_views": a["views"] / a["n"] if a["n"] else 0,
            "likes": a["likes"], "comments": a["comments"],
        })
    # Lean into what performs: rank by average views/video, then total views.
    rows.sort(key=lambda r: (r["avg_views"], r["views"]), reverse=True)
    return rows, unknown


def best_post_time(videos):
    """Recommend a day + time window from WHEN the channel's highest-viewed
    uploads were published (correlation, not a guarantee). Falls back to general
    guidance until there's enough data."""
    pts = []
    for v in videos:
        pub = v.get("snippet", {}).get("publishedAt")
        views = int(v.get("statistics", {}).get("viewCount", 0) or 0)
        if not pub:
            continue
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            if TZ:
                dt = dt.astimezone(TZ)
        except Exception:
            continue
        pts.append((dt.weekday(), dt.hour, views))
    if len(pts) < 6:
        return (f"Best time to post (general guidance until more data): weekday "
                f"afternoons ~2-4pm {TZ_LABEL}, or Sat/Sun mornings ~9-11am "
                f"{TZ_LABEL}. Need ~6+ videos for a personalized pick (have {len(pts)}).")
    day = defaultdict(lambda: [0, 0])
    win = defaultdict(lambda: [0, 0])
    for wd, hr, views in pts:
        day[wd][0] += views; day[wd][1] += 1
        for name, lo, hi in DAYPARTS:
            if lo <= hr < hi:
                win[name][0] += views; win[name][1] += 1
                break
    best_day = max(day.items(), key=lambda kv: kv[1][0] / kv[1][1])[0]
    best_win = max(win.items(), key=lambda kv: kv[1][0] / kv[1][1])[0]
    return (f"Best time to post (from your own uploads): {WEEKDAYS[best_day]} "
            f"{best_win} {TZ_LABEL} - that's when your highest-viewed videos cluster.")


def experiment_report(videos):
    """The 'scientific experiment': correlate each video's VIEWS with the frisson
    triggers + intensity used to make it (recorded in the song's .json in the
    repo), and recommend the best-performing intensity and triggers. Needs a few
    tagged posts before it can recommend (older posts have no triggers recorded)."""
    bps = {}
    for jp in MUSIC.rglob("*.json"):
        if jp.name == "blueprint.json":
            continue
        try:
            bp = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        bps[norm(bp.get("final_title") or jp.stem)] = {
            "triggers": bp.get("triggers") or [],
            "intensity": str(bp.get("intensity") or "").strip(),
        }
    by_int = defaultdict(lambda: [0, 0])    # intensity -> [views, n]
    by_trig = defaultdict(lambda: [0, 0])   # trigger   -> [views, n]
    matched = 0
    for v in videos:
        bp = bps.get(norm(v.get("snippet", {}).get("title", "")))
        if not bp:
            continue
        views = int(v.get("statistics", {}).get("viewCount", 0) or 0)
        if bp["intensity"]:
            by_int[bp["intensity"]][0] += views
            by_int[bp["intensity"]][1] += 1
            matched += 1
        for tg in bp["triggers"]:
            by_trig[tg][0] += views
            by_trig[tg][1] += 1
    if matched < 4:
        return ("Trigger/intensity experiment: collecting data "
                f"({matched} tagged post(s) so far). Once ~4+ posts carry their "
                "triggers + intensity, the best-performing settings will appear here.")
    bi = max(by_int.items(), key=lambda kv: kv[1][0] / kv[1][1])
    tt = sorted(by_trig.items(), key=lambda kv: kv[1][0] / kv[1][1], reverse=True)
    out = [f"Recommended intensity: {bi[0]}/10 "
           f"({bi[1][0] / bi[1][1]:.0f} avg views per post)."]
    if tt:
        out.append("Best-performing triggers so far: "
                   + ", ".join(t for t, _ in tt[:3]) + ".")
    return "\n".join(out)


def buffer_status(videos):
    """How many BUFFERED songs are still waiting to be posted (not yet on
    YouTube). Drives the monthly 'refill the buffer' reminder."""
    posted = {norm(v.get("snippet", {}).get("title", "")) for v in videos}
    left = 0
    for jp in MUSIC.rglob("*.json"):
        if jp.name == "blueprint.json":
            continue
        try:
            bp = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        if not bp.get("buffered"):
            continue
        if norm(bp.get("final_title") or jp.stem) not in posted:
            left += 1
    return left


def build_email(rows, unknown, total_videos, best_time, experiment, buffer_left):
    if not rows:
        winner = "Blues"
        headline = ("No genre stats yet (no matching videos found). Post anything "
                    "to start building data — try Blues.")
        board = ""
    else:
        winner = rows[0]["genre"]
        headline = (f"Today's pick: {winner.upper()} - your best-performing genre "
                    f"so far ({rows[0]['avg_views']:.0f} avg views/video across "
                    f"{rows[0]['videos']} video(s)).")
        lines = ["Genre leaderboard (by avg views/video):", ""]
        for i, r in enumerate(rows[:8], 1):
            lines.append(
                f"{i}. {r['genre']:<16} {r['avg_views']:>7.0f} avg  "
                f"{r['views']:>7} total  {r['videos']:>2} vids  "
                f"{r['likes']} likes  {r['comments']} comments")
        board = "\n".join(lines)

    if buffer_left == 0:
        buf = ("BUFFER EMPTY - no songs queued to post. Batch-download a new set "
               "now (Buffer mode ON) or posting stops.")
    elif buffer_left <= 5:
        buf = (f"** REFILL TIME ** only {buffer_left} buffered song(s) left (~{buffer_left} "
               "days of posts). Batch-download ~25 more this cycle (Buffer mode ON) "
               "to cover next month.")
    else:
        buf = f"Buffer: {buffer_left} songs queued (~{buffer_left} days of auto-posts left)."
    body = f"""{headline}

{buf}

{best_time}

{experiment}

To post it: open the generator, pick {winner}, hit Generate Frisson Blueprint,
then let it run through Suno - it auto-posts to YouTube.

  {GENERATOR_URL}

{board}

({total_videos} videos scanned{', ' + str(unknown) + ' had no genre tag' if unknown else ''}.)
Ranked by lifetime average views per video.
- Goosebumps genre bot
"""
    subject = f"Goosebumps: post {winner} today"
    return subject, body, winner


def send_email(subject, body):
    # `or` (not get-default): unset secrets arrive as "" from the workflow, and
    # an empty string must still fall back to the real address / sender.
    sender = os.environ.get("GMAIL_ADDRESS") or "promoteglobal@gmail.com"
    to     = os.environ.get("EMAIL_TO") or sender
    pw     = (os.environ.get("GMAIL_APP_PASSWORD") or "").replace(" ", "")
    if not pw:
        log("No GMAIL_APP_PASSWORD set - cannot send. (Set it as a repo secret.)")
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)
    ctx = ssl.create_default_context()
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls(context=ctx)
        s.login(sender, pw)
        s.send_message(msg)
    log(f"Email sent to {to}.")
    return True


def main():
    dry = "--dry-run" in sys.argv
    try:
        yt = youtube_client()
        videos = collect_videos(yt)
    except Exception as e:
        log(f"YouTube read failed ({e}); nothing to send.")
        return
    rows, unknown = rank_genres(videos)
    best_time = best_post_time(videos)
    experiment = experiment_report(videos)
    buffer_left = buffer_status(videos)
    subject, body, winner = build_email(rows, unknown, len(videos), best_time, experiment, buffer_left)
    log("=" * 60)
    log(subject)
    log(body)
    log("=" * 60)
    if dry:
        log("DRY RUN - email not sent.")
        return
    try:
        send_email(subject, body)
    except Exception as e:
        log(f"Email send failed ({e}).")


if __name__ == "__main__":
    main()
