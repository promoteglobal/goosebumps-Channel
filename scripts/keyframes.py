"""
keyframes.py — image->video helper for the consistent-character pipeline.

The AI-video render used to be text-to-video: every clip re-described the
character from scratch, so he changed every shot. We now START FROM A PICTURE:
one locked reference image per recurring asset (in "<Song>.refs/"), and every
per-shot KEYFRAME is generated from that reference (SDXL + IP-Adapter on the
Kaggle GPU) so the SAME character/place appears in every scene. Each keyframe is
then animated by LTX image-to-video.

This module runs on the GitHub Actions runner (no GPU). It:
  * snaps the storyboard's shot boundaries to the song's DOWNBEATS so each clip's
    length matches the music (was: equal division, ignoring the beat), and
  * turns each hand-written shot into a keyframe SPEC = {instruction prompt made
    from the bible's verbatim asset descriptions + the shot's lighting-arc phrase,
    which reference image to condition on, how many frames to animate}.
The specs + the reference-image bytes are baked into the Kaggle kernel.

Consistency levers (why this beats text-to-video):
  1) IP-Adapter conditions each keyframe on the actual reference picture.
  2) The bible's VERBATIM description of each asset is repeated in every prompt.
  3) One reference per keyframe (never fuse two faces — the bible's rule).
"""
import os, re, json, base64
from pathlib import Path

FPS = 24
# LTX loses coherence past ~7s/clip (morphing) — cap each animated clip there.
MAX_CLIP_SECS = float(os.environ.get("AI_MAX_CLIP_SECS", "7.5"))
MIN_SCENE_SECS = float(os.environ.get("AI_MIN_SCENE_SECS", "2.5"))


def refs_dir_for(mp3_path):
    """Locked reference set lives beside the mp3 as '<stem>.refs/'."""
    mp3_path = Path(mp3_path)
    return mp3_path.parent / (mp3_path.stem + ".refs")


def load_reference_b64(mp3_path, max_px=640):
    """Return {asset_name: base64-jpeg} for every image in '<stem>.refs/'.
    Downscaled to <=max_px on the long side so the kernel source stays small
    (IP-Adapter's image encoder only sees ~224px anyway)."""
    d = refs_dir_for(mp3_path)
    out = {}
    if not d.exists():
        print(f"keyframes: no refs dir {d} — image->video disabled, will text-to-video.")
        return out
    try:
        from PIL import Image  # available on the runner (we install pillow)
        import io
        have_pil = True
    except Exception:
        have_pil = False
    for p in sorted(d.glob("*.jpg")) + sorted(d.glob("*.png")):
        try:
            raw = p.read_bytes()
            if have_pil:
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                w, h = im.size
                if max(w, h) > max_px:
                    s = max_px / float(max(w, h))
                    im = im.resize((int(w * s), int(h * s)), Image.LANCZOS)
                buf = io.BytesIO()
                im.save(buf, format="JPEG", quality=88)
                raw = buf.getvalue()
            out[p.stem] = base64.b64encode(raw).decode()
        except Exception as e:
            print(f"keyframes: could not load ref {p.name} ({e})")
    print(f"keyframes: loaded {len(out)} locked references: {', '.join(sorted(out))}")
    return out


# --- music-aligned scene cuts ------------------------------------------------

def _downbeats(mp3_path, dur):
    """Estimate bar downbeats (beat-1 times) via librosa. Empty on failure."""
    try:
        import librosa, numpy as np
        y, sr = librosa.load(str(mp3_path), sr=22050, mono=True)
        _tempo, beats = librosa.beat.beat_track(y=y, sr=sr, trim=False, units="time")
        if len(beats) < 8:
            return []
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        bf = np.clip(librosa.time_to_frames(beats, sr=sr), 0, len(onset_env) - 1)
        bstr = onset_env[bf]
        # Downbeat phase = the beat-of-4 with the strongest average onset.
        phase = max(range(4), key=lambda p: float(bstr[p::4].sum()))
        downs = [float(t) for t in beats[phase::4] if 0.0 <= t < dur]
        return sorted(downs)
    except Exception as e:
        print(f"keyframes: downbeat detection failed ({e}) — equal division fallback.")
        return []


