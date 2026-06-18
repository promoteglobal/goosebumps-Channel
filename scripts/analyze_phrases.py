"""
analyze_phrases.py - Deep music structure analysis with the All-In-One Music
Structure Analyzer (allin1). Detects functional SECTIONS (intro/verse/chorus/
drop/outro) + beats + DOWNBEATS, written to JSON for create_video.py to place
scene cuts on real musical section changes (snapped to downbeats).

Runs in its OWN venv (torch/natten/demucs + madmom). Safe to fail: if anything
errors, create_video.py falls back to librosa.
"""
import sys, json


def main():
    if len(sys.argv) < 2:
        print("usage: analyze_phrases.py <audio> [out.json]")
        return 1
    audio = sys.argv[1]
    out   = sys.argv[2] if len(sys.argv) > 2 else "phrases.json"

    import allin1
    res = allin1.analyze(audio, device="cpu")
    if isinstance(res, list):
        res = res[0]

    downbeats = [round(float(t), 4) for t in (getattr(res, "downbeats", None) or [])]
    beats     = [round(float(t), 4) for t in (getattr(res, "beats", None) or [])]

    segments = []
    for s in (getattr(res, "segments", None) or []):
        segments.append({
            "start": round(float(s.start), 4),
            "end":   round(float(s.end), 4),
            "label": getattr(s, "label", ""),
        })

    with open(out, "w") as f:
        json.dump({"downbeats": downbeats, "beats": beats, "segments": segments}, f)
    print(f"allin1: {len(beats)} beats, {len(downbeats)} downbeats, "
          f"{len(segments)} sections -> {out}")
    if segments:
        print("sections: " + ", ".join(
            f"{s['label']}@{s['start']:.0f}s" for s in segments))
    return 0


if __name__ == "__main__":
    sys.exit(main())
