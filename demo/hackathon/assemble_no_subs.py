"""Assemble the demo WITHOUT the karaoke subtitle/caption overlay.

Reuses the per-beat visual clips (which never contain captions) and the
per-beat narration audio, but skips the caption track overlay that
assemble.py applies. Produces a clean narrated walkthrough.
"""
import json, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = json.load(open(HERE / "script.json"))
DURS = json.load(open(HERE / "durations.json"))
FF = "/opt/homebrew/bin/ffmpeg"
W, H = SCRIPT["width"], SCRIPT["height"]
FPS = 30
CLIPS = HERE / "clips"
AUDIO = HERE / "audio"
OUT = HERE / "sovereign_agent_fleet_hackathon.mp4"

order = [b["id"] for b in SCRIPT["beats"]]

# 1) visual concat of per-beat clips (no captions baked in)
vis_concat = HERE / "visual_concat.txt"
with open(vis_concat, "w") as f:
    for bid in order:
        p = CLIPS / f"{bid}.mp4"
        if not p.exists():
            raise SystemExit(f"missing clip: {p}")
        f.write(f"file '{p}'\n")

vis = HERE / "visual_tmp.mp4"
subprocess.run([FF, "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", str(vis_concat),
                "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,fps={FPS},format=yuv420p,setsar=1",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "medium",
                "-r", str(FPS), "-an", str(vis)], check=True)

# 2) concat narration audio
aud_concat = HERE / "audio_concat.txt"
with open(aud_concat, "w") as f:
    for bid in order:
        a = AUDIO / f"{bid}.wav"
        if not a.exists():
            raise SystemExit(f"missing audio: {a}")
        f.write(f"file '{a}'\n")
NARR = HERE / "narration.wav"
subprocess.run([FF, "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", str(aud_concat),
                "-c", "copy", str(NARR)], check=True)

# 3) mux visual + narration ONLY (no caption overlay)
subprocess.run([FF, "-y", "-hide_banner", "-i", str(vis), "-i", str(NARR),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "medium",
                "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
                str(OUT)], check=True)

total = sum(float(DURS[b["id"]]) for b in SCRIPT["beats"])
probe = subprocess.run([FF, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(OUT)],
                       capture_output=True, text=True)
print(f"ASSEMBLED (no subs) {OUT}")
print(f"expected {total:.2f}s | actual {probe.stdout.strip()}s")
