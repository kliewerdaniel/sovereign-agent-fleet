import os, json, subprocess, math
from PIL import Image

ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
FR = os.path.join(ROOT, "demo/frames")
AU = os.path.join(ROOT, "demo/audio")
OUT = os.path.join(ROOT, "demo")

def dur(path):
    return float(subprocess.check_output(
        ["/opt/homebrew/bin/ffprobe","-v","error","-show_entries","format=duration",
         "-of","csv=p=0", path]).decode().strip())

# audio segments in order: (audio_file, list_of_frame_files)
segments = [
    ("intro.m4a",   ["s1_intro.png"]),
    ("01_thesis.m4a", ["s2_thesis_000.png", "s2_thesis_001.png"]),
    ("02_r_a_o.m4a",  ["s3_flow_000.png", "s3_flow_001.png"]),
    ("03_beats.m4a",  [f"s4_beat_{i:02d}.png" for i in range(8)]),
    ("04_architecture.m4a", ["s5_arch_000.png", "s5_arch_001.png"]),
    ("05_close.m4a",  ["s7_close_000.png", "s7_close_001.png"]),
    ("outro.m4a",   ["s6_proof.png"]),
]

# Build per-frame durations so each segment's frames fill its audio length.
clips = []  # (frame_png, frame_duration)
for audio, frames in segments:
    a = dur(os.path.join(AU, audio))
    per = a / len(frames)
    for f in frames:
        clips.append((os.path.join(FR, f), per))

print("total clips:", len(clips), "est dur:", round(sum(c[1] for c in clips),1), "s")

# Write concat list of frame images with per-frame duration via fps trick:
# Easier: render each frame to its own video clip at fixed fps with -loop, then concat.
tmpdir = os.path.join(OUT, "_clips")
os.makedirs(tmpdir, exist_ok=True)
concat_lines = []
for i, (png, d) in enumerate(clips):
    # frame rate derived so duration ~ d seconds for 1 frame
    fps = 24
    nframes = max(1, int(round(d*fps)))
    clip = os.path.join(tmpdir, f"clip_{i:03d}.mp4")
    # use a constant frame image
    subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-loop","1","-i",png,
                    "-t", f"{d:.3f}","-r",str(fps),
                    "-c:v","libx264","-pix_fmt","yuv420p","-preset","ultrafast",
                    clip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    concat_lines.append(f"file '{clip}'\n")
    concat_lines.append(f"duration {d:.3f}\n")

# Build video (silent) concat via file-only list (each clip already has correct -t duration)
vlist = os.path.join(tmpdir, "vlist.txt")
with open(vlist, "w") as fh:
    for i in range(len(clips)):
        clip = os.path.join(tmpdir, f"clip_{i:03d}.mp4")
        fh.write(f"file '{clip}'\n")
silent = os.path.join(tmpdir, "silent.mp4")
subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-f","concat","-safe","0","-i",vlist,
                "-c","copy", silent], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Build audio concat
audios = [os.path.join(AU, s[0]) for s in segments]
alist = os.path.join(tmpdir, "alist.txt")
with open(alist, "w") as fh:
    for a in audios:
        fh.write(f"file '{a}'\n")
fullaudio = os.path.join(tmpdir, "full.m4a")
subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-f","concat","-safe","0","-i",alist,
                "-c","copy", fullaudio], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# Mux
final = os.path.join(OUT, "sovereign_agent_fleet_demo.mp4")
subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-i",silent,"-i",fullaudio,
                "-c:v","copy","-c:a","aac","-b:a","160k","-shortest", final],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print("FINAL:", final, os.path.getsize(final), "bytes")
print("final dur:", round(dur(final),1), "s")
