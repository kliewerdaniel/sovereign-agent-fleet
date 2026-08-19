"""Re-capture ONLY beat b5's VISUAL clip from the corrected evidence.html.

Does NOT import capture.py (which runs a full capture at import time). Owns
its own Playwright context + finalize step so we only regenerate the b5 clip
whose on-screen evidence text was just corrected for accuracy.

Evidence beat = a slow scroll over evidence.html (567 collected / 563 passed).
"""
import json, glob, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
DURS = json.load(open(HERE / "durations.json"))
FF = "/opt/homebrew/bin/ffmpeg"
CLIPS = HERE / "clips"
CLIPS.mkdir(exist_ok=True)
W, H = 1920, 1080
KEY = "b5"
DUR = float(DURS[KEY])
EVIDENCE = (HERE / "evidence.html").as_uri()

def finalize_clip(key, dur):
    raw = sorted(glob.glob(str(CLIPS / "*.webm")), key=lambda x: Path(x).stat().st_mtime)[-1]
    out = CLIPS / f"{key}.mp4"
    if out.exists():
        out.unlink()
    subprocess.run([FF, "-y", "-hide_banner", "-i", raw, "-t", str(dur),
                    "-vf", "scale=1920:1080,fps=30,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-an", str(out)],
                   check=True)
    Path(raw).unlink(missing_ok=True)
    print(f"  clip {key}: {out} ({dur:.1f}s)")

with sync_playwright() as p:
    ctx = p.chromium.launch().new_context(
        viewport={"width": W, "height": H},
        record_video_dir=str(CLIPS), record_video_size={"width": W, "height": H})
    pg = ctx.new_page()
    pg.goto(EVIDENCE, wait_until="domcontentloaded")
    pg.wait_for_timeout(1500)
    steps = max(1, int(DUR / 0.5))
    for i in range(steps):
        y = int(120 * (i / steps))
        pg.evaluate(f"window.scrollTo({{top:{y}, behavior:'instant'}})")
        pg.wait_for_timeout(500)
    pg.wait_for_timeout(400)
    ctx.close()
    finalize_clip(KEY, DUR)

print("B5 CLIP DONE")
