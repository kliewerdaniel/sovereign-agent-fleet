"""Re-voice ONLY beat b5 with the brit voice and patch durations.json.

Targeted (does not touch other beats) so we keep the existing brit timings
for b1-b4,b6-b8 and only update b5 after its narration text was corrected.
"""
import json, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:7860"
SCRIPT = json.load(open(HERE / "script.json"))
VOICE = "/Users/danielkliewer/Documents/Projects/vox/custom_voices/brit.mp3"
SPEED = SCRIPT.get("speed", 1.0)
AUDIO = HERE / "audio"; AUDIO.mkdir(exist_ok=True)

bid = "b5"
beat = next(b for b in SCRIPT["beats"] if b["id"] == bid)

def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())

resp = _post("/api/generate", {"text": beat["text"], "voice_file": VOICE, "speed": SPEED})
if not resp.get("success"):
    raise RuntimeError(f"generate failed: {resp}")
fid = resp["file_id"]; dur = float(resp.get("duration", 0.0))
with urllib.request.urlopen(BASE + "/api/audio/" + fid, timeout=300) as r:
    wav = r.read()
(HERE / "audio" / f"{bid}.wav").write_bytes(wav)

DUR = json.load(open(HERE / "durations.json"))
DUR[bid] = dur
json.dump(DUR, open(HERE / "durations.json", "w"), indent=2)
print(f"b5 re-voiced: {dur:.2f}s ; total now {round(sum(DUR.values()),2)}s")
