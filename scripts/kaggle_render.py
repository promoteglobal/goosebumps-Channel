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
    """Build ONE continuous cinematic STORY across the scenes: Claude first invents
    a single consistent world (a recurring character + setting + film style), then
    writes the scenes as a connected story arc following the song's emotional
    journey. The shared 'world' string is appended to every shot so independent
    AI clips feel like one short film, not random vignettes. Needs ANTHROPIC_API_KEY;
    falls back to mood prompts if unavailable."""
    n = len(cuts) - 1
    snippets = _section_snippets(bp, cuts)
    instrumental = bp.get("instrumental", not any(snippets))
    key = os.environ.get("ANTHROPIC_API_KEY", "")

    if key and n >= 1:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            full  = (bp.get('lyrics') or bp.get('structure') or '')[:1800]
            lines = "\n".join(
                f"{i}: {snippets[i] or '(instrumental / no words here)'}" for i in range(n))
            prompt = (
                f"You are a music-video director creating ONE continuous cinematic STORY "
                f"for a song, told across {n} sequential shots.\n\n"
                f"Song: '{title}' ({genre})\n"
                f"Full lyrics (for the real meaning and emotional arc):\n{full}\n\n"
                f"What is sung in each of the {n} shots, in order:\n{lines}\n\n"
                f"FIRST invent a SINGLE consistent visual world for the whole video:\n"
                f"- ONE recurring main character (specific: age, clothing, distinguishing "
                f"features) — the same person in every shot\n"
                f"- ONE coherent location/setting and time period\n"
                f"- ONE consistent film style (camera, film stock/color grade, lighting, mood)\n"
                f"This world is IDENTICAL in every shot so it reads as one story.\n\n"
                f"THEN write {n} shots that PROGRESS AS A STORY following the song's "
                f"emotional arc — setup, rising tension, the peak, resolution. Each shot "
                f"continues from the previous (same character, evolving situation). Match the "
                f"EMOTIONAL MEANING of the lyrics in that shot, NOT the literal objects "
                f"(e.g. 'dont close the door' = being left behind -> the character alone at a "
                f"rain-streaked window, not a closing door). Each shot: subject + action + a "
                f"slow gentle camera move. NO on-screen text, words, captions or logos.\n\n"
                f"Reply with ONLY JSON (no markdown):\n"
                f'{{"world": "<one detailed sentence: the SAME character + setting + film '
                f'style to reuse in every shot>", "shots": ["<shot 1>", ... exactly {n} items]}}')
            msg = client.messages.create(model="claude-opus-4-8", max_tokens=3000,
                                         messages=[{"role": "user", "content": prompt}])
            raw = next((b.text for b in msg.content if b.type == "text"), "").strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data  = json.loads(raw)
            world = str(data.get("world", "")).strip()
            shots = data.get("shots") or []
            if isinstance(shots, list) and len(shots) >= n:
                prompts = []
                for i in range(n):
                    shot = str(shots[i]).strip()
                    prompts.append(f"{shot}. {world}. No text or captions." if world else shot)
                print(f"Built a {n}-shot STORY with a consistent world "
                      f"({'instrumental' if instrumental else 'vocal'}).")
                return prompts
        except Exception as e:
            print(f"Story-prompt generation failed ({e}) — using mood fallback")

    # Fallback: simple mood prompt from the title for every scene.
    base = (f"cinematic atmospheric {genre} mood, evocative landscape, soft volumetric "
            f"light, slow drifting camera, inspired by '{title}'")
    return [base for _ in range(n)]


