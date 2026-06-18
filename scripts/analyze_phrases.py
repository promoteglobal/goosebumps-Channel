"""
analyze_phrases.py - Precise beat + DOWNBEAT detection with madmom.

Writes {"downbeats": [...], "beats": [...]} to JSON; create_video.py groups the
downbeats into 4/8-bar phrases and cuts scenes on those phrase boundaries.

madmom's DBN downbeat tracker handles complex/odd meters (tabla, Afrobeat, etc.),
which is why it beats a simple onset-phase guess. Runs in its OWN venv (older
numpy) and is safe to fail: if anything errors, create_video.py falls back to
librosa.
"""
import sys, json


def main():
    if len(sys.argv) < 2:
        print("usage: analyze_phrases.py <audio> [out.json]")
        return 1
    audio = sys.argv[1]
    out   = sys.argv[2] if len(sys.argv) > 2 else "phrases.json"

    from madmom.features.downbeats import (
        RNNDownBeatProcessor, DBNDownBeatTrackingProcessor)

    # RNN gives per-frame beat/downbeat activations; the DBN decodes them into
    # (time, position_in_bar). position_in_bar == 1 marks a bar's downbeat.
    # beats_per_bar covers common meters; madmom picks the best fit.
    act   = RNNDownBeatProcessor()(audio)
    proc  = DBNDownBeatTrackingProcessor(beats_per_bar=[2, 3, 4, 5, 6, 7], fps=100)
    beats = proc(act)

    downbeats = [round(float(t), 4) for t, b in beats if int(b) == 1]
    allbeats  = [round(float(t), 4) for t, b in beats]

    with open(out, "w") as f:
        json.dump({"downbeats": downbeats, "beats": allbeats}, f)
    print(f"madmom: {len(allbeats)} beats, {len(downbeats)} downbeats -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
