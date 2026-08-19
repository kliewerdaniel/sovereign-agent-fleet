"""Rebuild the demo's VISUAL clips with mostly-static architecture/diagram stills.

Per the redesign:
  - b5 stays LIVE (the decide() test-suite screen)  -> not touched here.
  - b8 stays ONE paper scroll (the single allowed scroll) -> not touched here.
  - b1,b2,b3,b4,b6,b7 become STATIC dark-themed stills rendered from the
    paper's own SVG figures + the fleet architecture.svg, cropped tight to the
    diagram content, centered on a 1920x1080 dark canvas at the beat's exact
    narration duration.

Run with the kleincannon venv (the one that has playwright):
  env -u PYTHONPATH -u VIRTUAL_ENV \
      /Users/danielkliewer/Documents/Projects/kleincannon/venv/bin/python rebuild_static.py
"""
import json, glob, subprocess, sys
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SCRIPT = json.load(open(HERE / "script.json"))
DURS = json.load(open(HERE / "durations.json"))
PAPER = SCRIPT.get("paper_base", "http://localhost:8099/paper")
ARCH_SVG = HERE.parent.parent / "docs" / "assets" / "architecture.svg"
CONSENT_STATE = HERE / "consent_state.json"
FF = "/opt/homebrew/bin/ffmpeg"
W, H = 1920, 1080
BG = "0x14130f"  # dark paper base (RGB 20,19,15)
MARGIN = 0.92    # diagram fills at most 92% of the frame -> balanced margins

# beat -> (source, locator)
# source "paper": aria-label substring of a <figure>'s svg
# source "arch":   the fleet architecture.svg file
STATIC = {
    "b1": ("arch", None),
    "b2": ("paper", "The Three Integrity Domains"),
    "b3": ("paper", "Sovereign Agent Fleet execution state machine"),
    "b4": ("paper", "Complete system architecture"),
    "b6": ("paper", "An untrusted agent emits an unauthorized proposal"),
    "b7": ("paper", "Three trust-domain zones separated by the transformation"),
}


def fig_png(name):
    return HERE / "figs" / f"{name}.png"


def crop_to_content(png: Path):
    """Tighten a screenshot to the diagram's content bounding box.

    The paper renders figures on a solid dark base (the top-left corner pixel),
    so any pixel that differs from that base is part of the diagram. Crop to the
    bounding box of those pixels (+ small padding) so the diagram fills and
    centers correctly after ffmpeg scaling (instead of inheriting the page's
    column padding / off-center position).
    """
    im = Image.open(png).convert("RGB")
    bg = im.getpixel((2, 2))
    px = im.load()
    w, h = im.size
    pad = max(24, int(w * 0.012))  # ~12px CSS at DSF2
    min_b = 255
    bbox = None
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y]
            if (abs(r - bg[0]) + abs(g - bg[1]) + abs(b - bg[2])) > 36:
                if bbox is None:
                    bbox = [x, y, x, y]
                else:
                    if x < bbox[0]: bbox[0] = x
                    if y < bbox[1]: bbox[1] = y
                    if x > bbox[2]: bbox[2] = x
                    if y > bbox[3]: bbox[3] = y
    if bbox is None:
        return  # nothing found; leave as-is
    x0 = max(0, bbox[0] - pad)
    y0 = max(0, bbox[1] - pad)
    x1 = min(w, bbox[2] + pad)
    y1 = min(h, bbox[3] + pad)
    im.crop((x0, y0, x1, y1)).save(png)
    print(f"    cropped {png.name} -> {x1 - x0}x{y1 - y0}")


def make_clip(bid, png, dur):
    out = HERE / "clips" / f"{bid}.mp4"
    if out.exists():
        out.unlink()
    iw, ih = Image.open(png).size
    scale = min(W * MARGIN / iw, H * MARGIN / ih)
    sw, sh = int(iw * scale), int(ih * scale)
    subprocess.run([FF, "-y", "-hide_banner", "-loop", "1", "-i", str(png),
                    "-t", str(dur),
                    "-vf", f"scale={sw}:{sh},"
                           f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={BG},"
                           f"setsar=1,fps=30,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-r", "30", "-an", str(out)],
                   check=True)
    print(f"  clip {bid}: {out} ({dur:.1f}s)")


def screenshot_paper_figures(p):
    ctx = p.chromium.launch().new_context(
        viewport={"width": W, "height": H},
        storage_state=str(CONSENT_STATE),
        device_scale_factor=2,
    )
    pg = ctx.new_page()
    pg.goto(PAPER, wait_until="domcontentloaded")
    # Force the paper's CSS custom properties onto the DARK palette so the
    # inline-SVG figures (which read var(--color-*)) match the dark stills.
    # Also let the figure SVGs render at their natural (un-clipped) height:
    # the paper HTML sets svg{overflow:hidden;height:...} which drops the
    # bottom of tall diagrams, so we override it before screenshotting.
    pg.add_style_tag(content="""
      :root, html { color-scheme: dark !important;
        --color-base:#14130f !important; --color-base-2:#1c1a15 !important;
        --color-paper:#14130f !important; --color-paper-2:#1c1a15 !important; --color-paper-3:#242118 !important;
        --color-ink:#f1ece0 !important; --color-ink-2:#d9d2c2 !important; --color-ink-3:#9a9384 !important;
        --color-green:#5bbf82 !important; --color-green-dark:#147a3f !important;
        --color-rule:#33302a !important; --color-pink:#e58ab6 !important; }
      html, body { background:#14130f !important; }
      figure, figure svg { overflow: visible !important; height: auto !important; }
    """)
    pg.wait_for_timeout(2500)
    for bid, (src, label) in STATIC.items():
        if src != "paper":
            continue
        dur = float(DURS[bid])
        el = pg.query_selector(f'figure svg[aria-label*="{label}"]')
        if el is None:
            el = pg.evaluate_handle(
                "(function(t){return [].slice.call(document.querySelectorAll('figure svg'))"
                ".find(function(s){return (s.getAttribute('aria-label')||'').indexOf(t)>=0;});})",
                label)
        if el is None:
            print(f"  WARN no figure for {bid}: {label}")
            continue
        # Screenshot the <svg> element. The injected style forces
        # svg{height:auto;overflow:visible} so the full diagram (including the
        # bottom of tall figures) renders before capture.
        png = fig_png(bid)
        el.screenshot(path=str(png))
        crop_to_content(png)
        make_clip(bid, png, dur)
    pg.context.close()


def screenshot_arch(p):
    pg = p.chromium.launch().new_context(
        viewport={"width": 1400, "height": 1000},
        device_scale_factor=2,
    ).new_page()
    pg.goto(ARCH_SVG.as_uri(), wait_until="domcontentloaded")
    pg.wait_for_timeout(1200)
    for bid, (src, label) in STATIC.items():
        if src != "arch":
            continue
        dur = float(DURS[bid])
        el = pg.query_selector("svg")
        png = fig_png(bid)
        if el is not None:
            el.screenshot(path=str(png))
        else:
            pg.screenshot(path=str(png))
        make_clip(bid, png, dur)
    pg.context.close()


with sync_playwright() as p:
    (HERE / "figs").mkdir(exist_ok=True)
    screenshot_arch(p)
    screenshot_paper_figures(p)
print("REBUILD STATIC DONE")
