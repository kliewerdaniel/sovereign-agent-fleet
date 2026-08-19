"""Re-capture ONLY beat b8: the single allowed paper scroll-through.

Uses the same paper-scroll logic as capture.py (consent state so no banner),
targets heading "15. Conclusion", and pads to the b8 narration duration.
Run with the kleincannon venv (has playwright):
  env -u PYTHONPATH -u VIRTUAL_ENV \\
      /Users/danielkliewer/Documents/Projects/kleincannon/venv/bin/python recLip_b8.py
"""
import json, glob, subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SCRIPT = json.load(open(HERE / "script.json"))
DURS = json.load(open(HERE / "durations.json"))
PAPER = SCRIPT.get("paper_base", "http://localhost:8099/paper")
CONSENT_STATE = HERE / "consent_state.json"
FF = "/opt/homebrew/bin/ffmpeg"
W, H = SCRIPT["width"], SCRIPT["height"]

TARGET = "15. Conclusion"


def scroll_target_y(page, txt):
    return page.evaluate(
        "(function(t){"
        "var hs=[].slice.call(document.querySelectorAll('article h2, article h3'));"
        "var el=hs.find(function(h){return h.textContent.trim().indexOf(t)===0;});"
        "if(!el) return null;"
        "return el.getBoundingClientRect().top + window.scrollY;"
        "})", txt)


def main():
    bid = "b8"
    dur = float(DURS[bid])
    with sync_playwright() as p:
        ctx = p.chromium.launch().new_context(
            viewport={"width": W, "height": H},
            storage_state=str(CONSENT_STATE),
            record_video_dir=str(HERE / "clips"),
            record_video_size={"width": W, "height": H},
        )
        # Inject dark palette BEFORE first paint / hydration so the recorded
        # scroll starts dark (add_style_tag alone applies only post-hydration,
        # leaving the opening frames in light mode).
        ctx.add_init_script("""
          (function(){
            function apply(){
              var s=document.createElement('style');
              s.textContent=`
                :root, html { color-scheme: dark !important;
                  --color-base:#14130f !important; --color-base-2:#1c1a15 !important;
                  --color-paper:#14130f !important; --color-paper-2:#1c1a15 !important; --color-paper-3:#242118 !important;
                  --color-ink:#f1ece0 !important; --color-ink-2:#d9d2c2 !important; --color-ink-3:#9a9384 !important;
                  --color-green:#5bbf82 !important; --color-green-dark:#147a3f !important;
                  --color-rule:#33302a !important; --color-pink:#e58ab6 !important; }
                html, body { background:#14130f !important; }`;
              document.head.appendChild(s);
            }
            if(document.head){ apply(); }
            else { document.addEventListener('DOMContentLoaded', apply); }
          })();
        """)
        pg = ctx.new_page()
        pg.goto(PAPER, wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        # Force dark palette with !important so Next.js hydration (which would
        # otherwise re-apply the light :root token block) cannot override it.
        pg.add_style_tag(content="""
          :root, html { color-scheme: dark !important;
            --color-base:#14130f !important; --color-base-2:#1c1a15 !important;
            --color-paper:#14130f !important; --color-paper-2:#1c1a15 !important; --color-paper-3:#242118 !important;
            --color-ink:#f1ece0 !important; --color-ink-2:#d9d2c2 !important; --color-ink-3:#9a9384 !important;
            --color-green:#5bbf82 !important; --color-green-dark:#147a3f !important;
            --color-rule:#33302a !important; --color-pink:#e58ab6 !important; }
          html, body { background:#14130f !important; }
        """)
        pg.wait_for_timeout(800)
        target = scroll_target_y(pg, TARGET) or 0
        focus = max(0, target - int(H * 0.18))
        steps = max(1, int(dur / 0.35))
        for i in range(steps):
            y = int(focus * (i / steps))
            pg.evaluate(f"window.scrollTo({{top:{y}, behavior:'instant'}})")
            pg.wait_for_timeout(350)
        pg.evaluate(f"window.scrollTo({{top:{focus}, behavior:'instant'}})")
        pg.wait_for_timeout(int((dur - steps * 0.35) * 1000) if dur > steps * 0.35 else 600)
        pg.wait_for_timeout(400)
        ctx.close()

    raw = sorted(glob.glob(str(HERE / "clips" / "*.webm")),
                 key=lambda x: Path(x).stat().st_mtime)[-1]
    out = HERE / "clips" / f"{bid}.mp4"
    if out.exists():
        out.unlink()
    subprocess.run([FF, "-y", "-hide_banner", "-i", raw, "-t", str(dur),
                    "-vf", "scale=1920:1080,fps=30,format=yuv420p",
                    "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-an", str(out)],
                   check=True)
    Path(raw).unlink(missing_ok=True)
    print(f"  clip {bid}: {out} ({dur:.1f}s)")


if __name__ == "__main__":
    main()
