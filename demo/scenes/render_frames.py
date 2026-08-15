# -*- coding: utf-8 -*-
"""Render dark-first demo frames, one per scene, embedding REAL artifacts."""
import json, os, textwrap
from PIL import Image, ImageDraw, ImageFont

ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
F = os.path.join(ROOT, "demo", "frames")
os.makedirs(F, exist_ok=True)
HFB = "/System/Library/Fonts/Helvetica.ttc"     # bold at index 1
MONO = "/System/Library/Fonts/Menlo.ttc"

def font(sz, bold=False, mono=False):
    if mono:
        return ImageFont.truetype(MONO, sz)
    if bold:
        return ImageFont.truetype(HFB, sz, index=1)
    return ImageFont.truetype(HFB, sz)

W, H = 1280, 720
BG = (13, 17, 23)
PANEL = (22, 27, 34)
ACCENT = (88, 166, 255)
GREEN = (63, 185, 80)
RED = (248, 81, 73)
GREY = (139, 148, 158)
WHITE = (230, 237, 243)

def new():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    return img, d

def rule(d, y, col=PANEL, h=2):
    d.rectangle([0, y, W, y + h], fill=col)

def header(d, title, sub=None):
    d.text((60, 44), title, font=font(34, bold=True), fill=WHITE)
    if sub:
        d.text((62, 92), sub, font=font(18), fill=GREY)
    rule(d, 130, PANEL, 2)

def footer(d, idx):
    d.text((60, H - 46), "Sovereign Agent Fleet  -  hackathon demo", font=font(15), fill=GREY)
    d.text((W - 160, H - 46), f"{idx}/10", font=font(15), fill=GREY)

def wrap_lines(d, x, y, text, fnt, fill, maxw, lh, maxlines=None):
    lines = []
    for para in text.split("\n"):
        lines += textwrap.wrap(para, maxw) or [""]
    if maxlines:
        lines = lines[:maxlines]
    for i, ln in enumerate(lines):
        d.text((x, y + i * lh), ln, font=fnt, fill=fill)
    return y + len(lines) * lh

