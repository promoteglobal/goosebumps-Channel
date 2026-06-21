"""
kaggle_render.py — Generate one AI VIDEO clip per scene on a FREE Kaggle GPU.

Why Kaggle: real text-to-video (LTX-Video) needs a GPU, and GitHub Actions
runners are CPU-only. Kaggle gives ~30 free GPU-hours/week with an API we can
drive headlessly. Because the posting bot only publishes ONE song/day, the GPU
work is naturally spaced to one song at a time — well within the weekly quota.

Flow (all from the GitHub Actions runner):
  1. Compute downbeat-aligned scene cuts (same logic create_video.py uses).
  2. Ask Claude for ONE cinematic T2V prompt per scene (emotional meaning of the
     lyrics there, not the literal words).
  3. Generate a Kaggle "script" kernel with those prompts baked in, push it, and
     poll until it finishes rendering on the GPU.
  4. Download the clips (clip_000.mp4 …) + cuts.json into output/ai_clips/.

This NEVER fails the build: any problem (no keys, push error, timeout, OOM) just
logs and exits 0, leaving output/ai_clips/ without clips so create_video.py
falls back to stock footage. Tag-safe, opt-in.
"""
import os, sys, json, time, base64, shutil, subprocess
from pathlib import Path

# Reuse the exact blueprint + cut logic the video builder uses, so scenes align.
sys.path.insert(0, str(Path(__file__).parent))
from create_video import find_blueprint, get_duration, get_cut_points

FPS = 24
# Short clips that LOOP to fill their scene = cheap on a T4 but still real motion.
NUM_FRAMES = int(os.environ.get("AI_NUM_FRAMES", "121"))   # ~5s @24fps (must be 8k+1)
AI_W       = int(os.environ.get("AI_W", "704"))            # both divisible by 32
AI_H       = int(os.environ.get("AI_H", "448"))
AI_STEPS   = int(os.environ.get("AI_STEPS", "30"))
MAX_CLIPS  = int(os.environ.get("AI_MAX_CLIPS", "40"))     # bound GPU time/quota
POLL_SECS  = 30
TIMEOUT_MIN= int(os.environ.get("AI_TIMEOUT_MIN", "110"))

OUT_DIR = Path("output/ai_clips")


def _section_snippets(bp, cuts):
    """Lyrics sung within each scene [cuts[i], cuts[i+1])."""
    segs = bp.get("lyric_segments") or []
    out = []
    for i in range(len(cuts) - 1):
        s_i, e_i = cuts[i], cuts[i + 1]
        out.append(" ".join(
            sg.get("text", "") for sg in segs
            if sg.get("end", 0) > s_i and sg.get("start", 1e9) < e_i).strip())
    return out


def build_video_prompts(bp, cuts, genre, title):
    """One cinematic text-to-video prompt per scene. Needs ANTHROPIC_API_KEY;
    falls back to mood prompts from the title if Claude is unavailable."""
    n = len(cuts) - 1
    snippets = _section_snippets(bp, cuts)
    instrumental = bp.get("instrumental", not any(snippets))
    key = os.environ.get("ANTHROPIC_API_KEY", "")

    if key and n >= 1:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            if instrumental:
                ctx = (f"INSTRUMENTAL {genre} track titled '{title}'. "
                       f"Mood/structure: {(bp.get('structure') or '')[:400]}")
                ask = (f"Write {n} cinematic AI text-to-video prompts for visuals that "
                       f"fit the title and mood, varied across the {n} scenes.")
            else:
                full  = (bp.get('lyrics') or '')[:1500]
                lines = "\n".join(f"{i}: {snippets[i] or '(no words here)'}" for i in range(n))
                ctx = (f"A {genre} song titled '{title}'. Full lyrics (for the REAL "
                       f"meaning):\n{full}\n\nLyrics sung in each of its {n} scenes:\n{lines}")
                ask = (f"For EACH of the {n} scenes write ONE cinematic AI text-to-video "
                       f"prompt for footage matching the EMOTIONAL MEANING of what is sung "
                       f"there — the feeling and subtext, NOT the literal objects. "
                       f"Example: 'dont close the door' is about being left -> a lone figure "
                       f"at a rain-streaked window at dusk, NOT a closing door.")
            rules = ("Each prompt: one vivid sentence describing subject, action, setting, "
                     "lighting and a slow gentle camera move (push-in, drift, pan). "
                     "Photorealistic cinematic footage. NO on-screen text, words, captions "
                     "or logos. Keep it filmable and coherent. Vary across scenes.")
            prompt = (f"{ctx}\n\n{ask}\n{rules}\n\nReply with ONLY a JSON array of exactly "
                      f"{n} strings, no markdown.")
            msg = client.messages.create(model="claude-opus-4-8", max_tokens=2000,
                                         messages=[{"role": "user", "content": prompt}])
            raw = next((b.text for b in msg.content if b.type == "text"), "").strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            qs = json.loads(raw)
            if isinstance(qs, list) and len(qs) >= n:
                print(f"Built {n} cinematic AI-video prompts "
                      f"({'instrumental' if instrumental else 'vocal'}).")
                return [str(q).strip() for q in qs[:n]]
        except Exception as e:
            print(f"Prompt generation failed ({e}) — using mood fallback")

    # Fallback: simple mood prompt from the title for every scene.
    base = (f"cinematic atmospheric {genre} mood, evocative landscape, soft volumetric "
            f"light, slow drifting camera, inspired by '{title}'")
    return [base for _ in range(n)]


