"""Build the combined flagship demo.

Stitches the honest 8-beat governability film + the exchange-quant pipeline
film into ONE ~4:30 movie with title / part / outro slates.

No source video is re-rendered. The two segments are concatenated as-is
(same profile: 1920x1080, 30fps, yuv420p, h264, aac/24k/mono), so the
existing narration is preserved verbatim. Slates are generated locally with
PIL (Arial) + ffmpeg. Nothing here touches the codebase, tests, or substrate.

Output: demo/sovereign_agent_fleet_combined_1080p.mp4
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
W, H = 1920, 1080
FPS = 30

BEAT = os.path.join(HERE, "demo_1080p.mp4")
EXCH = os.path.join(HERE, "exchange_demo", "exchange_demo_1080p.mp4")
OUT = os.path.join(HERE, "sovereign_agent_fleet_combined_1080p.mp4")
SLATE_DIR = os.path.join(HERE, "_slates")
SEG_DIR = os.path.join(HERE, "_combined_segs")
os.makedirs(SLATE_DIR, exist_ok=True)
os.makedirs(SEG_DIR, exist_ok=True)


def run(cmd):
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return r


def make_slate(name, title, subtitle, dur, accent="#5ad1c8"):
    """Render a dark slate PNG, then loop it with a silent mono audio track."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (W, H), (10, 13, 18))
    d = ImageDraw.Draw(img)
    # subtle top accent bar
    d.rectangle([0, 0, W, 8], fill=accent)
    d.rectangle([0, H - 8, W, H], fill=accent)

    def font(sz):
        return ImageFont.truetype(FONT, sz)

    # title (wrapped)
    title_f = font(116)
    tw = W - 320
    lines = []
    words = title.split(" ")
    cur = ""
    for w in words:
        if d.textlength((cur + " " + w).strip(), font=title_f) <= tw:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)

    y = H // 2 - (len(lines) * 116) // 2 - 40
    for ln in lines:
        lw = d.textlength(ln, font=title_f)
        d.text(((W - lw) / 2, y), ln, font=title_f, fill="#f2f5f7")
        y += 126

    if subtitle:
        sub_f = font(40)
        # wrap subtitle
        sw = W - 480
        slines = []
        cur = ""
        for w in subtitle.split(" "):
            if d.textlength((cur + " " + w).strip(), font=sub_f) <= sw:
                cur = (cur + " " + w).strip()
            else:
                slines.append(cur)
                cur = w
        if cur:
            slines.append(cur)
        sy = H // 2 + (len(lines) * 126) // 2 + 30
        for ln in slines:
            lw = d.textlength(ln, font=sub_f)
            d.text(((W - lw) / 2, sy), ln, font=sub_f, fill="#9fb0bb")
            sy += 52

    png = os.path.join(SLATE_DIR, f"{name}.png")
    img.save(png)

    mp4 = os.path.join(SEG_DIR, f"{name}.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", png,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=24000",
        "-t", f"{dur:.3f}",
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
               f"setsar=1,format=yuv420p",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", "-shortest",
        "-r", str(FPS), "-movflags", "+faststart", mp4,
    ]
    run(cmd)
    return mp4


def main():
    slates = []
    slates.append(make_slate(
        "title",
        "Sovereign Agent Fleet",
        "Governed by execution, not by models — an adversarial governability layer and a prediction-market exchange behind it.",
        6.0,
    ))
    slates.append(make_slate(
        "part1",
        "Part 1 — Adversarial Governability",
        "Eight beats: a model proposes; the protocol decides; a forged identity is refused.",
        3.5,
    ))
    slates.append(make_slate(
        "part2",
        "Part 2 — Exchange Quant Pipeline",
        "A market feed the model can read, behind gates the model can never bypass.",
        3.5,
    ))
    slates.append(make_slate(
        "outro",
        "Built real. Verified.",
        "Local-first. 480 tests. One signed, hash-chained protocol. Owned by you.",
        5.0,
    ))

    segments = [slates[0], slates[1], BEAT, slates[2], EXCH, slates[3]]

    listf = os.path.join(SEG_DIR, "list.txt")
    with open(listf, "w") as lf:
        for s in segments:
            lf.write(f"file '{os.path.abspath(s)}'\n")

    run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", listf,
        "-c", "copy", OUT,
    ])

    # verify
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", OUT],
        capture_output=True, text=True).stdout.strip()
    probe = subprocess.run(
        ["ffprobe", "-v", "error",
         "-show_entries", "stream=codec_type,codec_name,width,height",
         "-of", "default=nw=1", OUT],
        capture_output=True, text=True).stdout.strip()
    size = os.path.getsize(OUT)
    mm = int(float(dur)) // 60
    ss = int(float(dur)) % 60
    print(f"built {OUT}")
    print(f"  duration={dur}s ({mm}:{ss:02d})  size={size/1e6:.1f}MB")
    print(f"  streams:\n  {probe}")
    print(f"  slates: {[os.path.basename(s) for s in slates]}")


if __name__ == "__main__":
    main()
