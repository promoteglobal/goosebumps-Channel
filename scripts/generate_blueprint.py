"""
generate_blueprint.py - 30+ genres covering world music
"""
import anthropic, json, os, random
from datetime import datetime
from pathlib import Path

GENRES = [
    "Blues","Jazz","Classical","Rock","Folk","Country","Gospel",
    "R&B","Hip-Hop","EDM","Ambient","Cinematic","Indie Pop",
    "Lo-Fi","Metal","Reggae","Neo-Soul",
    "Afrobeat","West African Drumming","South African Jazz",
    "Indian Classical","Bollywood","Flamenco","Celtic",
    "Middle Eastern","Latin","Bossa Nova","Tango",
    "K-Pop","J-Pop","Nordic Folk","Caribbean",
    "Chillwave","Synthwave","Deep House","Drum and Bass",
]

FRISSON_TRIGGERS = [
    "unexpected harmonic shift to a distant chord",
    "sudden dynamic contrast — silence then full orchestra",
    "melodic tension building then resolving to the tonic",
    "tempo entrainment near 65 BPM matching resting heartbeat",
    "unexpected new instrument timbre entering suddenly",
    "emotional climax at the golden ratio point (61.8%) of the track",
    "long sustained note breaking into lush harmony",
    "raw exposed solo voice with no accompaniment",
    "chromatic descending bassline under a rising melody",
    "key change up a half step at emotional peak",
    "call and response between two instruments reaching resolution",
    "sudden drop to near-silence followed by full ensemble",
]

GENRE_FOLDERS = {
    "Blues":"blues","Jazz":"jazz","Classical":"classical",
    "Rock":"rock","Folk":"folk","Country":"country",
    "Gospel":"gospel","R&B":"rnb","Hip-Hop":"hiphop",
    "EDM":"edm","Ambient":"ambient","Cinematic":"cinematic",
    "Indie Pop":"indie","Lo-Fi":"lofi","Metal":"metal",
    "Reggae":"reggae","Neo-Soul":"neosoul","Afrobeat":"afrobeat",
    "West African Drumming":"afrobeat","South African Jazz":"afrobeat",
    "Indian Classical":"indian","Bollywood":"indian",
    "Flamenco":"flamenco","Celtic":"celtic",
    "Middle Eastern":"world","Latin":"latin",
    "Bossa Nova":"latin","Tango":"latin",
    "K-Pop":"kpop","J-Pop":"kpop","Nordic Folk":"folk",
    "Caribbean":"reggae","Chillwave":"ambient",
    "Synthwave":"electronic","Deep House":"electronic",
    "Drum and Bass":"electronic",
}

def generate_blueprint(genre=None, intensity=None):
    genre = genre or random.choice(GENRES)
    intensity = intensity or random.randint(6,10)
    triggers = random.sample(FRISSON_TRIGGERS, k=random.randint(3,5))
    folder = GENRE_FOLDERS.get(genre, "world")
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = f"""You are a music neuroscience expert in musical frisson (goosebumps).
Blueprint a royalty-free {genre} track.
Triggers: {', '.join(triggers)}
Intensity: {intensity}/10
Respond ONLY with valid JSON no markdown:
{{"genre":"{genre}","folder":"{folder}","frisson_score":<int 55-99>,"title":"<6-10 word YouTube title>","description":"<3 paragraph YouTube description>","tags":["<10 YouTube tags>"],"suno_prompt":"<65-80 word Suno prompt no words frisson or goosebumps>","scientific_note":"<1 sentence neuroscience reason this causes chills>"}}"""
    message = client.messages.create(
        model="claude-opus-4-5", max_tokens=1400,
        messages=[{"role":"user","content":prompt}]
    )
    raw = message.content[0].text.strip()
    bp = json.loads(raw)
    bp["intensity"] = intensity
    bp["triggers"] = triggers
    bp["generated_at"] = datetime.utcnow().isoformat()
    return bp

def save_blueprint(bp):
    queue_dir = Path(__file__).parent.parent / "queue"
    queue_dir.mkdir(exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = bp["genre"].lower().replace(" ","_")
    fp = queue_dir / f"{ts}_{slug}.json"
    with open(fp,"w") as f: json.dump(bp,f,indent=2)
    print(f"\nBlueprint: {fp.name}")
    print(f"Genre: {bp['genre']} -> music/{bp.get('folder','world')}/")
    print(f"Title: {bp['title']}")
    print(f"Score: {bp['frisson_score']}%")
    print(f"\n{'='*60}")
    print("SUNO PROMPT:")
    print('='*60)
    print(bp["suno_prompt"])
    print('='*60)
    print(f"\nSave MP3 to: music/{bp.get('folder','world')}/your-track.mp3")
    return fp

def main():
    genre = os.environ.get("GENRE") or None
    intensity = int(os.environ.get("INTENSITY",0)) or None
    bp = generate_blueprint(genre=genre, intensity=intensity)
    save_blueprint(bp)

if __name__ == "__main__":
    main()