def music_aligned_cuts(mp3_path, dur, n):
    """Return n+1 cut times for n shots. Each internal boundary is snapped to the
    nearest song downbeat (so cuts land on the beat and clip length follows the
    music), kept strictly increasing with a minimum scene length. Falls back to
    equal division if no downbeats are found."""
    n = max(1, int(n))
    if n == 1:
        return [0.0, float(dur)]
    downs = [d for d in _downbeats(mp3_path, dur) if MIN_SCENE_SECS < d < dur - MIN_SCENE_SECS]
    if not downs:
        cuts = [round(dur * i / n, 3) for i in range(n)] + [float(dur)]
        print(f"keyframes: EQUAL division ({n} scenes ~{dur/n:.1f}s) — no downbeats.")
        return cuts

    cuts = [0.0]
    used = set()
    for i in range(1, n):
        target = dur * i / n
        remaining = n - i                       # boundaries still to place after this one
        # snap to the nearest UNUSED downbeat that leaves room for the rest
        cand = sorted(downs, key=lambda d: abs(d - target))
        placed = None
        for d in cand:
            if d in used:
                continue
            if d <= cuts[-1] + MIN_SCENE_SECS:
                continue
            if d >= dur - MIN_SCENE_SECS * remaining:
                continue
            placed = d
            break
        if placed is None:
            placed = min(dur - MIN_SCENE_SECS * remaining, cuts[-1] + max(MIN_SCENE_SECS, target - cuts[-1]))
        used.add(placed)
        cuts.append(round(placed, 3))
    cuts.append(float(dur))
    # guarantee strictly increasing
    for i in range(1, len(cuts)):
        if cuts[i] <= cuts[i - 1]:
            cuts[i] = round(min(dur, cuts[i - 1] + MIN_SCENE_SECS), 3)
    cuts[-1] = float(dur)
    segs = [cuts[i + 1] - cuts[i] for i in range(n)]
    print(f"keyframes: MUSIC-ALIGNED {n} scenes on downbeats "
          f"({min(segs):.1f}-{max(segs):.1f}s, avg {sum(segs)/len(segs):.1f}s).")
    return cuts


def frames_for(secs):
    """LTX needs 8*k+1 frames; cover `secs` (+margin) capped at MAX_CLIP_SECS."""
    secs = min(float(secs), MAX_CLIP_SECS)
    f = int(round((secs + 0.4) * FPS))
    while (f - 1) % 8 != 0:
        f += 1
    return max(25, f)


# --- shot -> asset mapping + prompt -------------------------------------------

# Which bible asset each shot references, matched on the shot text. Order matters:
# the FIRST match becomes the IP-Adapter reference (one identity per keyframe).
ASSET_KEYWORDS = [
    ("climber",      ["young man", "blonde", "blond", "climber", "tracksuit", "ice axe",
                      "his face", "his blue eyes", "his gloved", "his hand", "man's"]),
    ("grandma",      ["mother", "grey-haired", "grey hair", "older woman", "cardigan",
                      "grandmother", "praying", "her eyes", "woman"]),
    ("rescuer",      ["rescuer", "red jacket", "red rescue", "rescue jacket", "rescuers"]),
    ("prayer_light", ["orb", "golden orb", "glowing", "the light", "glow", "spark", "firefly"]),
    ("tv",           ["tv", "television", "news broadcast", "on the news"]),
    ("grandma_house",["living room", "lamplit", "lamp", "armchair", "indoors", "at home", "room"]),
    ("boulder",      ["rock", "boulder"]),
    ("mountain",     ["mountain", "summit", "peak", "ridge", "snowfield", "slope",
                      "avalanche", "snow", "alpine", "aerial"]),
]


# Short secondary-character tags (SDXL truncates at 77 tokens, so we can't paste
# the full bible look for a secondary; IP-Adapter carries the PRIMARY's identity).
SHORT_TAG = {
    "climber":      "the blonde young man in a black ski tracksuit",
    "grandma":      "the grey-haired grandmother in a maroon cardigan",
    "rescuer":      "the bearded mountain rescuer in a red jacket",
    "prayer_light": "the small glowing golden orb of light",
}
SHORT_STYLE = "Pixar-style 3D animated movie still, cinematic, highly detailed"
# Characters with a mouth → force closed (no talking faces over the music).
HUMAN_CHARS = {"climber", "grandma", "rescuer"}


def _bible_look(bible, asset):
    """Verbatim canonical description of an asset from the bible (characters or places)."""
    ch = (bible.get("characters") or {}).get(asset)
    if ch:
        return ch.get("look", "")
    ob = (bible.get("objects_places") or {}).get(asset)
    if ob:
        return ob.get("look", "")
    return ""


