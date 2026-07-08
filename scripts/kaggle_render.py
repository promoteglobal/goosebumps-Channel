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
from keyframes import (music_aligned_cuts, build_shot_specs, load_reference_b64,
                       refs_dir_for)

FPS = 24
# --- image->video (consistent characters) settings ---
# 1152x640 keeps SDXL peak VRAM safe on a Kaggle P100 (16GB) while giving a clean
# 16:9 keyframe to seed LTX (which downsizes to AI_W x AI_H = 832x480 anyway).
KF_W     = int(os.environ.get("AI_KF_W", "1152"))
KF_H     = int(os.environ.get("AI_KF_H", "640"))
KF_STEPS = int(os.environ.get("AI_KF_STEPS", "28"))
# 0.5 balances identity vs following the scene prompt. Higher (0.7) locks identity
# but copies the reference's pose/plain background; lower frees the pose.
IP_SCALE = float(os.environ.get("AI_IP_SCALE", "0.5"))
# Path B = NO LOOPS: each scene gets its own unique clip rendered to the scene's
# length (no repeating). Scenes are short (~AI_SCENE_SECS) so clips stay short =
# fewer AI artifacts AND no looping. Higher resolution than the looped prototype
# for more clarity (832x480 upscales to 1080p far cleaner than 704x448).
AI_SCENE_SECS = float(os.environ.get("AI_SCENE_SECS", "6.5"))
AI_W       = int(os.environ.get("AI_W", "832"))            # both divisible by 32
AI_H       = int(os.environ.get("AI_H", "480"))
AI_STEPS   = int(os.environ.get("AI_STEPS", "25"))         # full quality (async render = no 6h pressure)
MAX_CLIPS  = int(os.environ.get("AI_MAX_CLIPS", "60"))     # allow more short scenes
POLL_SECS  = 30
# No-loop renders the WHOLE song length of unique video, so it is long: at
# 832x480 on a P100, budget several hours. The smoke probe measures the real
# per-clip time before any full run (see [[feedback-no-guessing-expensive-tests]]).
TIMEOUT_MIN= int(os.environ.get("AI_TIMEOUT_MIN", "345"))


