#!/usr/bin/env python3
# Pillow transparent overlays: CODE CALLOUT box (TOP-LEFT) + bottom CAPTION strip.
# Real code pulled from the repo. One 1920x1080 RGBA PNG per scene.
import json, os
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
OUT = "callouts"; os.makedirs(OUT, exist_ok=True)
durs = json.load(open("vo/durations.json"))

def font(paths, size):
    for p in paths:
        if os.path.exists(p):
            try: return ImageFont.truetype(p, size)
            except Exception: pass
    return ImageFont.load_default()

MONO = font(["/System/Library/Fonts/Menlo.ttc", "/Library/Fonts/Courier New.ttf"], 27)
UI_SM = font(["/System/Library/Fonts/SFNSDisplay.ttf",
              "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"], 28)
UI = font(["/System/Library/Fonts/SFNSDisplay.ttf",
           "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"], 42)

# (id, title, [real code lines], caption)
SCENE_DATA = {
    "s1": ("", [],
           "Control surface: receives signed artifacts, never decides."),
    "s2": ("LEDGER.append() — fleet/crypto/chriscrypt/ledger.py",
           ["h = hashlib.sha256(self._prev + _entry_body(entry)).digest()",
            "entry['sig'] = self._key.sign(h).hex()",
            "self._prev = h   # next entry commits to THIS one",
            "# tamper with one entry -> every downstream sig breaks"],
           "Immutable, Ed25519-signed. Edges are parent-hash links."),
    "s3": ("Entry payload — canonical signed bytes",
           ["entry = { 'seq':.., 'prev':.., 'ts':..,",
            "           'kind':.., 'payload':.. }",
            "body = canonical_bytes(entry)   # verify against pubkey",
            "sig  = key.sign(sha256(body))"],
           "Open any entry: canonical bytes, prev hash, signature, pubkey."),
    "s4": ("Incident policy — fleet/layers/incident.py",
           ["if verification == HALLUCINATION: return BLOCKED",
            "if VERIFIED and severity==LOW and blast=='LOW': return AUTO",
            "if ASSERTED:                      return HUMAN",
            "# HIGH severity or revenue-svc always escalates"],
           "Three outcomes: AUTO · HUMAN · BLOCKED. Model is never authority."),
    "s5": ("Approval.sign() — fleet/layers/runtime.py (D17)",
           ["body = canonical_bytes({agent_id, action_id,",
            "                        capability, artifact_hash, ...})",
            "sig = human_key.sign(body).hex()",
            "return Approval(approval_id='ap_..', human_sig=sig, ...)"],
           "Asserted -> human. A real Ed25519 approval, bound to this action."),
    "s6": ("Protected asset — fleet/layers/incident.py",
           ["if asset == identity-svc and containment:",
            "    return BLOCKED   # never isolate your own IdP",
            "# sales / financial: schema-only, not yet wired",
            "wired_domains = ['incident']"],
           "identity-svc refuses containment. Unwired domains shown honestly."),
    "s7": ("Live bridge — bridge/app.py",
           ["@app.websocket('/ws')",
            "async def ws(ws): _subscribers.append(ws)",
            "def _broadcast(ev):  # on every append",
            "    await ws.send_text(ev)   # no polling, no replay"],
           "Console subscribes to /ws. Real events, the moment they happen."),
}

PAD = 22
for sid, (title, code, caption) in SCENE_DATA.items():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(img)
    if title or code:
        max_cw = W - 80
        cw = min(int(max([UI_SM.getlength(title)] + [MONO.getlength(l) for l in code]) + 2*PAD), max_cw)
        nlines = len(code)
        box_h = PAD*2 + (40 if title else 0) + nlines*36 + 10
        bx, by = 30, 30                      # TOP-LEFT
        dr.rounded_rectangle([bx, by, bx+cw, by+box_h], radius=14,
                             fill=(12, 16, 22, 235), outline=(120, 200, 140, 235), width=2)
        ty = by + PAD
        if title:
            dr.text((bx+PAD, ty), title, font=UI_SM, fill=(120, 220, 160, 255)); ty += 44
        for l in code:
            col = (255, 210, 120, 255) if l.strip().startswith("#") else (210, 230, 240, 255)
            dr.text((bx+PAD, ty), l, font=MONO, fill=col); ty += 36
    # bottom caption band
    dr.rectangle([0, H-150, W, H], fill=(0, 0, 0, 175))
    dr.text((60, H-118), caption, font=UI, fill=(235, 240, 245, 255))
    img.save(f"{OUT}/{sid}.png")
    print("callout", sid)
print("CALLOUTS DONE")