def _short_light(phrase):
    """SDXL truncates prompts at ~77 tokens, so the lighting cue must be SHORT and
    sit EARLY in the prompt or the time-of-day gets cut off (v1 bug: random day↔night
    flips). Keep the leading clause (which holds the time keyword) up to ~7 words."""
    p = str(phrase).split(";")[0].replace("—", " ").replace("-", " ")
    p = p.split(",")[0] if len(p.split(",")[0].split()) >= 4 else p
    return " ".join(p.split()[:7]).strip().rstrip(",").lower()


def _lighting_for(bible, i, n):
    """SHORT lighting cue for shot i (0-based) of n, from the bible's arc (keyed by
    shot ranges of the 40-shot storyboard, scaled if n != 40)."""
    arc = bible.get("lighting_time_arc") or {}
    ranges = []
    for k, v in arc.items():
        m = re.match(r"shots?_(\d+)_(\d+)", k)
        if m:
            ranges.append((int(m.group(1)), int(m.group(2)), v))
    if not ranges:
        return ""
    ranges.sort()
    total = max(b for _a, b, _v in ranges)          # usually 40
    shot_no = 1 + round(i * (total - 1) / max(1, n - 1))  # scale to the arc's numbering
    for a, b, v in ranges:
        if a <= shot_no <= b:
            return _short_light(v)
    return _short_light(ranges[-1][2])


def assets_in_shot(shot_text):
    """List of bible asset keys referenced by this shot (first = primary/identity)."""
    t = shot_text.lower()
    found = []
    for asset, kws in ASSET_KEYWORDS:
        if any(kw in t for kw in kws):
            found.append(asset)
    return found


def build_shot_specs(story, bible, cuts, available_refs):
    """One spec per shot: {instr, ref (primary asset name or None), extra_looks, frames}.
    `available_refs` = set of asset names we actually have a reference image for."""
    characters = set((bible.get("characters") or {}).keys())
    shots = story["shots"]
    n = len(shots)
    specs = []
    for i, shot in enumerate(shots):
        shot = str(shot).strip().rstrip(".")
        found = assets_in_shot(shot)
        # primary identity ref = first found asset we have an image for (characters
        # rank before places in ASSET_KEYWORDS, so a person wins over scenery).
        primary = next((a for a in found if a in available_refs), None)
        # BURIED shots: condition on the dedicated buried-face reference, not the
        # standing full-body one (IP-Adapter copies the reference COMPOSITION, so a
        # standing ref forces a standing figure — v2 probe showed him standing next
        # to a snow mound instead of buried). Keeps the buried STATE consistent.
        sl = shot.lower()
        if ("buried" in sl or "under the snow" in sl) and "climber_buried" in available_refs:
            primary = "climber_buried"
        # SDXL truncates at 77 tokens, so the prompt must be SHORT and put the SCENE
        # FIRST (so the action/setting survives). IP-Adapter carries the PRIMARY's
        # identity from its picture, so we don't repeat the primary's verbatim look;
        # a SECONDARY character gets only a short tag (it isn't in the reference).
        sec = []
        if primary in characters:
            for a in found:
                if a != primary and a in characters and a in SHORT_TAG:
                    sec.append(SHORT_TAG[a])
        light = _lighting_for(bible, i, n)
        # Order matters (SDXL truncates at ~77 tokens): scene, then the SHORT lighting
        # cue (so time-of-day survives — fixes v1 day/night flips), then mouth-closed
        # for people (no talking faces), secondaries, style.
        parts = [shot]
        if light:
            parts.append(light)
        if primary in HUMAN_CHARS:
            parts.append("mouth closed, calm still expression, not talking")
        parts += sec + [SHORT_STYLE, "no text, no watermark"]
        instr = ". ".join(p.strip().rstrip(".") for p in parts if p and p.strip()) + "."
        seg = cuts[i + 1] - cuts[i]
        specs.append({"instr": instr, "ref": primary, "assets": found,
                      "frames": frames_for(seg), "secs": round(seg, 2)})
    covered = sum(1 for s in specs if s["ref"])
    print(f"keyframes: {n} shot specs built — {covered}/{n} conditioned on a locked "
          f"reference image (rest are text-only scenery).")
    return specs
