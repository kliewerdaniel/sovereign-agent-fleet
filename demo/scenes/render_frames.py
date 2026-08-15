import os, math, subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
FR = os.path.join(ROOT, "demo/frames")
os.makedirs(FR, exist_ok=True)

W, H = 1280, 720
BG = (13, 17, 23)
PANEL = (22, 27, 34)
ACCENT = (88, 166, 255)      # github blue
ACCENT2 = (63, 185, 80)      # green (pass)
WARN = (248, 81, 73)         # red (deny)
TEXT = (230, 237, 243)
DIM = (139, 148, 158)

HFB = "/System/Library/Fonts/Helvetica.ttc"
HFB_B = "/System/Library/Fonts/Helvetica.ttc"  # bold = index 1
MONO = "/System/Library/Fonts/Menlo.ttc"
def font(path, size, bold=False):
    idx = 1 if (bold and path.endswith("Helvetica.ttc")) else 0
    return ImageFont.truetype(path, size, index=idx)

def new():
    return Image.new("RGB", (W, H), BG)

def progress_bar(d, total, frame, t):
    # bottom progress bar
    d.rectangle([0, H-6, W, H], fill=(30,36,44))
    frac = (frame + 1) / total
    d.rectangle([0, H-6, int(W*frac), H], fill=ACCENT)

def footer(d, label):
    d.text((40, H-46), label, font=font(HFB, 22), fill=DIM)

def caption(d, text, y=H-92):
    # lower-third caption band
    d.rectangle([0, y-10, W, y+34], fill=(10,13,18))
    d.rectangle([0, y-10, 6, y+34], fill=ACCENT)
    d.text((28, y), text, font=font(HFB, 24), fill=TEXT)

