"""Assemble the exchange demo: per-beat Ken Burns clip + caption overlay +
narration mux, then concat into exchange_demo_1080p.mp4.
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, "frames")
CAPS = os.path.join(HERE, "caps")
VO = os.path.join(HERE, "audio")
SEG = os.path.join(HERE, "segs")
os.makedirs(SEG, exist_ok=True)
FPS = 30
W, H = 1920, 1080

script = json.load(open(os.path.join(HERE, "script.json")))
durations = json.load(open(os.path.join(HERE, "durations.json")))
beats = [b["id"] for b in script["beats"]]


def run(cmd):
    r = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return r


def build_beat(bid):
    img = os.path.join(FRAMES, f"{bid}.png")
    cap = os.path.join(CAPS, f"{bid}_concat.txt")
    aud = os.path.join(VO, f"{bid}.wav")
    out = os.path.join(SEG, f"{bid}.mp4")
    dur = durations[bid]
    n = max(1, int(round(dur * FPS)))
    vf = (
        f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"zoompan=z='min(1.06,1+0.06*on/{n})':d=1:s={W}x{H}:"
        f"x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':fps={FPS},"
        f"scale={W}:{H}:flags=lanczos,setsar=1,format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", str(FPS), "-i", img,
        "-f", "concat", "-safe", "0", "-i", cap,
        "-i", aud,
        "-filter_complex",
        f"[0:v]{vf}[v];[1:v]format=rgba[cap];[v][cap]overlay=0:0[vout]",
        "-map", "[vout]", "-map", "2:a",
        "-c:v", "libx264", "-crf", "20", "-preset", "medium",
        "-c:a", "aac", "-b:a", "192k", "-r", str(FPS), "-movflags", "+faststart",
        "-t", f"{dur:.3f}", out,
    ]
    run(cmd)
    return out


def main():
    segs = []
    for bid in beats:
        print("build", bid)
        segs.append(build_beat(bid))
    listf = os.path.join(SEG, "list.txt")
    with open(listf, "w") as lf:
        for s in segs:
            lf.write(f"file '{os.path.abspath(s)}'\n")
    out = os.path.join(HERE, "exchange_demo_1080p.mp4")
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "concat", "-safe", "0", "-i", listf, "-c", "copy", out])
    # error-free gate: ffprobe duration ~ sum(durations)
    total = sum(durations[b] for b in beats)
    res = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of",
                          "default=noprint_wrappers=1:nokey=1", out],
                         capture_output=True, text=True)
    got = float(res.stdout.strip())
    print(f"built {out}: ffprobe={got:.2f}s expected~{total:.2f}s "
          f"({'OK' if abs(got - total) < 1.0 else 'CHECK'})")


if __name__ == "__main__":
    main()
