"""Regenerate all narration with the brit voice and rewrite durations.json.

The TTS server is deterministic per (text, voice_file, speed); brit yields
different durations than John, so durations.json must be updated to match the
new narration before re-capturing visuals and re-assembling.
"""
import json, os, urllib.request, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:7860"
SCRIPT = json.load(open(HERE / "script.json"))
VOICE = "/Users/danielkliewer/Documents/Projects/vox/custom_voices/brit.mp3"
SPEED = SCRIPT.get("speed", 1.0)
AUDIO = HERE / "audio"
AUDIO.mkdir(exist_ok=True)


def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def generate(text, voice_file, speed):
    resp = _post("/api/generate", {"text": text, "voice_file": voice_file, "speed": speed})
    if not resp.get("success"):
        raise RuntimeError(f"generate failed: {resp}")
    fid = resp["file_id"]
    dur = float(resp.get("duration", 0.0))
    with urllib.request.urlopen(BASE + "/api/audio/" + fid, timeout=300) as r:
        wav = r.read()
    return wav, dur


durations = {}
for b in SCRIPT["beats"]:
    bid = b["id"]
    sys.stderr.write(f"TTS {bid} (brit)...\n")
    sys.stderr.flush()
    wav, dur = generate(b["text"], VOICE, SPEED)
    out = AUDIO / f"{bid}.wav"
    out.write_bytes(wav)
    durations[bid] = dur
    sys.stderr.write(f"  -> {dur:.2f}s\n")
    sys.stderr.flush()

json.dump(durations, open(HERE / "durations.json", "w"), indent=2)
print("TOTAL", round(sum(durations.values()), 2), "s")
print("PER-BEAT:")
for k, v in durations.items():
    print(f"  {k}: {v:.2f}")
