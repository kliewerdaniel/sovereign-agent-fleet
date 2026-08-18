import os, sys, json, glob, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SCRIPT = json.load(open(HERE / "script.json"))
DURS = json.load(open(HERE / "durations.json"))
W, H = SCRIPT["width"], SCRIPT["height"]
PAPER = SCRIPT.get("paper_base", "http://localhost:8099/paper")
CLIPS = HERE / "clips"
SHOTS = HERE / "shots"
CLIPS.mkdir(exist_ok=True)
SHOTS.mkdir(exist_ok=True)
FF = "/opt/homebrew/bin/ffmpeg"
# Playwright storage state that already carries the dismissed cookie-consent
# flag (localStorage 'cookie_consent' with hasInteracted:true). Loading it into
# each capture context means the consent banner never mounts on the paper page.
CONSENT_STATE = HERE / "consent_state.json"

# Heading text -> scroll target, resolved at capture time by text match.
TARGETS = {
    "b1": "1. Introduction",
    "b2": "2. The Research Object and the Central Principle",
    "b3": "3. Architectural Invariants",
    "b4": "4. Three Trust Domains and Three Types of Correctness",
    "b6": "11. Threat-Model Conformance Tests",
    "b7": "10. Evaluation Results",
    "b8": "15. Conclusion",
}



def scroll_target_y(page, txt):
    return page.evaluate(
        """(function(t){
            var hs=[].slice.call(document.querySelectorAll('article h2, article h3'));
            var el=hs.find(function(h){return h.textContent.trim().indexOf(t)===0;});
            if(!el) return null;
            return el.getBoundingClientRect().top + window.scrollY;
        })""", txt)


def record_paper_beat(key, url, txt, dur):
    ctx = p.chromium.launch().new_context(
        viewport={"width": W, "height": H},
        storage_state=str(CONSENT_STATE),
        record_video_dir=str(CLIPS), record_video_size={"width": W, "height": H})
    pg = ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded")
    pg.wait_for_timeout(2000)
    target = scroll_target_y(pg, txt) if txt else 0
    if target is None:
        target = 0
    # gentle scroll so the target heading sits comfortably in upper third
    focus = max(0, target - int(H * 0.18))
    steps = max(1, int(dur / 0.35))
    for i in range(steps):
        y = int(focus * (i / steps))
        pg.evaluate(f"window.scrollTo({{top:{y}, behavior:'instant'}})")
        pg.wait_for_timeout(350)
    # settle on the focus point
    pg.evaluate(f"window.scrollTo({{top:{focus}, behavior:'instant'}})")
    pg.wait_for_timeout(int((dur - steps * 0.35) * 1000) if dur > steps * 0.35 else 600)
    pg.wait_for_timeout(400)
    ctx.close()
    finalize_clip(key, dur)


def record_evidence_beat(key, url, dur):
    ctx = p.chromium.launch().new_context(
        viewport={"width": W, "height": H},
        record_video_dir=str(CLIPS), record_video_size={"width": W, "height": H})
    pg = ctx.new_page()
    pg.goto(url, wait_until="domcontentloaded")
    pg.wait_for_timeout(1500)
    steps = max(1, int(dur / 0.5))
    for i in range(steps):
        y = int(120 * (i / steps))
        pg.evaluate(f"window.scrollTo({{top:{y}, behavior:'instant'}})")
        pg.wait_for_timeout(500)
    pg.wait_for_timeout(400)
    ctx.close()
    finalize_clip(key, dur)


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
    for beat in SCRIPT["beats"]:
        key = beat["id"]
        dur = float(DURS[key])
        route = beat["route"]
        sys.stderr.write(f"CAPTURE {key} ({dur:.1f}s)\n"); sys.stderr.flush()
        if route.startswith("live:"):
            record_evidence_beat(key, "file://" + str(HERE / "evidence.html"), dur)
        else:
            record_paper_beat(key, route, TARGETS.get(key, ""), dur)
print("CAPTURE DONE")