def frames_for(secs):
    """Frame count covering `secs` (plus a small margin so create_video can trim
    cleanly with NO loop), rounded up to LTX's required 8*k+1."""
    f = int(round((secs + 0.5) * FPS))
    while (f - 1) % 8 != 0:
        f += 1
    return max(25, f)


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
    """Direct a CINEMATIC MINI-MOVIE across the scenes. Claude casts ONE recurring
    OTHERWORLDLY protagonist (a surreal being — so AI's anatomy/motion glitches read
    as intentional 'ethereal', not 'broken'), writes an emotional story arc that
    interprets the song, designs shots that avoid realistic human locomotion (camera
    moves, not bodies) and save AI-strong spectacle (water/fire/auroras/cosmic light)
    for the frisson PEAK. The shared 'world' is appended to every shot for continuity.
    Needs ANTHROPIC_API_KEY; falls back to mood prompts if unavailable."""
    n = len(cuts) - 1
    snippets = _section_snippets(bp, cuts)
    instrumental = bp.get("instrumental", not any(snippets))
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    score = bp.get("frisson_score", "")
    peak  = max(1, round(0.62 * n))   # golden-ratio frisson peak (~62% through)

    if key and n >= 1:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            full  = (bp.get('lyrics') or bp.get('structure') or '')[:1800]
            lines = "\n".join(
                f"{i}: {snippets[i] or '(instrumental / no words here)'}" for i in range(n))
            prompt = (
                f"You are the DIRECTOR of a cinematic music video — a mini-movie — for this "
                f"song. Tell ONE emotional STORY across {n} sequential shots that interprets "
                f"the song's meaning and amplifies its goosebumps (frisson).\n\n"
                f"Song: '{title}' ({genre}). Frisson score: {score}.\n"
                f"The emotional PEAK lands around shot {peak} of {n} — save the most "
                f"breathtaking, awe-inducing visual for there (and the shots near it).\n"
                f"Full lyrics (for the real meaning and arc):\n{full}\n\n"
                f"What is sung in each shot, in order:\n{lines}\n\n"
                f"CAST A PROTAGONIST the audience can FEEL for — a single recurring being on "
                f"a journey (longing, loss, struggle, hope, transcendence). Give it a clear "
                f"emotional arc with stakes.\n\n"
                f"CRITICAL — design to flatter AI video's strengths and hide its weaknesses:\n"
                f"- The protagonist must be CLEARLY NON-HUMAN — an alien or otherworldly being "
                f"with a distinct, unmistakably inhuman silhouette and features (glowing eyes, "
                f"unusual skin/light, non-human proportions). It must NEVER read as a deformed "
                f"or low-quality HUMAN — make its inhuman-ness obvious and intentional, so AI "
                f"distortions look like the creature's nature, not a glitch.\n"
                f"- Keep its IDENTITY consistent — the same distinctive silhouette, colour and "
                f"features in every shot, so viewers always recognise it as ONE character. Any "
                f"change of form/mood is a deliberate, expressive transformation (ethereal, "
                f"fierce, sorrowful), still recognisably the same being.\n"
                f"- AVOID realistic human locomotion (no walking/running/complex hand gestures). "
                f"Favor the being STILL: standing, floating, gazing, slowly reaching, as a "
                f"silhouette, backlit, seen from behind, in extreme close-up (face/eyes), or "
                f"small within a vast world. Let the CAMERA move (slow push-in, drift, aerial, "
                f"orbit), not the body.\n"
                f"- Use what AI renders beautifully — oceans, water, fire, embers, smoke, mist, "
                f"rain, storms, clouds, auroras, dust, cosmic light, glowing particles — as the "
                f"WORLD, and especially at the PEAK to spike the chills.\n"
                f"- Embrace a dreamlike, surreal, otherworldly look so any imperfection reads "
                f"as style.\n\n"
                f"Keep ONE consistent protagonist + world + film style across ALL shots. Each "
                f"shot: the being + a slow camera move + atmospheric phenomena, matching the "
                f"EMOTIONAL meaning of that shot's lyric (not literal objects). NO on-screen "
                f"text, words, captions or logos.\n\n"
                f"Reply with ONLY JSON (no markdown):\n"
                f'{{"concept": "<one-line logline>", "world": "<one detailed sentence: the SAME '
                f'protagonist + world + film style to reuse in every shot>", "shots": '
                f'["<shot 1>", ... exactly {n} items]}}')
            msg = client.messages.create(model="claude-opus-4-8", max_tokens=4000,
                                         messages=[{"role": "user", "content": prompt}])
            raw = next((b.text for b in msg.content if b.type == "text"), "").strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            data  = json.loads(raw)
            world = str(data.get("world", "")).strip()
            shots = data.get("shots") or []
            if isinstance(shots, list) and len(shots) >= n:
                print(f"STORY concept: {str(data.get('concept',''))[:160]}")
                prompts = []
                for i in range(n):
                    shot = str(shots[i]).strip()
                    prompts.append(
                        f"{shot}. {world}. Surreal otherworldly cinematic film, no text."
                        if world else shot)
                print(f"Built a {n}-shot MINI-MOVIE with an otherworldly protagonist "
                      f"(peak ~shot {peak}, {'instrumental' if instrumental else 'vocal'}).")
                return prompts
        except Exception as e:
            print(f"Story-prompt generation failed ({e}) — using mood fallback")

    # Fallback: surreal otherworldly mood prompt for every scene.
    base = (f"a lone luminous otherworldly figure in a vast surreal {genre} dreamscape, "
            f"glowing mist and cosmic light, slow drifting camera, ethereal and cinematic")
    return [base for _ in range(n)]