KERNEL_TEMPLATE = r'''
import json, os, sys, base64, subprocess, traceback

def pipi(*pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])

# PROVEN by kernel log: Kaggle's default torch lacks P100 (sm_60) kernels ->
# "no kernel image available for execution on the device" on a P100. torch 2.4.1
# (cu121) ships kernels for sm_60 AND sm_75 (T4), so it runs on either Kaggle GPU.
# ARCH_LIST printed below is the proof that sm_60 is in the build.
# transformers 5.x broke diffusers' LTX import (proven: TRANSFORMERS 5.12.1 ->
# `from transformers import T5EncoderModel` fails). Cap below 5 so pip resolves a
# compatible 4.x + diffusers pair. torch 2.4.1 confirmed to run on the P100.
pipi("-U", "torch==2.4.1",
     "diffusers>=0.32.0,<0.40", "transformers>=4.44.0,<5", "accelerate",
     "sentencepiece", "imageio", "imageio-ffmpeg")

import torch
print("TORCH", torch.__version__, "| CUDA", torch.version.cuda)
try:
    print("ARCH_LIST", torch.cuda.get_arch_list())
    print("DEVICE", torch.cuda.get_device_name(0))
    _x = (torch.randn(64, 64, device="cuda") @ torch.randn(64, 64, device="cuda")).sum().item()
    print("GPU_OP_OK", round(_x, 3))
except Exception as _e:
    import traceback; print("GPU_DIAG_FAIL", _e); traceback.print_exc()

import transformers, diffusers
print("TRANSFORMERS", transformers.__version__, "| DIFFUSERS", diffusers.__version__)
try:
    from transformers import T5EncoderModel  # the dep diffusers LTX needs
    print("T5_IMPORT_OK")
except Exception as _e:
    import traceback; print("T5_IMPORT_FAIL:", repr(_e)); traceback.print_exc()

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
    # The current Kaggle CLI authenticates with a single KAGGLE_API_TOKEN (the
    # "KGAT…" token from the settings UI), NOT the legacy username/key pair.
    # Accept either secret name and expose it the way the CLI expects.
    token = (os.environ.get("KAGGLE_API_TOKEN", "").strip()
             or os.environ.get("KAGGLE_KEY", "").strip())
    if not user or not token:
        print("No KAGGLE_USERNAME / token — skipping AI render (stock fallback).")
        return False
    os.environ["KAGGLE_API_TOKEN"] = token

    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        alt = Path(__file__).parent.parent / mp3_path
        mp3_path = alt if alt.exists() else mp3_path
    bp    = find_blueprint(mp3_path)
    genre = mp3_path.parent.name.lower()
    title = bp.get("title") or mp3_path.stem
    dur   = get_duration(mp3_path)

    smoke = os.environ.get("AI_SMOKE", "").lower() in ("1", "true", "yes")
    if smoke:
        # Cheap ~10-min probe: 1 tiny clip + the GPU diagnostics (ARCH_LIST etc).
        # Confirms torch/CUDA work on Kaggle's GPU BEFORE spending a full hour.
        cuts, prompts = [0.0, min(6.0, dur)], [
            "a calm cinematic landscape at dawn, slow gentle camera drift"]
        nframes, nsteps = 25, 8
        print("SMOKE TEST: 1 diagnostic clip, skipping analysis + Claude.")
    else:
        cuts = get_cut_points(mp3_path, dur)
        # Cap scene count to bound GPU time/quota (re-grid evenly if over the cap).
        if len(cuts) - 1 > MAX_CLIPS:
            n = MAX_CLIPS
            cuts = [round(dur * i / n, 3) for i in range(n)] + [float(dur)]
        prompts = build_video_prompts(bp, cuts, genre, title)
        nframes, nsteps = NUM_FRAMES, AI_STEPS
    n = len(cuts) - 1
    print(f"AI render: {n} scene(s) over {dur:.0f}s for '{title}' ({genre})")

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
            .replace("__NUM_FRAMES__", str(nframes))
            .replace("__W__", str(AI_W)).replace("__H__", str(AI_H))
            .replace("__FPS__", str(FPS)).replace("__STEPS__", str(nsteps)))
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

    # Pull outputs (clips + the kernel's own log land in OUT_DIR).
    o = _kaggle("kernels", "output", slug, "-p", str(OUT_DIR))
    print(o.stdout.strip()); print(o.stderr.strip())

    # Print the kernel's log so a GPU-side failure is visible HERE (not hidden
    # on Kaggle). This is what tells us WHY a render produced no clips.
    keys = ("TORCH", "ARCH_LIST", "DEVICE", "GPU_OP", "GPU_DIAG", "TRANSFORMERS",
            "DIFFUSERS", "T5_IMPORT", "RENDER_DONE", "Error", "error", "FAIL",
            "ModuleNotFound", "ImportError")
    for lg in sorted(OUT_DIR.glob("*.log")):
        try:
            txt = lg.read_text(errors="ignore")
            hits = [ln for ln in txt.splitlines() if any(k in ln for k in keys)]
            if hits:
                print(f"\n----- key diagnostic lines from {lg.name} -----")
                for h in hits[-60:]:
                    print(h[:500])
            print(f"\n----- Kaggle kernel log: {lg.name} (tail) -----")
            print(txt[-6000:])
            print("----- end kernel log -----\n")
        except Exception:
            pass

    clips = sorted(OUT_DIR.glob("clip_*.mp4"))
    print(f"Retrieved {len(clips)} AI clip(s).")
    rep = OUT_DIR / "render_report.json"
    if rep.exists():
        print("Render report:", rep.read_text()[:1200])
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
