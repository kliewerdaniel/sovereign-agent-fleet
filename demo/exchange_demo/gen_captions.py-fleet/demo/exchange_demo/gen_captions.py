"""Karaoke captions + ffmpeg assembly for the exchange demo.

For each beat: split narration into word-slices, render one transparent PNG
per slice (revealed-so-far) into caps/<beat>_NNN.png, write a concat list with
per-slice durations, then assemble each beat as a Ken Burns clip, overlay the
caption concat, and concatenate beats into the final 1080p mp4.

Font auto-fits per beat so the full sentence always fits the plate (no
bottom cutoff). Output: exchange_demo_1080p.mp4
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")
CAPS = os.path.join(HERE, "caps")
os.makedirs(CAPS, exist_ok=True)
W, H = 1920, 1080

SANS_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
WHITE = (255, 255, 255)
ACCENT = (57, 211, 132)
PLATE = (14, 18, 26)
MAX_CHARS = 46
PLATE_H = 230
PLATE_PAD = 22


def wrap_words(words, max_chars):
    lines, cur = [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) > max_chars and cur:
            lines.append(cur); cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def fit_font(full_text):
    for size in range(34, 18, -1):
        f = ImageFont.truetype(SANS_BOLD, size)
        lines = wrap_words(full_text.split(), MAX_CHARS)
        line_h = int(size * 1.18)
        if line_h * len(lines) <= PLATE_H - 2 * PLATE_PAD:
            return f, size, lines
    f = ImageFont.truetype(SANS_BOLD, 18)
    return f, 18, wrap_words(full_text.split(), MAX_CHARS)


def render_beat_captions(beat_id, text, dur):
    words = text.split()
    n = max(1, len(words))
    f, size, lines = fit_font(text)
    line_h = int(size * 1.18)
    step = dur / n
    concat_lines = []
    paths = []
    for i in range(n):
        revealed = " ".join(words[: i + 1])
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        plate_y = H - PLATE_H - 40
        d.rounded_rectangle([0, plate_y, W, plate_y + PLATE_H], radius=18,
                            fill=(*PLATE, 226))
        d.rounded_rectangle([0, plate_y, 10, plate_y + PLATE_H], fill=(*ACCENT, 255))
        ty = plate_y + PLATE_PAD
        for ln in wrap_words(revealed.split(), MAX_CHARS):
            d.text((80, ty), ln, fill=WHITE, font=f)
            ty += line_h
        p = os.path.join(CAPS, f"{beat_id}_{i:03d}.png")
        img.save(p)
        paths.append(p)
        d_slice = step if i < n - 1 else (dur - step * (n - 1))
        concat_lines.append(f"file '{p}'\nduration {d_slice:.4f}\n")
    listf = os.path.join(CAPS, f"{beat_id}_concat.txt")
    with open(listf, "w") as lf:
        lf.writelines(concat_lines)
    return listf, paths


if __name__ == "__main__":
    script = json.load(open(os.path.join(HERE, "script.json")))
    durations = json.load(open(os.path.join(HERE, "durations.json")))
    for bid, text in script["monologue"].items():
        lst, _ = render_beat_captions(bid, text, durations[bid])
        print("captions", bid, "->", lst)
