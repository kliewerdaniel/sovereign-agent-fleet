#!/usr/bin/env python3
"""Generate a Devpost 3:2 thumbnail (2400x1600) for the project.

Style: dark, architecture-diagram, brand-consistent with the paper/README.
States the core thesis visually: probabilistic COGNITION is walled off from
the deterministic AUTHORITY boundary that actually decides.
"""
from PIL import Image, ImageDraw, ImageFont
import os

W, H = 2400, 1600
OUT = os.path.join(os.path.dirname(__file__), "thumbnail.png")

# ---- palette (matches README paper theme) ----
BG       = (21, 19, 14)      # near-black warm
PANEL    = (33, 29, 20)      # card
PANEL2   = (40, 35, 24)
INK      = (235, 226, 205)   # warm off-white
MUTE     = (150, 138, 116)   # muted label
ORANGE   = (226, 120, 74)    # accent (--color-orange dark)
GREEN    = (120, 190, 120)   # verified / pass
RED      = (214, 90, 70)     # blocked
BLUE     = (120, 165, 210)   # cognition/ai
LINE     = (78, 70, 52)

FONTS = {
    "heavy": "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "bold": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "reg":  "/System/Library/Fonts/Supplemental/Arial.ttf",
    "mono": "/System/Library/Fonts/Menlo.ttc",
}

def font(kind, size):
    path = FONTS[kind]
    if path.endswith(".ttc"):
        return ImageFont.truetype(path, size, index=0)
    return ImageFont.truetype(path, size)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# subtle dotted grid for "engineering" texture
grid = 80
for x in range(0, W, grid):
    for y in range(0, H, grid):
        d.point((x, y), fill=(39, 35, 25))

def rr(box, r, fill=None, outline=None, width=3):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def text(cx, cy, s, fnt, fill=INK, anchor="mm"):
    d.text((cx, cy), s, font=fnt, fill=fill, anchor=anchor)

# ---------------- header ----------------
text(120, 92, "SOVEREIGN AGENT FLEET", font("heavy", 52), fill=INK, anchor="lm")
text(120, 150, "Separating probabilistic cognition from consequential authority",
     font("reg", 30), fill=MUTE, anchor="lm")

# small horizontal rule under header
d.rectangle([120, 182, 2280, 185], fill=LINE)

# ---------------- two big panels ----------------
LX0, LY0, LX1, LY1 = 120, 230, 1180, 760
RX0, RY0, RX1, RY1 = 1220, 230, 2280, 760

rr((LX0, LY0, LX1, LY1), 22, fill=PANEL, outline=BLUE, width=3)
rr((RX0, RY0, RX1, RY1), 22, fill=PANEL, outline=ORANGE, width=3)

text(LX0+40, LY0+50, "COGNITION", font("bold", 40), fill=BLUE, anchor="lm")
text(LX0+40, LY0+95, "probabilistic · may be wrong", font("reg", 26), fill=MUTE, anchor="lm")
# brain-ish stacked blocks (uncertainty)
bx = LX0+60; by = LY0+150; bw=420; bh=70
for i, label in enumerate(["propose", "infer", "recommend"]):
    yy = by + i*(bh+22)
    rr((bx, yy, bx+bw, yy+bh), 12, fill=PANEL2, outline=BLUE, width=2)
    text(bx+24, yy+bh/2, f"  {label}( )  →  confidence?", font("mono", 26), fill=INK, anchor="lm")
text(LX0+40, LY1-46, "never reaches the decision", font("reg", 26), fill=MUTE, anchor="lm")

text(RX0+40, RY0+50, "AUTHORITY", font("bold", 40), fill=ORANGE, anchor="lm")
text(RX0+40, RY0+95, "deterministic · independently verifiable", font("reg", 26), fill=MUTE, anchor="lm")
# the frozen decide() function box
fx = RX0+60; fy = RY0+150
rr((fx, fy, fx+980, fy+250), 14, fill=PANEL2, outline=ORANGE, width=2)
text(fx+30, fy+55, "decide(identity, grant,", font("mono", 30), fill=GREEN, anchor="lm")
text(fx+30, fy+105, "       scope, policy)", font("mono", 30), fill=GREEN, anchor="lm")
text(fx+30, fy+165, "→ AUTO | HUMAN | BLOCKED", font("mono", 30), fill=ORANGE, anchor="lm")
text(RX0+40, RY1-46, "one frozen function · every domain", font("reg", 26), fill=MUTE, anchor="lm")

# ---------------- the boundary wall ----------------
WALL_Y = 830
d.rectangle([120, WALL_Y, 2280, WALL_Y+8], fill=ORANGE)
text(1200, WALL_Y+44, "THE AUTHORITY BOUNDARY — execution only occurs if decide() authorizes it",
     font("bold", 30), fill=ORANGE, anchor="mm")

# ---------------- three verdict chips + verifier ----------------
chip_w = 360; chip_h = 110; gap = 40
start_x = 120; cy = WALL_Y+110
colors = [GREEN, ORANGE, RED]
labels = ["AUTO", "HUMAN", "BLOCKED"]
subs   = ["decide() grants", "human approval", "rejected at boundary"]
for i, (c, lb, sb) in enumerate(zip(colors, labels, subs)):
    x0 = start_x + i*(chip_w+gap)
    rr((x0, cy, x0+chip_w, cy+chip_h), 16, fill=PANEL, outline=c, width=3)
    text(x0+chip_w/2, cy+40, lb, font("bold", 38), fill=c, anchor="mm")
    text(x0+chip_w/2, cy+82, sb, font("reg", 22), fill=MUTE, anchor="mm")

# verifier row on the right
vx0 = 1320; vw = 960
rr((vx0, cy, vx0+vw, cy+chip_h), 16, fill=PANEL, outline=GREEN, width=2)
text(vx0+30, cy+40, "INDEPENDENT VERIFIER", font("bold", 34), fill=GREEN, anchor="lm")
text(vx0+30, cy+82, "execution reported success?  prove it — or be detected", font("reg", 22), fill=MUTE, anchor="lm")

# ---------------- footer thesis ----------------
text(1200, 1110, "“Don’t trust the model. Trust the execution protocol.”",
     font("heavy", 46), fill=INK, anchor="mm")
text(1200, 1172, "Cognition can be wrong, compromised, or hostile — authority is a policy function the model never reaches.",
     font("reg", 26), fill=MUTE, anchor="mm")

# bottom strip with proof points
strip_y = 1240
d.rectangle([120, strip_y, 2280, strip_y+300], fill=PANEL)
d.rectangle([120, strip_y, 2280, strip_y+6], fill=LINE)
points = [
    ("6 domains", "reuse one frozen decide()"),
    ("563 tests", "pass offline · 0 failures"),
    ("A1–A6 threat model", "identity · capability · audit"),
    ("local-first", "no cloud · no model required"),
]
px = 150; pw = (2280-300)/4
for i,(t,s) in enumerate(points):
    cx = px + pw*i + pw/2
    text(cx, strip_y+90, t, font("bold", 36), fill=ORANGE, anchor="mm")
    text(cx, strip_y+150, s, font("reg", 24), fill=MUTE, anchor="mm")

text(120, 1580, "Sovereign Agent Fleet — hackathon submission", font("reg", 20), fill=(90,82,64), anchor="lm")

img.save(OUT, "PNG", optimize=True)
size = os.path.getsize(OUT)
print("wrote", OUT, "bytes", size, "ratio", round(W/H,3))
