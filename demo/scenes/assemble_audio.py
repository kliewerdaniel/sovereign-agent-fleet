import os, subprocess
ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
AU = os.path.join(ROOT, "demo/audio")
TMP = os.path.join(ROOT, "demo/_clips")

segments = ["intro.m4a","01_thesis.m4a","02_r_a_o.m4a","03_beats.m4a",
            "04_architecture.m4a","05_close.m4a","outro.m4a"]

# 1) decode each to WAV (PCM) so concatenation is exact, no codec timestamp issues
wavs = []
for s in segments:
    w = os.path.join(TMP, s.replace(".m4a",".wav"))
    subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-i",os.path.join(AU,s),
                    "-ar","44100","-ac","1","-c:a","pcm_s16le", w], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wavs.append(w)

# 2) concat WAVs via demuxer (same params => exact join)
wlist = os.path.join(TMP, "wavs.txt")
with open(wlist,"w") as fh:
    for w in wavs:
        fh.write(f"file '{w}'\n")
fullwav = os.path.join(TMP, "full.wav")
subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-f","concat","-safe","0","-i",wlist,
                "-c","copy", fullwav], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# 3) mux video + audio (video already 214s); encode audio to aac
final = os.path.join(ROOT, "demo", "sovereign_agent_fleet_demo.mp4")
subprocess.run(["/opt/homebrew/bin/ffmpeg","-y","-i",os.path.join(TMP,"silent.mp4"),
                "-i",fullwav,"-c:v","copy","-c:a","aac","-b:a","160k","-shortest", final],
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
d = float(subprocess.check_output(["/opt/homebrew/bin/ffprobe","-v","error",
      "-show_entries","format=duration","-of","csv=p=0", final]).decode().strip())
print("FINAL:", final, os.path.getsize(final), "bytes  dur:", round(d,1), "s")
