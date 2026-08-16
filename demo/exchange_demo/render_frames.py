"""Render real-output 1920x1080 dark frames for the exchange demo.

Each beat -> a styled PNG. JSON beats render faithful REAL endpoint output
(window chrome, accent command echo, green [LIVE]/red [SIM], truncation
marker). Title beats render a clean headline card. Output: frames/bN.png
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (11, 15, 22)
PANEL = (17, 22, 33)
PANEL_EDGE = (38, 48, 66)
ACCENT = (57, 211, 132)      # green
ACCENT2 = (122, 162, 255)    # blue
WHITE = (235, 242, 255)
DIM = (140, 156, 182)
RED = (255, 99, 110)
AMBER = (255, 193, 99)
MONO = "/System/Library/Fonts/SFNSMono.ttf"
MONO_BOLD = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"
HEADER = "/System/Library/Fonts/SFNSMono.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Courier New Bold.ttf"

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")
os.makedirs(FRAMES, exist_ok=True)


def f(path, size=24):
    return ImageFont.truetype(path, size)


def load(name):
    with open(os.path.join(HERE, name)) as fh:
        return json.load(fh)


def new_img():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    return img, d


def window(d, title, x, y, w, h):
    """Draw a dark window panel with a title bar."""
    d.rounded_rectangle([x, y, x + w, y + h], radius=14, fill=PANEL,
                        outline=PANEL_EDGE, width=2)
    d.rounded_rectangle([x, y, x + w, y + 40], radius=14, fill=(24, 31, 46))
    for i, col in enumerate([(255, 99, 110), (255, 193, 99), (57, 211, 132)]):
        d.ellipse([x + 22 + i * 22, y + 14, x + 34 + i * 22, y + 26], fill=col)
    d.text((x + 90, y + 11), title, font=f(HEADER, 19), fill=DIM)


def clip(text, n):
    return text if len(text) <= n else text[: n - 1] + "\u2026"


def render_title(beat_id, text):
    img, d = new_img()
    d.text((140, 360), "SOVEREIGN AGENT FLEET", font=f(BOLD, 30), fill=ACCENT)
    lines = []
    cur = ""
    for word in text.split():
        cand = (cur + " " + word).strip()
        if len(cand) > 30 and cur:
            lines.append(cur); cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    y = 430
    for ln in lines:
        d.text((140, y), ln, font=f(BOLD, 64), fill=WHITE); y += 78
    d.text((140, y + 20), "live exchange  \u00b7  governability by design", font=f(MONO, 26), fill=DIM)
    out = os.path.join(FRAMES, f"{beat_id}.png")
    img.save(out); print("frame", out)


def render_json(beat_id, data, title, accent_line, highlight=None):
    img, d = new_img()
    window(d, title, 110, 90, W - 220, H - 180)
    tx, ty = 150, 150
    d.text((tx, ty), accent_line, font=f(BOLD, 24), fill=ACCENT2)
    ty += 44
    txt = json.dumps(data, indent=2)
    rows = txt.split("\n")
    if len(rows) > 26:
        rows = rows[:25] + ["  \u2026 (%d more lines)" % (len(txt.splitlines()) - 25)]
    for row in rows:
        color = WHITE
        if '"live": true' in row or '"connected": true' in row or '"subscription": "all"' in row:
            color = ACCENT
        elif '"live": false' in row or '"connected": false' in row:
            color = RED
        elif any(k in row for k in ("live_ticks", "seen_markets", "bid_cents", "ask_cents")):
            color = AMBER
        if highlight and highlight in row:
            color = ACCENT
        d.text((tx, ty), clip(row, 96), font=f(MONO, 21), fill=color)
        ty += 30
    out = os.path.join(FRAMES, f"{beat_id}.png")
    img.save(out); print("frame", out)


def render_live_title(beat_id, data, text):
    img, d = new_img()
    window(d, "GET /stream/status  \u2014  LIVE", 110, 90, W - 220, H - 180)
    tx, ty = 150, 150
    d.text((tx, ty), text, font=f(BOLD, 26), fill=WHITE); ty += 50
    tiles = [
        ("LIVE TICKS", f"{data['live_ticks']:,}", ACCENT),
        ("SEEN MARKETS", f"{data['seen_markets']:,}", ACCENT2),
        ("SUBSCRIPTION", data["subscription"].upper(), AMBER),
        ("CONNECTED", "YES" if data["connected"] else "NO", ACCENT if data["connected"] else RED),
    ]
    tw = (W - 220 - 150) // 2 - 30
    th = 150
    for i, (lab, val, col) in enumerate(tiles):
        cx = 150 + (i % 2) * (tw + 60)
        cy = ty + (i // 2) * (th + 30)
        d.rounded_rectangle([cx, cy, cx + tw, cy + th], radius=12, fill=(22, 29, 43), outline=col, width=2)
        d.text((cx + 24, cy + 26), lab, font=f(MONO, 22), fill=DIM)
        d.text((cx + 24, cy + 64), val, font=f(BOLD, 46), fill=col)
    out = os.path.join(FRAMES, f"{beat_id}.png")
    img.save(out); print("frame", out)


def render_fleet_gov(beat_id, cases):
    img, d = new_img()
    window(d, "fleet policy  \u2014  required_authorization()  [REAL]", 110, 70, W - 220, H - 140)
    tx, ty = 150, 130
    d.text((tx, ty), "verification  \u00b7  severity  \u00b7  asset class  \u2192  AUTO / HUMAN / BLOCKED",
           font=f(BOLD, 22), fill=ACCENT2); ty += 40
    hdr = f"{'SEV':<8}{'VERIFICATION':<14}{'WORKLOAD':<14}{'ACTION':<14}{'DECISION':<10}"
    d.text((tx, ty), hdr, font=f(MONO, 20), fill=DIM); ty += 30
    sample = [c for c in cases if c["severity"] in ("low", "high", "critical")][:18]
    for c in sample:
        line = f"{c['severity']:<8}{c['verification']:<14}{c['workload']:<14}{c['action']:<14}{c['authorization']}"
        col = {"AUTO": ACCENT, "HUMAN": AMBER, "BLOCKED": RED}[c["authorization"]]
        d.text((tx, ty), line, font=f(MONO, 20), fill=col); ty += 28
    d.text((tx, ty + 14), f"  \u2026 {len(cases)} rows computed by the real policy (no mocks)",
           font=f(MONO, 18), fill=DIM)
    out = os.path.join(FRAMES, f"{beat_id}.png")
    img.save(out); print("frame", out)


def main():
    script = json.load(open(os.path.join(HERE, "script.json")))
    for beat in script["beats"]:
        bid = beat["id"]
        if beat["kind"] == "title":
            render_title(bid, script["monologue"][bid])
        elif bid == "b2":
            render_live_title(bid, load(beat["source"]), "One websocket. All markets. Eight seconds of real flow.")
        elif bid == "b3":
            render_json(bid, load(beat["source"]), "GET /quotes  \u2014  honest live quotes",
                        "Every quote carries live=true. Sim fallback only where no real tick exists.",
                        highlight='"live": true')
        elif bid == "b4":
            render_json(bid, load(beat["source"]), "GET /stream/status  \u2014  SIM-ONLY",
                        "Same code, no credentials: connected=false, live=false, ticks=0, with a note.")
        elif bid == "b5":
            render_fleet_gov(bid, load(beat["source"]))
        else:
            render_title(bid, script["monologue"][bid])


if __name__ == "__main__":
    main()