KERNEL_TEMPLATE = r'''
import json, os, sys, base64, subprocess, traceback

def pipi(*pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])

# LTXPipeline lives in recent diffusers; install video IO deps too.
pipi("-U", "diffusers>=0.32.0", "transformers>=4.44.0", "accelerate",
     "sentencepiece", "imageio", "imageio-ffmpeg")

import torch
from diffusers import LTXPipeline
from diffusers.utils import export_to_video

PROMPTS = json.loads(base64.b64decode("__PROMPTS_B64__").decode())
NUM_FRAMES, W, H, FPS, STEPS = __NUM_FRAMES__, __W__, __H__, __FPS__, __STEPS__

os.makedirs("/kaggle/working", exist_ok=True)
report = {"device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
          "n": len(PROMPTS), "results": {}}
print("DEVICE:", report["device"], "| prompts:", len(PROMPTS))

pipe = LTXPipeline.from_pretrained("Lightricks/LTX-Video", torch_dtype=torch.float16)
pipe.enable_model_cpu_offload()          # keep peak VRAM low enough for a T4
try:
    pipe.vae.enable_tiling()
except Exception:
    pass

NEG = "worst quality, jittery, blurry, distorted, watermark, text, caption, logo"
for i, prompt in enumerate(PROMPTS):
    try:
        frames = pipe(prompt=prompt, negative_prompt=NEG, width=W, height=H,
                      num_frames=NUM_FRAMES, num_inference_steps=STEPS).frames[0]
        export_to_video(frames, f"/kaggle/working/clip_{i:03d}.mp4", fps=FPS)
        report["results"][i] = "ok"
        print(f"[{i+1}/{len(PROMPTS)}] OK")
    except Exception as e:
        report["results"][i] = "FAIL: " + str(e)
        print(f"[{i+1}/{len(PROMPTS)}] FAIL: {e}")
        traceback.print_exc()
    with open("/kaggle/working/render_report.json", "w") as f:
        json.dump(report, f, indent=2)
print("RENDER_DONE")
'''


def _kaggle(*args, **kw):
    return subprocess.run(["kaggle", *args], capture_output=True, text=True, **kw)


def render(mp3_path):
    user = os.environ.get("KAGGLE_USERNAME", "").strip()
    key  = os.environ.get("KAGGLE_KEY", "").strip()
    if not user or not key:
        print("No KAGGLE_USERNAME / KAGGLE_KEY — skipping AI render (stock fallback).")
        return False

    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        alt = Path(__file__).parent.parent / mp3_path
        mp3_path = alt if alt.exists() else mp3_path
    bp    = find_blueprint(mp3_path)
    genre = mp3_path.parent.name.lower()
    title = bp.get("title") or mp3_path.stem
    dur   = get_duration(mp3_path)

    cuts = get_cut_points(mp3_path, dur)
    # Cap scene count to bound GPU time/quota (re-grid evenly if over the cap).
    if len(cuts) - 1 > MAX_CLIPS:
        n = MAX_CLIPS
        cuts = [round(dur * i / n, 3) for i in range(n)] + [float(dur)]
    n = len(cuts) - 1
    print(f"AI render: {n} scenes over {dur:.0f}s for '{title}' ({genre})")

    prompts = build_video_prompts(bp, cuts, genre, title)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Write cuts FIRST so create_video can align even on a partial render.
    with open(OUT_DIR / "cuts.json", "w", encoding="utf-8") as f:
        json.dump(cuts, f)

    # Build the kernel folder.
    work = Path("output/_kernel")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    b64 = base64.b64encode(json.dumps(prompts).encode()).decode()
    code = (KERNEL_TEMPLATE
            .replace("__PROMPTS_B64__", b64)
            .replace("__NUM_FRAMES__", str(NUM_FRAMES))
            .replace("__W__", str(AI_W)).replace("__H__", str(AI_H))
            .replace("__FPS__", str(FPS)).replace("__STEPS__", str(AI_STEPS)))
    (work / "gb_render.py").write_text(code, encoding="utf-8")
    slug = f"{user}/gb-render-test"
    meta = {
        "id": slug, "title": "gb-render-test", "code_file": "gb_render.py",
        "language": "python", "kernel_type": "script", "is_private": True,
        "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [], "competition_sources": [], "kernel_sources": [],
    }
    (work / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Pushing kernel {slug} …")
    r = _kaggle("kernels", "push", "-p", str(work))
    print(r.stdout.strip()); print(r.stderr.strip())
    if r.returncode != 0:
        print("Kaggle push failed — stock fallback."); return False

    # Poll until the kernel finishes.
    deadline = time.time() + TIMEOUT_MIN * 60
    status = ""
    while time.time() < deadline:
        time.sleep(POLL_SECS)
        s = _kaggle("kernels", "status", slug)
        status = (s.stdout + s.stderr).lower()
        if "complete" in status:
            print("Kernel complete."); break
        if "error" in status or "cancel" in status:
            print(f"Kernel ended badly: {status.strip()}"); break
        print(f"  … still running ({int((deadline-time.time())/60)} min left)")
    else:
        print("Kernel timed out — pulling whatever rendered.")

    # Pull outputs (clips land in OUT_DIR).
    o = _kaggle("kernels", "output", slug, "-p", str(OUT_DIR))
    print(o.stdout.strip()); print(o.stderr.strip())

    clips = sorted(OUT_DIR.glob("clip_*.mp4"))
    print(f"Retrieved {len(clips)} AI clip(s).")
    rep = OUT_DIR / "render_report.json"
    if rep.exists():
        print("Render report:", rep.read_text()[:800])
    return len(clips) > 0


def main():
    if len(sys.argv) < 2:
        print("usage: kaggle_render.py <mp3_path>"); return
    try:
        ok = render(sys.argv[1])
        print("AI render produced clips." if ok else "No AI clips — create_video will use stock.")
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"AI render crashed ({e}) — stock fallback. (non-fatal)")


if __name__ == "__main__":
    main()
