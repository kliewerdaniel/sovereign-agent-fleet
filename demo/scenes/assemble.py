# -*- coding: utf-8 -*-
"""Assemble the brit-narrated demo: per-scene clips + xfade concat."""
import json, os, subprocess
FF = "/opt/homebrew/bin/ffmpeg"
FP = "/opt/homebrew/bin/ffprobe"
ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
FR = os.path.join(ROOT, "demo", "frames")
AU = os.path.join(ROOT, "demo", "audio")
CL = os.path.join(ROOT, "demo", "_clips")
os.makedirs(CL, exist_ok=True)

SCENES = ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "T10"]
XF = 0.4  # crossfade seconds

def dur(path):
    out = subprocess.check_output([FP, "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())

# Build one clip per scene: hold the frame for the audio duration.
clip_paths = []
for s in SCENES:
    frame = os.path.join(FR, s + ".png")
    audio = os.path.join(AU, s + ".wav")
    out = os.path.join(CL, s + ".mp4")
    ad = dur(audio)
    cmd = [FF, "-y", "-loop", "1", "-i", frame, "-i", audio,
           "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
           "-c:a", "aac", "-b:a", "160k", "-shortest", "-t", f"{ad:.3f}", out]
    subprocess.check_call(cmd)
    clip_paths.append(out)
    print(s, "clip", f"{ad:.2f}s")

# Silent intro hold (poster) + silent outro hold
intro = os.path.join(CL, "intro.mp4")
subprocess.check_call([FF, "-y", "-loop", "1", "-i", os.path.join(FR, "T01.png"),
                       "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                       "-t", "14", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                       "-shortest", "-t", "14", intro])
outro = os.path.join(CL, "outro.mp4")
subprocess.check_call([FF, "-y", "-loop", "1", "-i", os.path.join(FR, "T10.png"),
                       "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                       "-t", "14", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                       "-shortest", "-t", "14", outro])
clip_paths = [intro] + clip_paths + [outro]
print("intro/outro holds added")

# xfade concat
n = len(clip_paths)
if n == 1:
    final = clip_paths[0]
else:
    # inputs
    cmd = [FF, "-y"]
    for c in clip_paths:
        cmd += ["-i", c]
    # build filter_complex chain
    fc = ""
    prev = "[0:v]"
    off = 0.0
    # We need audio xfade too; do video xfade then audio amix across.
    # Simpler: xfade video stream, and for audio use acrossfade.
    vinputs = "".join(f"[{i}:v]" for i in range(n))
    ainputs = "".join(f"[{i}:a]" for i in range(n))
    # Video xfade chain
    chain = ""
    chain += f"[0:v][1:v]xfade=transition=fade:duration={XF}:offset={dur(clip_paths[0])-XF}[v01];"
    labels = ["[v01]"]
    off = dur(clip_paths[0])
    for i in range(2, n):
        off += dur(clip_paths[i-1])
        prevlabel = labels[-1]
        outlabel = f"[v{i:02d}]"
        chain += f"{prevlabel}[{i}:v]xfade=transition=fade:duration={XF}:offset={off-XF}{outlabel};"
        labels.append(outlabel)
    vlast = labels[-1]
    # Audio acrossfade chain (clean, sequential)
    achain = ""
    alabels = ["[0:a]"]
    for i in range(1, n):
        alabels.append(f"[a{i:02d}]")
        achain += f"{alabels[i-1]}[{i}:a]acrossfade=duration={XF}:c1=exp:c2=exp{alabels[i]};"
    fc = chain + achain + f"{vlast}{alabels[-1]}concat=n=1:v=1:a=1[outv][outa]"
    cmd += ["-filter_complex", fc, "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "160k", os.path.join(ROOT, "demo", "sovereign_agent_fleet_demo.mp4")]
    print("FILTER:", fc)
    subprocess.check_call(cmd)

final = os.path.join(ROOT, "demo", "sovereign_agent_fleet_demo.mp4")
print("FINAL:", dur(final), "s ->", final)
