"""
kaggle_collect.py — the COLLECTOR half of the decoupled AI-video pipeline.

kaggle_render.py (kickoff mode) pushes a render to Kaggle and exits immediately.
Kaggle then renders for hours ON ITS OWN (well under its ~9h session limit). This
collector runs on a short schedule (cron). Each tick it:
  1. checks the render kernel's status — if still running, does nothing;
  2. when finished, downloads the clips + meta.json + cuts.json from the kernel
     output, and (if this render_id hasn't been posted yet) signals the workflow
     to build + upload the video.

Idempotent: the posted render_id is recorded in output/ai_last_posted.txt, so a
finished render is posted exactly once no matter how often the collector ticks.
Old/non-kickoff renders (no meta.json) are ignored. Sets GITHUB_OUTPUT:
  ready=true|false, mp3=<path>, render_id=<id>.
"""
import os, sys, json, shutil, subprocess
from pathlib import Path

OUT_DIR = Path("output/ai_clips")
STATE   = Path("output/ai_last_posted.txt")


def gh_out(**kw):
    p = os.environ.get("GITHUB_OUTPUT")
    if not p:
        print("(no GITHUB_OUTPUT)", kw); return
    with open(p, "a", encoding="utf-8") as f:
        for k, v in kw.items():
            f.write(f"{k}={v}\n")


def kaggle(*a):
    return subprocess.run(["kaggle", *a], capture_output=True, text=True)


def main():
    user  = os.environ.get("KAGGLE_USERNAME", "").strip()
    token = (os.environ.get("KAGGLE_API_TOKEN", "").strip()
             or os.environ.get("KAGGLE_KEY", "").strip())
    if not user or not token:
        print("No Kaggle creds — nothing to collect."); gh_out(ready="false"); return
    os.environ["KAGGLE_API_TOKEN"] = token
    slug = f"{user}/gb-render-test"

    s = kaggle("kernels", "status", slug)
    status = (s.stdout + s.stderr).lower()
    print("kernel status:", status.strip()[:200])
    if not ("complete" in status or "error" in status):
        print("Kernel still running/queued — nothing to do."); gh_out(ready="false"); return

    # Fresh download (avoid mixing with a previous render's clips).
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    o = kaggle("kernels", "output", slug, "-p", str(OUT_DIR))
    print(o.stdout.strip()[:400]); print(o.stderr.strip()[:400])

    clips  = sorted(OUT_DIR.glob("clip_*.mp4"))
    meta_f = OUT_DIR / "meta.json"
    if not clips or not meta_f.exists():
        print(f"No clips ({len(clips)}) or no meta.json — skip "
              f"(old/non-kickoff render, or render produced nothing).")
        gh_out(ready="false"); return

    meta = json.loads(meta_f.read_text(encoding="utf-8"))
    rid  = str(meta.get("render_id") or "")
    mp3  = meta.get("mp3") or ""
    if not rid or not mp3:
        print("meta.json missing render_id/mp3 — skip."); gh_out(ready="false"); return

    last = STATE.read_text(encoding="utf-8").strip() if STATE.exists() else ""
    if rid == last:
        print(f"render_id {rid} already posted — skip."); gh_out(ready="false"); return

    print(f"READY: {len(clips)} clips, render_id={rid}, mp3={mp3}")
    gh_out(ready="true", mp3=mp3, render_id=rid)


if __name__ == "__main__":
    main()