KERNEL_TEMPLATE = r'''
import json, os, sys, base64, subprocess, traceback

def pipi(*pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])

# PROVEN by kernel log: Kaggle's default torch lacks P100 (sm_60) kernels ->
# "no kernel image available for execution on the device" on a P100. torch 2.4.1
# (cu121) ships kernels for sm_60 AND sm_75 (T4), so it runs on either Kaggle GPU.
# ARCH_LIST printed below is the proof that sm_60 is in the build.
# Proven, layer by layer:
#  - Kaggle's default torch lacks P100/sm_60 kernels -> pin torch==2.4.1 (has sm_60).
#  - torchvision MUST match torch or you get "operator torchvision::nms does not
#    exist" (ABI mismatch) -> torchvision==0.19.1 pairs with torch 2.4.1.
#  - transformers 5.x breaks diffusers' LTX T5 import -> cap <5.
#  - diffusers 0.38 registers a custom op via a torch.library schema API newer
#    than torch 2.4.1 ("infer_schema: Parameter q unsupported") -> pin diffusers
#    to 0.32.0 (LTX's debut, matches torch 2.4.x).
pipi("-U", "torch==2.4.1", "torchvision==0.19.1",
     "diffusers==0.32.0", "transformers>=4.44.0,<5", "accelerate",
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
# meta.json + cuts.json travel WITH the clips in the kernel output, so the
# decoupled collector can build the video without the original Actions runner.
META = json.loads(base64.b64decode("__META_B64__").decode())
CUTS = json.loads(base64.b64decode("__CUTS_B64__").decode())
with open("/kaggle/working/meta.json", "w") as f:
    json.dump(META, f)
with open("/kaggle/working/cuts.json", "w") as f:
    json.dump(CUTS, f)
print("RENDER_ID", META.get("render_id"))

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


# ============================================================================
# IMAGE -> VIDEO kernel (consistent characters). Two stages, ONE env:
#   1) KEYFRAMES: SDXL + IP-Adapter, each keyframe conditioned on a LOCKED
#      reference picture of the recurring character/place -> the SAME character
#      every shot (the whole point). Prompt = the shot's bible-built instruction.
#   2) ANIMATE: LTX image-to-video turns each keyframe into that shot's clip, at
#      the shot's own frame count (length follows the music).
# Both run on torch==2.4.1 + diffusers==0.32.0, which has sm_60 (P100) AND sm_75
# (T4) kernels AND both pipelines — so it works on whichever GPU Kaggle assigns.
# Heavier true-edit models (Flux Kontext / Qwen-Image-Edit) are deliberately NOT
# used: they need a newer torch that DROPPED the P100 we can't opt out of.
# ============================================================================
# Worker run as a SEPARATE PROCESS per stage (keyframes, then animate) so SDXL's
# RAM is fully returned to the OS before LTX loads — a single process was
# OOM-killed on the P100's ~13GB system RAM. Reads params from _shared.json and
# reference pictures from _ref_<name>.jpg (both written by the parent below).
STAGE_PY = r"""
import sys, json, os, time, traceback, glob, re
from PIL import Image
import torch

stage = sys.argv[1]
WORK  = "/kaggle/working"
S = json.load(open(WORK + "/_shared.json"))
PROMPTS, REFNAMES, FRAMES = S["prompts"], S["refnames"], S["frames"]
W, H, FPS, STEPS = S["W"], S["H"], S["FPS"], S["STEPS"]
KF_STEPS, IP_SCALE, KF_W, KF_H = S["KF_STEPS"], S["IP_SCALE"], S["KF_W"], S["KF_H"]
KF_ONLY, ANIMATE_N, SWEEP = S["KF_ONLY"], S["ANIMATE_N"], S.get("sweep") or []

def load_report():
    try: return json.load(open(WORK + "/render_report.json"))
    except Exception:
        return {"kf": {}, "clips": {},
                "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"}
def save_report(r): json.dump(r, open(WORK + "/render_report.json", "w"), indent=2)

if stage == "keyframes":
    from diffusers import StableDiffusionXLPipeline
    from transformers import CLIPVisionModelWithProjection
    rep = load_report(); rep["stage"] = "keyframes"; save_report(rep)
    REFS = {}
    for f in glob.glob(WORK + "/_ref_*.jpg") + glob.glob(WORK + "/_ref_*.png"):
        name = os.path.basename(f)[5:].rsplit(".", 1)[0]
        try: REFS[name] = Image.open(f).convert("RGB")
        except Exception as e: print("ref load fail", name, e, flush=True)
    print("REFERENCES:", ", ".join(sorted(REFS)), flush=True)
    ie = CLIPVisionModelWithProjection.from_pretrained(
        "h94/IP-Adapter", subfolder="models/image_encoder", torch_dtype=torch.float16)
    sdxl = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0", torch_dtype=torch.float16,
        image_encoder=ie, use_safetensors=True)
    sdxl.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models",
                         weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    sdxl.enable_model_cpu_offload()
    try: sdxl.enable_vae_tiling()
    except Exception: pass
    NEG = ("worst quality, low quality, blurry, distorted, deformed, disfigured, extra "
           "limbs, extra fingers, bad anatomy, text, caption, watermark, logo, signature, "
           "photorealistic photo")
    gen = torch.Generator(device="cuda"); t0 = time.time()
    def one(i, scale, suffix):
        rn  = REFNAMES[i]; ref = REFS.get(rn)
        sdxl.set_ip_adapter_scale(scale if ref is not None else 0.0)
        ip = ref if ref is not None else (next(iter(REFS.values())) if REFS else Image.new("RGB", (224, 224)))
        gen.manual_seed(9679 + i)
        img = sdxl(prompt=PROMPTS[i][:300], negative_prompt=NEG, ip_adapter_image=ip,
                   num_inference_steps=KF_STEPS, guidance_scale=6.5,
                   width=KF_W, height=KF_H, generator=gen).images[0]
        img.save("%s/kf_%03d%s.png" % (WORK, i, suffix))
        return rn
    for i in range(len(PROMPTS)):
        try:
            rn = one(i, IP_SCALE, "")
            rep = load_report(); rep.setdefault("kf", {})[str(i)] = "ok:" + str(rn); save_report(rep)
            print("[KF %d/%d] ok ref=%s scale=%s (%ds)" % (i+1, len(PROMPTS), rn, IP_SCALE, int(time.time()-t0)), flush=True)
            for sc in SWEEP:                    # extra scale variants for tuning (kf_###_sNN.png)
                one(i, sc, "_s%03d" % int(round(sc * 100)))
                print("    sweep kf_%03d @ %s" % (i, sc), flush=True)
        except Exception as e:
            rep = load_report(); rep.setdefault("kf", {})[str(i)] = "FAIL: " + str(e); save_report(rep)
            print("[KF %d/%d] FAIL: %s" % (i+1, len(PROMPTS), e), flush=True); traceback.print_exc()
    print("KEYFRAMES_DONE in %ds" % int(time.time() - t0), flush=True)

elif stage == "animate":
    from diffusers import LTXImageToVideoPipeline
    from diffusers.utils import export_to_video
    rep = load_report(); rep["stage"] = "animate"; save_report(rep)
    idxs = sorted(int(os.path.basename(f)[3:6]) for f in glob.glob(WORK + "/kf_*.png")
                  if re.match(r"kf_\d{3}\.png$", os.path.basename(f)))
    if KF_ONLY: idxs = idxs[:ANIMATE_N]
    if not idxs:
        print("NO_KEYFRAMES_TO_ANIMATE", flush=True); sys.exit(0)
    ltx = LTXImageToVideoPipeline.from_pretrained("Lightricks/LTX-Video", torch_dtype=torch.float16)
    ltx.enable_model_cpu_offload()
    try: ltx.vae.enable_tiling()
    except Exception: pass
    NEGV = "worst quality, jittery, blurry, distorted, morphing, watermark, text, caption, logo"
    ta = time.time()
    for i in idxs:
        try:
            kf = Image.open("%s/kf_%03d.png" % (WORK, i)).convert("RGB").resize((W, H))
            nf = int(FRAMES[i])
            frames = ltx(image=kf, prompt=PROMPTS[i][:300], negative_prompt=NEGV,
                         width=W, height=H, num_frames=nf, num_inference_steps=STEPS).frames[0]
            export_to_video(frames, "%s/clip_%03d.mp4" % (WORK, i), fps=FPS)
            rep = load_report(); rep.setdefault("clips", {})[str(i)] = "ok"; save_report(rep)
            print("[CLIP %d] ok (%df, %ds)" % (i, nf, int(time.time() - ta)), flush=True)
        except Exception as e:
            rep = load_report(); rep.setdefault("clips", {})[str(i)] = "FAIL: " + str(e); save_report(rep)
            print("[CLIP %d] FAIL: %s" % (i, e), flush=True); traceback.print_exc()
    print("ANIMATE_DONE", flush=True)
"""


KERNEL_TEMPLATE_I2V = r'''
import json, os, sys, base64, subprocess

