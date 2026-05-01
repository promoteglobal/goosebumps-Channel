"""
generate_blueprint.py
Generates a frisson music blueprint using Claude API.
Saves the blueprint + Suno prompt to the /queue folder.
Run this on a schedule via GitHub Actions.
"""

import anthropic
import json
import os
import random
from datetime import datetime
from pathlib import Path

GENRES = [
    "Blues", "Jazz", "K-Pop", "Classical", "Hip-Hop",
    "Ambient", "Rock", "R&B", "Folk", "Gospel",
    "Cinematic", "Neo-Soul", "Indie Pop", "Lo-Fi", "Reggae"
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
    "key change up a half step at emotional peak"
]

def generate_blueprint(genre: str = None, intensity: int = None) -> dict:
    """Generate a frisson music blueprint for a given genre."""

    genre = genre or random.choice(GENRES)
    intensity = intensity or random.randint(6, 10)
    triggers = random.sample(FRISSON_TRIGGERS, k=random.randint(3, 5))

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    prompt = f"""You are a music neuroscience expert specializing in musical frisson (goosebumps/chills).
Create a complete frisson music blueprint for a royalty-free {genre} track.

Active frisson triggers: {', '.join(triggers)}
Intensity level: {intensity}/10

Respond ONLY with valid JSON, no markdown, no backticks:
{{
  "genre": "{genre}",
  "frisson_score": <integer 55-99 based on trigger count and intensity>,
  "title": "<evocative YouTube video title, 6-10 words, no clickbait>",
  "description": "<YouTube description, 3 paragraphs: 1) what the track does emotionally, 2) the science of why it causes goosebumps, 3) subscribe call-to-action for the Goosebumps channel>",
  "tags": ["<10 relevant YouTube tags as array>"],
  "suno_prompt": "<60-80 word music generation prompt for Suno — encode all frisson triggers as natural musical description, specify genre, instruments, BPM, key, emotional arc and peak moment — never use the words frisson or goosebumps>",
  "scientific_note": "<1 sentence for the video — the neuroscience reason this track triggers chills, cite dopamine or Panksepp>"
}}"""

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()
    blueprint = json.loads(raw)
    blueprint["intensity"] = intensity
    blueprint["triggers"] = triggers
    blueprint["generated_at"] = datetime.utcnow().isoformat()

    return blueprint


def save_blueprint(blueprint: dict) -> Path:
    """Save blueprint to queue folder."""
    queue_dir = Path(__file__).parent.parent / "queue"
    queue_dir.mkdir(exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    genre_slug = blueprint["genre"].lower().replace(" ", "_").replace("-", "_")
    filename = f"{timestamp}_{genre_slug}.json"
    filepath = queue_dir / filename

    with open(filepath, "w") as f:
        json.dump(blueprint, f, indent=2)

    print(f"Blueprint saved: {filepath}")
    print(f"\nGenre: {blueprint['genre']}")
    print(f"Title: {blueprint['title']}")
    print(f"Frisson score: {blueprint['frisson_score']}%")
    print(f"\n{'='*60}")
    print("SUNO PROMPT — paste this into suno.com:")
    print('='*60)
    print(blueprint["suno_prompt"])
    print('='*60)

    return filepath


def main():
    # Can override via env vars for manual runs
    genre = os.environ.get("GENRE", None)
    intensity = int(os.environ.get("INTENSITY", 0)) or None

    blueprint = generate_blueprint(genre=genre, intensity=intensity)
    save_blueprint(blueprint)


if __name__ == "__main__":
    main()