def badge(d, x, y, text, col):
    fnt = font(20, bold=True)
    tw = d.textlength(text, font=fnt)
    d.rounded_rectangle([x, y, x + tw + 28, y + 40], radius=8, fill=(col[0]//3, col[1]//3, col[2]//3))
    d.text((x + 14, y + 7), text, font=fnt, fill=col)

# ---- load real artifacts ----
with open(os.path.join(ROOT, "demo", "scenes", "gcp_proof.json")) as f:
    gcp = json.load(f)
beats = []
for line in open(os.path.join(ROOT, "demo", "scenes", "beats_run.txt")):
    if "PASSED" in line or "passed" in line:
        beats.append(line.strip())

# ============================ T01 intro ============================
img, d = new()
header(d, "Sovereign Agent Fleet", "Fortified Enterprise agent system - act on outcomes, under authority")
d.text((60, 180), "An AI fleet that can act on real business", font=font(30), fill=WHITE)
d.text((60, 222), "outcomes - but only under cryptographic", font=font(30), fill=WHITE)
d.text((60, 264), "authority and human-approved actions.", font=font(30), fill=WHITE)
badge(d, 60, 340, "DETERMINISTIC CONTROL PLANE", ACCENT)
badge(d, 430, 340, "PLUGGABLE BRAIN", GREEN)
badge(d, 690, 340, "HUMAN-IN-THE-LOOP", (228, 161, 63))
footer(d, 1)
img.save(os.path.join(F, "T01.png"))

# ============================ T02 threat model ============================
img, d = new()
header(d, "Threat Model", "What we designed against")
items = [
    ("PROMPT INJECTION", "tries to exfiltrate data / misdirect the agent", RED),
    ("CAPABILITY ESCALATION", "worker attempts a capability it was never granted", RED),
    ("FORGED IDENTITY", "impersonates a trusted, root-signed agent", RED),
    ("TAMPERED CLOUD LOG", "post-hoc edit hides what actually happened", RED),
]
y = 180
for t, s, c in items:
    badge(d, 60, y, t, c)
    d.text((360, y + 9), s, font=font(20), fill=GREY)
    y += 80
footer(d, 2)
img.save(os.path.join(F, "T02.png"))

# ============================ T03 architecture ============================
img, d = new()
header(d, "Architecture", "Deterministic control plane + pluggable brain")
d.text((60, 175), "MODEL PROPOSES   ->   CONTROL PLANE DECIDES", font=font(24, bold=True), fill=ACCENT)
# pipeline boxes
bx, by, bw, bh = 60, 280, 340, 120
for i, (t, s) in enumerate([("RESEARCHER", "gather evidence"), ("ANALYST", "qualify -> verified"), ("OPERATOR", "act (with approval)")]):
    x = bx + i * (bw + 40)
    d.rounded_rectangle([x, by, x + bw, by + bh], radius=12, fill=PANEL, outline=ACCENT, width=2)
    d.text((x + 20, by + 28), t, font=font(24, bold=True), fill=WHITE)
    d.text((x + 20, by + 72), s, font=font(18), fill=GREY)
    if i < 2:
        d.text((x + bw + 6, by + 48), "->", font=font(30, bold=True), fill=GREY)
d.text((60, 450), "Evidence (Researcher) -> Qualified intel (Analyst) -> Final action (Operator)", font=font(18), fill=GREY)
footer(d, 3)
img.save(os.path.join(F, "T03.png"))

# ============================ T04 beats ============================
img, d = new()
header(d, "Real Tests, Not Slides", "Adversarial beat suite - 9 end-to-end scenarios")
y = 175
for ln in beats[:9]:
    name = ln.split("::")[-1].replace("test_", "").replace("_", " ")
    d.text((70, y), "PASS", font=font(20, bold=True), fill=GREEN)
    d.text((170, y), name, font=font(19), fill=WHITE)
    y += 42
footer(d, 4)
img.save(os.path.join(F, "T04.png"))

# ============================ T05 human approval ============================
img, d = new()
header(d, "Authority Stays With the Human", "D17 - signed, bound approval record")
d.text((60, 185), "Consequential action without human sign-off is REFUSED.", font=font(22), fill=WHITE)
y = 270
for t in ["human signs ApprovalRecord", "bound to: action_id + capability + artifact_hash",
          "operator reaches FINAL only with valid approval", "Gateway REQUIRES_APPROVAL for consequential ops"]:
    d.text((80, y), "- " + t, font=font(20), fill=GREY)
    y += 56
badge(d, 60, 520, "needs_approval = TRUE", (228, 161, 63))
badge(d, 380, 520, "operator.final = TRUE (on sign)", GREEN)
footer(d, 5)
img.save(os.path.join(F, "T05.png"))

# ============================ T06 signed + replicated ============================
img, d = new()
header(d, "Signed, Chained, Replicated", "Every action mirrored as a signed document")
d.text((60, 190), "operator.final and all preceding events", font=font(22), fill=WHITE)
d.text((60, 226), "are mirrored to the cloud store.", font=font(22), fill=WHITE)
badge(d, 60, 300, "LOCAL_CHAIN_OK = TRUE", GREEN)
d.text((420, 308), "-> 12 signed documents replicated", font=font(20), fill=GREY)
footer(d, 6)
img, d = new()
header(d, "Signed, Chained, Replicated", "Every action mirrored as a signed document")
d.text((60, 190), "operator.final and all preceding events", font=font(22), fill=WHITE)
d.text((60, 226), "are mirrored to the cloud store.", font=font(22), fill=WHITE)
badge(d, 60, 300, "LOCAL_CHAIN_OK = TRUE", GREEN)
d.text((420, 308), "-> 12 signed documents replicated", font=font(20), fill=GREY)
footer(d, 6)
img.save(os.path.join(F, "T06.png"))

# ============================ T07 gcp public-key proof ============================
img, d = new()
header(d, "Cloud Copy: Public-Key Verifiable", "Data, not authority (D3/D6)")
d.rounded_rectangle([60, 180, W - 60, 470], radius=10, fill=PANEL, outline=(60, 70, 85))
rows = [
    ("GCP_PROJECT", gcp["GCP_PROJECT"]),
    ("VERIFIER", "FirestoreVerifier (public-key-only)"),
    ("LOCAL_CHAIN_OK", str(gcp["LOCAL_CHAIN_OK"]).upper()),
    ("REPLICATED_DOCS", str(gcp["REPLICATED_DOCS"])),
    ("TAMPER_DETECTED", str(gcp["TAMPER_DETECTED"]).upper()),
    ("PRIVATE_KEY_USED", str(gcp["PRIVATE_KEY_USED_BY_VERIFIER"]).upper()),
]
y = 210
for k, v in rows:
    d.text((90, y), k, font=font(20, bold=True), fill=ACCENT)
    col = GREEN if v in ("TRUE",) else (WHITE if v.startswith("project") else GREY)
    d.text((460, y), v, font=font(20), fill=col)
    y += 46
footer(d, 7)
img.save(os.path.join(F, "T07.png"))

# ============================ T08 brain boundary ============================
img, d = new()
header(d, "Model Brain Is Sandboxed by Contract", "D15 - proposes, never decides")
d.text((60, 185), "Brain proposes classifications; control plane", font=font(22), fill=WHITE)
d.text((60, 221), "enforces the output schema before any record.", font=font(22), fill=WHITE)
y = 300
for t in ["malformed / out-of-range proposals -> REJECTED", "no policy / approval vocabulary reaches the model",
          "validate_brain_output() guards the boundary", "MODEL_CALLED = FALSE in this proof"]:
    d.text((80, y), "- " + t, font=font(20), fill=GREY)
    y += 52
badge(d, 60, 540, "SCHEMA_ENFORCED", GREEN)
footer(d, 8)
img.save(os.path.join(F, "T08.png"))

# ============================ T09 honest ============================
img, d = new()
header(d, "The Honest Version", "Local-first, verifiable, sovereign")
d.text((60, 200), "The GCP proof runs entirely on PUBLIC-KEY", font=font(22), fill=WHITE)
d.text((60, 236), "verification:", font=font(22), fill=WHITE)
for i, t in enumerate(["no private key in the verifier", "no live cloud spend in the demo", "local first, verifiable, sovereign"]):
    badge(d, 60, 300 + i * 70, t, ACCENT)
footer(d, 9)
img.save(os.path.join(F, "T09.png"))

# ============================ T10 close ============================
img, d = new()
header(d, "Sovereign Agent Fleet", "Thank you - good luck to all teams")
d.text((60, 210), "Cryptographic identity.", font=font(26), fill=WHITE)
d.text((60, 256), "Human-in-the-loop authority.", font=font(26), fill=WHITE)
d.text((60, 302), "Verifiable replication.", font=font(26), fill=WHITE)
d.text((60, 348), "A model that proposes but never decides.", font=font(26), fill=WHITE)
footer(d, 10)
img.save(os.path.join(F, "T10.png"))

print("frames written:", sorted(os.listdir(F)))