def pipi(*pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *pkgs])

pipi("-U", "torch==2.4.1", "torchvision==0.19.1",
     "diffusers==0.32.0", "transformers>=4.44.0,<5", "accelerate",
     "peft", "sentencepiece", "imageio", "imageio-ffmpeg")

import torch
print("TORCH", torch.__version__, "| CUDA", torch.version.cuda)
try:
    print("ARCH_LIST", torch.cuda.get_arch_list())
    print("DEVICE", torch.cuda.get_device_name(0))
    _x = (torch.randn(64,64,device="cuda") @ torch.randn(64,64,device="cuda")).sum().item()
    print("GPU_OP_OK", round(_x,3))
except Exception as _e:
    import traceback as _tb; print("GPU_DIAG_FAIL", _e); _tb.print_exc()

os.makedirs("/kaggle/working", exist_ok=True)
META = json.loads(base64.b64decode("__META_B64__").decode())
CUTS = json.loads(base64.b64decode("__CUTS_B64__").decode())
json.dump(META, open("/kaggle/working/meta.json","w"))
json.dump(CUTS, open("/kaggle/working/cuts.json","w"))
shared = {
    "prompts":  json.loads(base64.b64decode("__PROMPTS_B64__").decode()),
    "refnames": json.loads(base64.b64decode("__REFNAMES_B64__").decode()),
    "frames":   json.loads(base64.b64decode("__FRAMES_B64__").decode()),
    "sweep":    json.loads(base64.b64decode("__SWEEP_B64__").decode()),
    "W": __W__, "H": __H__, "FPS": __FPS__, "STEPS": __STEPS__,
    "KF_STEPS": __KF_STEPS__, "IP_SCALE": __IP_SCALE__, "KF_W": __KF_W__, "KF_H": __KF_H__,
    "KF_ONLY": __KF_ONLY__, "ANIMATE_N": __ANIMATE_N__,
}
json.dump(shared, open("/kaggle/working/_shared.json","w"))
REFS_B64 = json.loads(base64.b64decode("__REFS_B64__").decode())
for name, b in REFS_B64.items():
    open("/kaggle/working/_ref_" + name + ".jpg", "wb").write(base64.b64decode(b))