# ---------------------------------------------------------------- S1 INTRO
def scene_intro():
    im = new(); d = ImageDraw.Draw(im)
    d.text((W//2, 250), "SOVEREIGN AGENT FLEET", font=font(HFB_B, 58), fill=TEXT, anchor="mm")
    d.text((W//2, 320), "Do not trust the model.  Trust the execution protocol.",
           font=font(HFB, 28), fill=ACCENT, anchor="mm")
    d.text((W//2, 400), "An enterprise agent fleet that answers four questions cryptographically:",
           font=font(HFB, 22), fill=DIM, anchor="mm")
    for i, q in enumerate(["which agent", "under what authority", "using what evidence", "has the record been altered"]):
        x = 200 + i*220
        d.rounded_rectangle([x-90, 450, x+90, 500], radius=10, outline=ACCENT, width=2)
        d.text((x, 475), q, font=font(HFB, 16), fill=TEXT, anchor="mm")
    d.text((W//2, 640), "Governability by construction  •  Local-first  •  Verifiable artifacts",
           font=font(HFB, 20), fill=DIM, anchor="mm")
    im.save(os.path.join(FR, "s1_intro.png"))

# ---------------------------------------------------------------- S2 THESIS
def scene_thesis(frame, total):
    im = new(); d = ImageDraw.Draw(im)
    d.text((60, 90), "THESIS", font=font(HFB_B, 26), fill=ACCENT)
    d.text((60, 140), "Do not trust the model.\nTrust the protocol.", font=font(HFB_B, 46), fill=TEXT)
    d.text((60, 300), "Enterprise agents fail adoption because four questions go unanswered:",
           font=font(HFB, 24), fill=DIM)
    for i, q in enumerate(["Which agent acted?", "Under what authority?", "Using what evidence?", "Has the record been altered?"]):
        y = 370 + i*55
        d.ellipse([70, y-12, 94, y+12], fill=ACCENT)
        d.text((82, y), str(i+1), font=font(HFB_B, 18), fill=BG, anchor="mm")
        d.text((120, y), q, font=font(HFB, 26), fill=TEXT, anchor="lm")
    d.text((60, 620), "We built a fleet that answers all four  —  cryptographically.",
           font=font(HFB_B, 28), fill=ACCENT2)
    caption(d, "Intelligence is probabilistic.  Authority is deterministic, and verifiable.")
    progress_bar(d, 1, frame, 0)
    im.save(os.path.join(FR, f"s2_thesis_{frame:03d}.png"))

# ---------------------------------------------------------------- S3 R->A->O
def scene_flow(frame, total):
    im = new(); d = ImageDraw.Draw(im)
    d.text((60, 70), "LIVE MULTI-AGENT RUN", font=font(HFB_B, 26), fill=ACCENT)
    # three agent boxes
    boxes = [("RESEARCHER", "emit SourcedEvidence", (40, 150), ACCENT),
             ("ANALYST", "evaluate -> QualifiedIntel", (480, 150), ACCENT2),
             ("OPERATOR", "artifact + request authority", (920, 150), WARN)]
    for title, sub, (x, y), c in boxes:
        d.rounded_rectangle([x, y, x+300, y+120], radius=14, outline=c, width=3)
        d.text((x+150, y+45), title, font=font(HFB_B, 24), fill=c, anchor="mm")
        d.text((x+150, y+80), sub, font=font(HFB, 15), fill=DIM, anchor="mm")
        if title != "RESEARCHER":
            px = x-40
            d.polygon([(px, y+60), (px+26, y+48), (px+26, y+72)], fill=TEXT)
    # evidence citation arrow loop
    d.rounded_rectangle([40, 330, 1220, 560], radius=12, fill=PANEL)
    ev = [
        "Researcher.gather()  ->  ToolEnvelope verifiable by tool cert  ->  SourcedEvidence(ev_id)",
        "Analyst.qualify()    ->  QualifiedIntel citing [ev_id]  ->  verification = VERIFIED",
        "Operator.act()       ->  artifact + authority request  ->  crm_write",
        "Human approval signed (Ed25519)  ->  FINAL  ->  signed, chained, replicated",
    ]
    for i, line in enumerate(ev):
        d.text((70, 360 + i*48), line, font=font(MONO, 20), fill=TEXT)
    d.text((70, 560), "Against a simulated CRM  •  Registry setup: dept A publishes, dept B discovers",
           font=font(HFB, 18), fill=DIM)
    footer(d, "ControlPlane.publish_agent()  ->  Registry  ->  Fleet")
    caption(d, "One deterministic protocol drives Researcher -> Analyst -> Operator.")
    progress_bar(d, 1, frame, 0)
    im.save(os.path.join(FR, f"s3_flow_{frame:03d}.png"))

# ---------------------------------------------------------------- S4 BEATS
BEATS = [
    ("1", "Prompt injection", "stripped at structured boundary", ACCENT2),
    ("2", "Capability denial", "Gateway DENY + signed deny event", WARN),
    ("3", "No approval", "consequential action blocked pre-FINAL", WARN),
    ("4", "Human approval", "Ed25519 ApprovalRecord signed", ACCENT2),
    ("5", "Execution", "signed, chained, replicated", ACCENT2),
    ("6", "Tamper", "hash-chain verifier detects edit", WARN),
    ("7", "Forged identity", "not signed by root -> rejected", WARN),
    ("8", "Revoke + rotate", "fresh key, chain intact", ACCENT2),
]
def scene_beats(active):
    im = new(); d = ImageDraw.Draw(im)
    d.text((60, 60), "ADVERSARIAL DEMO  —  8 beats, each a passing test", font=font(HFB_B, 26), fill=ACCENT)
    cols, x0, y0, cw, ch, gx, gy = 4, 60, 120, 285, 120, 20, 20
    for i, (num, t, sub, c) in enumerate(BEATS):
        r, cidx = divmod(i, cols)
        x = x0 + cidx*(cw+gx); y = y0 + r*(ch+gy)
        on = (i == active)
        fill = PANEL if not on else (28, 38, 52)
        d.rounded_rectangle([x, y, x+cw, y+ch], radius=12, fill=fill,
                            outline=(c if on else (40,48,58)), width=(4 if on else 2))
        d.ellipse([x+16, y+16, x+52, y+52], fill=(c if on else (40,48,58)))
        d.text((x+34, y+34), num, font=font(HFB_B, 22), fill=(BG if on else DIM), anchor="mm")
        d.text((x+70, y+30), t, font=font(HFB_B, 21), fill=(TEXT if on else DIM))
        d.text((x+16, y+74), sub, font=font(HFB, 15), fill=(TEXT if on else DIM))
    d.text((60, 650), "All 9 tests green in the repository  (pytest fleet/tests)",
           font=font(HFB_B, 22), fill=ACCENT2)
    footer(d, "test_adversarial_beats_phase5.py  •  9 passed in ~1s")
    return im

def scene_beats_seq():
    # render one frame per beat (held in video) showing progression
    for i in range(len(BEATS)):
        im = scene_beats(i)
        caption(im_draw(im), f"Beat {BEATS[i][0]}: {BEATS[i][1]} — {BEATS[i][2]}")
        progress_bar(im_draw(im), 1, 0, 0)
        im.save(os.path.join(FR, f"s4_beat_{i:02d}.png"))

def im_draw(im):
    return ImageDraw.Draw(im)

# ---------------------------------------------------------------- S5 ARCH
def scene_arch(frame, total):
    img = Image.open(os.path.join(ROOT, "docs/assets/architecture.png")).convert("RGB")
    img = img.resize((W, H))
    # subtle darken vignette
    d = ImageDraw.Draw(img)
    caption(d, "Local-first: keys & authority local.  Only signed artifacts replicate to GCP.")
    progress_bar(d, 1, frame, 0)
    img.save(os.path.join(FR, f"s5_arch_{frame:03d}.png"))

# ---------------------------------------------------------------- S5b PROOF overlay
def scene_proof():
    im = new(); d = ImageDraw.Draw(im)
    d.text((60, 60), "GCP REPLICATION  —  verified with PUBLIC keys only", font=font(HFB_B, 26), fill=ACCENT)
    proof = open(os.path.join(ROOT, "demo/scenes/gcp_proof.txt")).read().strip().splitlines()
    d.rounded_rectangle([60, 120, 1220, 360], radius=12, fill=PANEL)
    for i, line in enumerate(proof):
        col = ACCENT2 if "=" in line and ("True" in line or "VERIFIED" in line) else TEXT
        d.text((90, 150 + i*38), line, font=font(MONO, 22), fill=col)
    bonus = open(os.path.join(ROOT, "demo/scenes/gemma_bonus.txt")).read().strip().splitlines()
    d.text((60, 400), "PLUGGABLE BRAIN (D15/D18/D20)", font=font(HFB, 24, bold=True), fill=ACCENT)
    d.rounded_rectangle([60, 440, 1220, 680], radius=12, fill=PANEL)
    import textwrap
    yy = 470
    for i, line in enumerate(bonus):
        for wrap in textwrap.wrap(line, 90):
            d.text((90, yy), wrap, font=font(MONO, 17), fill=TEXT)
            yy += 28
            if yy > 672:
                break
        if yy > 672:
            break
    footer(d, "GcpBridge(mode=local) + FirestoreVerifier  •  Brain interface: Gemma4 dev / Gemini demo")
    caption(d, "GCP holds verifiable DATA, not authority.  Local model == Gemini interface.")
    progress_bar(d, 1, 0, 0)
    im.save(os.path.join(FR, "s6_proof.png"))

# ---------------------------------------------------------------- S6 CLOSE
def scene_close(frame, total):
    im = new(); d = ImageDraw.Draw(im)
    d.text((W//2, 120), "Governability by construction", font=font(HFB_B, 44), fill=TEXT, anchor="mm")
    pts = ["Every beat is a passing automated test — the protocol enforces it",
           "Intelligence stays probabilistic",
           "Authority stays deterministic, signed, and verifiable",
           "A fleet an enterprise can actually adopt"]
    for i, p in enumerate(pts):
        y = 240 + i*70
        d.ellipse([200, y-14, 228, y+14], fill=ACCENT2)
        d.text((214, y), "✓", font=font(HFB_B, 22), fill=BG, anchor="mm")
        d.text((250, y), p, font=font(HFB, 26), fill=TEXT, anchor="lm")
    d.text((W//2, 600), "Run it yourself:  github.com/kliewerdaniel/sovereign-agent-fleet",
           font=font(HFB_B, 24), fill=ACCENT, anchor="mm")
    caption(d, "See the README and architecture diagram in the repo.")
    progress_bar(d, 1, frame, 0)
    im.save(os.path.join(FR, f"s7_close_{frame:03d}.png"))

if __name__ == "__main__":
    scene_intro()
    for f in range(2): scene_thesis(f, 2)
    for f in range(2): scene_flow(f, 2)
    scene_beats_seq()
    for f in range(2): scene_arch(f, 2)
    scene_proof()
    for f in range(2): scene_close(f, 2)
    print("frames rendered:", len(os.listdir(FR)))
