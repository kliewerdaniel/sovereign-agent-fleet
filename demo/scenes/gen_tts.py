# -*- coding: utf-8 -*-
"""Generate one brit-voice WAV per scene from demo/scenes/scripts.txt.

IMPORTANT: the Qwen3-TTS server on :7860 expects the reference-voice field to be
`voice_file` (a filename inside its custom_voices dir, e.g. "brit.mp3"). Sending
`voice` instead is silently ignored and the server falls back to "default" — which
is what produced the wrong-voice audio in commit a03edbe. Use voice_file.
"""
import json, os, urllib.request
BASE = "http://localhost:7860"
ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
OUT = os.path.join(ROOT, "demo", "audio")
os.makedirs(OUT, exist_ok=True)
SCRIPT = os.path.join(ROOT, "demo", "scenes", "scripts.txt")

def gen(text):
    body = json.dumps({"text": text, "voice_file": "brit.mp3", "speed": 0.82}).encode()
    req = urllib.request.Request(BASE + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=180).read().decode())
    fid = data["file_id"]
    wav = urllib.request.urlopen(BASE + "/api/audio/" + fid, timeout=180).read()
    return wav, data.get("duration", 0.0), data.get("voice", "")

total = 0.0
with open(SCRIPT) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line or "|" not in line:
            continue
        sid, text = line.split("|", 1)
        wav, dur, vlabel = gen(text)
        path = os.path.join(OUT, sid + ".wav")
        open(path, "wb").write(wav)
        total += float(dur)
        print(f"{sid}: {dur:.2f}s voice={vlabel} -> {path} ({len(wav)} bytes)")
print(f"TOTAL_NARR: {total:.1f}s")