open("/kaggle/working/stage.py","w").write(base64.b64decode("__STAGE_PY_B64__").decode())
print("RENDER_ID", META.get("render_id"), "| shots", len(shared["prompts"]),
      "| refs", len(REFS_B64), "| KF_ONLY", __KF_ONLY__)

# Two SEPARATE processes so SDXL's RAM is freed before LTX loads.
r1 = subprocess.run([sys.executable, "/kaggle/working/stage.py", "keyframes"])
print("keyframes stage exit", r1.returncode)
r2 = subprocess.run([sys.executable, "/kaggle/working/stage.py", "animate"])
print("animate stage exit", r2.returncode)
print("RENDER_DONE")
'''


def _kaggle(*args, **kw):
    return subprocess.run(["kaggle", *args], capture_output=True, text=True, **kw)


def _poll_and_pull(slug, out_dir):
    """Wait for the kernel, pull its output, and print the key diagnostic lines so
    a GPU-side failure/timing is visible in the Actions log (not hidden on Kaggle)."""
    deadline = time.time() + TIMEOUT_MIN * 60
    while time.time() < deadline:
        time.sleep(POLL_SECS)
        s = _kaggle("kernels", "status", slug)
        status = (s.stdout + s.stderr).lower()
        if "complete" in status:
            print("Kernel complete."); break
        if "error" in status or "cancel" in status:
            print(f"Kernel ended badly: {status.strip()[:200]}"); break
        print(f"  … still running ({int((deadline-time.time())/60)} min left)")
    else:
        print("Kernel timed out — pulling whatever rendered.")
    o = _kaggle("kernels", "output", slug, "-p", str(out_dir))
    print(o.stdout.strip()); print(o.stderr.strip())
    keys = ("TORCH", "ARCH_LIST", "DEVICE", "GPU_OP", "GPU_DIAG", "REFERENCES",
            "KEYFRAMES_DONE", "[KF ", "[CLIP ", "RENDER_DONE", "Error", "FAIL",
            "Traceback", "OutOfMemory", "CUDA out", "No module", "no kernel image")
    for lg in sorted(Path(out_dir).glob("*.log")):
        try:
            txt = lg.read_text(errors="ignore")
            hits = [ln for ln in txt.splitlines() if any(k in ln for k in keys)]
            if hits:
                print(f"\n----- key lines from {lg.name} -----")
                for h in hits[-80:]:
                    print(h[:400])
            print(f"\n----- {lg.name} (tail) -----"); print(txt[-4000:]); print("----- end log -----\n")
        except Exception:
            pass
    rep = Path(out_dir) / "render_report.json"
    if rep.exists():
        print("Render report:", rep.read_text()[:2000])


def render_i2v(mp3_path, mp3_arg, dur, story, user):
    """IMAGE->VIDEO: one locked-reference keyframe per shot (SDXL + IP-Adapter),
    then LTX image-to-video animates each. Returns True on success, or None to
    signal 'no references -> fall back to text-to-video'."""
    stem  = mp3_path.stem
    bible = {}
    bpath = mp3_path.parent / (stem + ".bible.json")
    if bpath.exists():
        try:
            bible = json.loads(bpath.read_text(encoding="utf-8"))
        except Exception as e:
            print("bible unreadable:", e)
    if not bible.get("style"):
        bible["style"] = story.get("world", "")

    refs_b64 = load_reference_b64(mp3_path)
    if not refs_b64:
        return None  # no locked references -> caller falls back to T2V

    n    = len(story["shots"])
    cuts = music_aligned_cuts(mp3_path, dur, n)
    specs = build_shot_specs(story, bible, cuts, set(refs_b64))

    kf_only   = os.environ.get("AI_KEYFRAMES_ONLY", "").lower() in ("1", "true", "yes")
    animate_n = int(os.environ.get("AI_ANIMATE_N", "1"))
    # Optional IP-Adapter scale sweep (extra kf_###_sNN.png variants) for tuning the
    # identity-vs-scene balance. Defaults on during the keyframe probe only.
    sweep = [float(x) for x in os.environ.get(
        "AI_IP_SWEEP", ("0.35,0.65" if kf_only else "")).replace(" ", "").split(",") if x]

    if kf_only:
        # Cheap probe: the FIRST shot that uses each distinct reference (covers every
        # character + a scenery), so we can eyeball identity-lock before the full run.
        seen, pick = set(), []
        for i, s in enumerate(specs):
            key = s["ref"] or "scenery"
            if key not in seen:
                seen.add(key); pick.append(i)
        pick = sorted(pick)[:8]
        specs_used = [specs[i] for i in pick]
        print(f"KEYFRAMES-ONLY smoke: shots {pick} refs={[specs[i]['ref'] for i in pick]}")
    else:
        specs_used = specs

    prompts  = [s["instr"] for s in specs_used]
    refnames = [s["ref"] or "" for s in specs_used]
    frames   = [s["frames"] for s in specs_used]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "cuts.json", "w", encoding="utf-8") as f:
        json.dump(cuts, f)

    work = Path("output/_kernel")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    render_id = os.environ.get("AI_RENDER_ID") or str(int(time.time()))
    meta_payload = {"render_id": render_id, "mp3": mp3_arg, "n": len(specs_used),
                    "w": AI_W, "h": AI_H, "mode": "i2v", "smoke": kf_only}

    def b(x):
        return base64.b64encode(json.dumps(x).encode()).decode()
    code = (KERNEL_TEMPLATE_I2V
            .replace("__PROMPTS_B64__",  b(prompts))
            .replace("__REFNAMES_B64__", b(refnames))
            .replace("__FRAMES_B64__",   b(frames))
            .replace("__REFS_B64__",     b(refs_b64))
            .replace("__META_B64__",     b(meta_payload))
            .replace("__CUTS_B64__",     b(cuts))
            .replace("__SWEEP_B64__",    b(sweep))
            .replace("__STAGE_PY_B64__", base64.b64encode(STAGE_PY.encode()).decode())
            .replace("__W__", str(AI_W)).replace("__H__", str(AI_H))
            .replace("__FPS__", str(FPS)).replace("__STEPS__", str(AI_STEPS))
            .replace("__KF_STEPS__", str(KF_STEPS)).replace("__IP_SCALE__", str(IP_SCALE))
            .replace("__KF_W__", str(KF_W)).replace("__KF_H__", str(KF_H))
            .replace("__KF_ONLY__", "True" if kf_only else "False")
            .replace("__ANIMATE_N__", str(animate_n)))
    (work / "gb_render.py").write_text(code, encoding="utf-8")
    slug = f"{user}/gb-render-test"
    kmeta = {"id": slug, "title": "gb-render-test", "code_file": "gb_render.py",
             "language": "python", "kernel_type": "script", "is_private": True,
             "enable_gpu": True, "enable_internet": True,
             "dataset_sources": [], "competition_sources": [], "kernel_sources": []}
    (work / "kernel-metadata.json").write_text(json.dumps(kmeta, indent=2), encoding="utf-8")

    print(f"IMAGE->VIDEO: {len(specs_used)} shot(s), {len(refs_b64)} locked refs, "
          f"KF {KF_W}x{KF_H}/{KF_STEPS}st ip={IP_SCALE}, clips {AI_W}x{AI_H}/{AI_STEPS}st, "
          f"kf_only={kf_only}, render_id={render_id}")
    r = _kaggle("kernels", "push", "-p", str(work))
    print(r.stdout.strip()); print(r.stderr.strip())
    if r.returncode != 0:
        print("Kaggle push failed."); return False

    # FULL render: decoupled kickoff (push + exit; the collector posts it).
    if not kf_only and os.environ.get("AI_KICKOFF", "").lower() in ("1", "true", "yes"):
        print(f"KICKOFF complete — render_id={render_id} now rendering on Kaggle. Not waiting.")
        return True

    # KEYFRAMES-ONLY probe (synchronous): wait + pull the keyframes to eyeball.
    kf_dir = Path("output/keyframes")
    kf_dir.mkdir(parents=True, exist_ok=True)
    _poll_and_pull(slug, kf_dir)
    print(f"Keyframes pulled to {kf_dir} ({len(list(kf_dir.glob('kf_*.png')))} images).")
    return True


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

    mp3_arg = str(mp3_path)   # repo-relative path the collector re-uses to build
    mp3_path = Path(mp3_path)
    if not mp3_path.exists():
        alt = Path(__file__).parent.parent / mp3_path
        mp3_path = alt if alt.exists() else mp3_path
    bp    = find_blueprint(mp3_path)
    genre = mp3_path.parent.name.lower()
    title = bp.get("title") or mp3_path.stem
    dur   = get_duration(mp3_path)

    # A hand-written storyboard ("<Song>.story.json" beside the mp3) takes priority
    # over the auto-generator: scene count == number of shots, one clip per shot.
    smoke = os.environ.get("AI_SMOKE", "").lower() in ("1", "true", "yes")
    story = None
    if not smoke:
        sp = mp3_path.parent / (mp3_path.stem + ".story.json")
        if sp.exists():
            try:
                story = json.loads(sp.read_text(encoding="utf-8"))
                if not story.get("shots"):
                    story = None
                else:
                    print(f"MANUAL STORYBOARD: {len(story['shots'])} hand-written shots "
                          f"from {sp.name}")
            except Exception as e:
                print(f"story file unreadable ({e}) — using auto storyboard"); story = None

    # IMAGE->VIDEO (consistent characters): a hand-written story + a locked
    # "<Song>.refs/" reference set -> one keyframe per shot generated FROM the
    # reference picture, then LTX image-to-video. This is the whole point of the
    # upgrade; only falls through to text-to-video if the references are missing.
    if story and refs_dir_for(mp3_path).exists():
        res = render_i2v(mp3_path, mp3_arg, dur, story, user)
        if res is not None:
            return res
        print("Reference load failed — falling back to text-to-video.")

    # NO-LOOP scene grid: even scenes; each clip rendered a hair longer than its
    # scene so create_video trims it with no repeat (one uniform frame count).
    if smoke:
        # ~12-min probe: 2 clips at full-run resolution/frames/steps (measure per-clip
        # time + confirm no OOM) BEFORE a multi-hour render. Skips Claude.
        n = max(8, round(dur / AI_SCENE_SECS))
        scene_len = dur / n
        cuts = [0.0, scene_len, min(2 * scene_len, dur)]
        prompts = [
            "a lone luminous spirit standing still in a vast surreal dreamscape, glowing "
            "mist, slow camera push-in, ethereal otherworldly cinematic film, no text",
            "an otherworldly figure silhouetted against a cosmic aurora over a dark ocean, "
            "drifting embers, slow aerial drift, surreal cinematic film, no text"]
        print(f"SMOKE/TIMING: 2 clips at {AI_W}x{AI_H}; skipping Claude.")
    elif story:
        shots = story["shots"]
        world = (story.get("world") or "").strip()
        n = len(shots)
        scene_len = dur / n
        cuts = [round(dur * i / n, 3) for i in range(n)] + [float(dur)]
        prompts = [(f"{str(s).strip()}. {world}" if world else str(s).strip()) for s in shots]
    else:
        n = max(8, min(MAX_CLIPS, round(dur / AI_SCENE_SECS)))
        scene_len = dur / n
        cuts = [round(dur * i / n, 3) for i in range(n)] + [float(dur)]
        prompts = build_video_prompts(bp, cuts, genre, title)

    nframes, nsteps = frames_for(scene_len), AI_STEPS
    n = len(cuts) - 1
    print(f"AI render (NO-LOOP): {n} scene(s) ~{scene_len:.1f}s each over {dur:.0f}s, "
          f"{AI_W}x{AI_H} {nframes}f/{nsteps}steps for '{title}' ({genre})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # Write cuts FIRST so create_video can align even on a partial render.
    with open(OUT_DIR / "cuts.json", "w", encoding="utf-8") as f:
        json.dump(cuts, f)

    # Build the kernel folder.
    work = Path("output/_kernel")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    render_id = os.environ.get("AI_RENDER_ID") or str(int(time.time()))
    meta_payload = {"render_id": render_id, "mp3": mp3_arg, "n": n,
                    "w": AI_W, "h": AI_H, "frames": nframes, "steps": nsteps}
    b64      = base64.b64encode(json.dumps(prompts).encode()).decode()
    meta_b64 = base64.b64encode(json.dumps(meta_payload).encode()).decode()
    cuts_b64 = base64.b64encode(json.dumps(cuts).encode()).decode()
    code = (KERNEL_TEMPLATE
            .replace("__PROMPTS_B64__", b64)
            .replace("__META_B64__", meta_b64)
            .replace("__CUTS_B64__", cuts_b64)
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

    print(f"Pushing kernel {slug} … (render_id={render_id})")
    r = _kaggle("kernels", "push", "-p", str(work))
    print(r.stdout.strip()); print(r.stderr.strip())
    if r.returncode != 0:
        print("Kaggle push failed — stock fallback."); return False

    # DECOUPLED kickoff: push and EXIT (no waiting). Kaggle renders for hours on
    # its own (well under its ~9h session limit); the scheduled collector
    # (kaggle_collect.py) downloads + builds + posts once the kernel completes.
    # This is how a multi-hour, full-quality, NO-LOOP render avoids GitHub's 6h
    # per-job cap — no single job ever waits long.
    if os.environ.get("AI_KICKOFF", "").lower() in ("1", "true", "yes"):
        print(f"KICKOFF complete — render_id={render_id} is now rendering on Kaggle. "
              f"The collector will pick it up when done. Not waiting.")
        return True

    # Poll until the kernel finishes (sync mode — used by the smoke probe).
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
