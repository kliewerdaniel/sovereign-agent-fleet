import os, json, math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
SCRIPT = json.load(open(HERE / "script.json"))
DURS = json.load(open(HERE / "durations.json"))
FPS = 30
CAPS = HERE / "caps"
CAPS.mkdir(exist_ok=True)
W, H = SCRIPT["width"], SCRIPT["height"]

# Caption plate geometry (landscape demo style: large, transparent, lower-third)
PLATE_H = 320
PLATE_Y = H - PLATE_H
PLATE_PAD = 36
MAX_CHARS = 46
ACCENT = (57, 211, 132)      # current word
SPOKEN = (255, 255, 255)     # spoken
UPCOMING = (150, 160, 175)   # upcoming/dimmed
SHADOW = (0, 0, 0)

# Font — system UI-ish; fall back gracefully
FONT_PATHS = [
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/SFProText-Regular.ttf",
]
FONT = None
for fp in FONT_PATHS:
    if os.path.exists(fp):
        FONT = fp
        break


def load_font(sz):
    if FONT and FONT.endswith(".ttc"):
        return ImageFont.truetype(FONT, sz, index=0)
    return ImageFont.truetype(FONT, sz) if FONT else ImageFont.load_default()


def clip_wrap(text, max_chars):
    words = text.split(" ")
    lines, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    # continuation indent for wrapped lines
    return lines


def fit_font(text, max_w, max_h):
    # binary search font size so the wrapped block fits plate
    lo, hi = 24, 96
    best = lo
    for _ in range(12):
        mid = (lo + hi) // 2
        f = load_font(mid)
        lines = clip_wrap(text, MAX_CHARS)
        ascent, descent = f.getmetrics()
        line_h = ascent + descent + 6
        tot_h = line_h * len(lines)
        max_w_line = max((f.getlength(l) for l in lines), default=0)
        if tot_h <= max_h - 2 * PLATE_PAD and max_w_line <= max_w - 2 * PLATE_PAD:
            best = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def tokenize(text):
    # word-level tokens with trailing space for wrap-aware layout
    return text.split(" ")


# Build per-beat word timeline (proportional spacing from exact transcript)
forall = {}
for b in SCRIPT["beats"]:
    bid = b["id"]
    dur = float(DURS[bid])
    words = tokenize(b["text"])
    n = len(words)
    # each word gets an even slice; leading small pad
    word_durs = [dur / n] * n
    t = 0.0
    timeline = []
    for i, w in enumerate(words):
        timeline.append({"word": w, "start": t, "end": t + word_durs[i]})
        t += word_durs[i]
    forall[bid] = timeline

# Render caption PNGs per beat, per word-frame at FPS
caption_concat = HERE / "caption_concat.txt"
concat_lines = []
frame_idx = 0
for b in SCRIPT["beats"]:
    bid = b["id"]
    dur = float(DURS[bid])
    tl = forall[bid]
    nframes = int(dur * FPS)
    # fit font to the FULL final sentence (spoken_so_far grows) -> use max size that fits longest line of full text
    fsize = fit_font(b["text"], W, PLATE_H)
    font = load_font(fsize)
    ascent, descent = font.getmetrics()
    line_h = ascent + descent + 8
    for fi in range(nframes):
        tsec = fi / FPS
        spoken_idx = [i for i, w in enumerate(tl) if w["end"] <= tsec]
        cur_idx = len(spoken_idx)  # word currently being spoken
        # Build display: spoken words (white) + current (accent) + upcoming (dim)
        disp_words = []
        for i, w in enumerate(tl):
            if i < cur_idx:
                disp_words.append((w["word"], "spoken"))
            elif i == cur_idx:
                disp_words.append((w["word"], "current"))
            else:
                disp_words.append((w["word"], "upcoming"))
        # wrap into lines (wrap-aware)
        lines = []
        cur = ""
        styled = []  # list of (line_text, [(word,style),...])
        line_words = []
        for w, st in disp_words:
            trial = (cur + " " + w).strip()
            if len(trial) <= MAX_CHARS:
                cur = trial
                line_words.append((w, st))
            else:
                lines.append(line_words)
                cur = w
                line_words = [(w, st)]
        if line_words:
            lines.append(line_words)
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # faint plate behind the caption for overlay legibility (landscape demo style)
        d.rectangle([0, PLATE_Y, W, H], fill=(0, 0, 0, 55))
        # vertical centering of block within plate
        block_h = line_h * len(lines)
        y0 = PLATE_Y + (PLATE_H - block_h) // 2
        for li, lw in enumerate(lines):
            line_text = " ".join(w for w, _ in lw)
            # measure to center horizontally
            lw_px = font.getlength(line_text)
            x = (W - lw_px) / 2
            y = y0 + li * line_h
            # draw each word with its color (shadow then fill)
            cx = x
            for w, st in lw:
                col = SPOKEN if st == "spoken" else (ACCENT if st == "current" else UPCOMING)
                d.text((cx + 2, y + 2), w + " ", font=font, fill=SHADOW)
                d.text((cx, y), w + " ", font=font, fill=col)
                cx += font.getlength(w + " ")
        fn = CAPS / f"{bid}_{frame_idx:05d}.png"
        img.save(fn)
        concat_lines.append(f"file 'caps/{bid}_{frame_idx:05d}.png'")
        concat_lines.append(f"duration {1.0/FPS:.4f}")
        frame_idx += 1

with open(caption_concat, "w") as f:
    f.write("\n".join(concat_lines) + "\n")
print("CAPTIONS RENDERED", frame_idx, "frames;", len(concat_lines) // 2, "word-frames")
