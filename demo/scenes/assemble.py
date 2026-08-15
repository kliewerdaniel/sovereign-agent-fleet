# -*- coding: utf-8 -*-
"""Assemble the brit-narrated demo: per-scene clips + hard-cut concat."""
import json, os, subprocess
FF = "/opt/homebrew/bin/ffmpeg"
FP = "/opt/homebrew/bin/ffprobe"
ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
FR = os.path.join(ROOT, "demo", "frames")
AU = os.path.join(ROOT, "demo", "audio")
CL = os.path.join(ROOT, "demo", "_clips")
os.makedirs(CL, exist_ok=True)

SCENES = ["T01", "T02", "T03", "T04", "T05", "T06", "T07", "T08", "T09", "T10"]

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
           "-c:a", "aac", "-ar", "44100", "-b:a", "160k", "-shortest", "-t", f"{ad:.3f}", out]
    subprocess.check_call(cmd)
    clip_paths.append(out)
    print(s, "clip", f"{ad:.2f}s")

# Short silent outro tail only — speech begins immediately at t=0 (T01
# narration) and ends on the last slide; a brief 2s hold keeps a clean
# ending instead of an abrupt cut. (No silent intro: user wants the video
# to open with speech, not a silent title card.)
OUTRO_TAIL = 2.0
outro = os.path.join(CL, "outro.mp4")
subprocess.check_call([FF, "-y", "-loop", "1", "-i", os.path.join(FR, "T10.png"),
                       "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                       "-t", f"{OUTRO_TAIL:.1f}", "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2",
                       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
                       "-shortest", "-t", f"{OUTRO_TAIL:.1f}", outro])
clip_paths = clip_paths + [outro]
print("outro hold added; speech starts at t=0")

# Concat with HARD CUTS (no audio crossfade, no video xfade).
#
# WHY NO acrossfade: fading the last XF seconds of every clip ducks each slide's
# closing syllable (the "end of audio cut off" complaint). Discrete per-slide
# narration must not overlap, so we glue clips with a frame-accurate concat
# FILTER (hard cuts) preserving every slide's full tail. Using the filter (not
# the concat demuxer) avoids the mp4 edit-list duration bug.
final = os.path.join(ROOT, "demo", "sovereign_agent_fleet_demo.mp4")
inp = []
for c in clip_paths:
    inp += ["-i", c]
streams = "".join(f"[{i}:v][{i}:a]" for i in range(len(clip_paths)))
# v=1:a=1 hard-concatenates N (video,audio) pairs in order, no fade.
cmd = [FF, "-y"] + inp + ["-filter_complex", f"{streams}concat=n={len(clip_paths)}:v=1:a=1[outv][outa]",
       "-map", "[outv]", "-map", "[outa]",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "24",
       "-c:a", "aac", "-b:a", "160k", final]
print("CONCAT hard-cut (no audio fade):", len(clip_paths), "segments")
subprocess.check_call(cmd)
print("FINAL:", dur(final), "s ->", final)
