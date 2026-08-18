import json, os, urllib.request, sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:7860"
SCRIPT = json.load(open(os.path.join(HERE, "script.json")))
VOICE = SCRIPT.get("voice") or "John.mp3"
SPEED = SCRIPT.get("speed", 1.0)
AUDIO = os.path.join(HERE, "audio")
os.makedirs(AUDIO, exist_ok=True)


def _post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read())


def generate(text, voice_file, speed):
    resp = _post("/api/generate", {"text": text, "voice_file": voice_file, "speed": speed})
    if not resp.get("success"):
        raise RuntimeError(f"generate failed: {resp}")
    fid = resp["file_id"]
    dur = float(resp.get("duration", 0.0))
    with urllib.request.urlopen(BASE + "/api/audio/" + fid, timeout=240) as r:
        wav = r.read()
    return wav, dur


durations = {}
for b in SCRIPT["beats"]:
    bid = b["id"]
    sys.stderr.write(f"TTS {bid}...\n")
    sys.stderr.flush()
    wav, dur = generate(b["text"], VOICE, SPEED)
    with open(os.path.join(AUDIO, f"{bid}.wav"), "wb") as f:
        f.write(wav)
    durations[bid] = dur
    sys.stderr.write(f"  -> {dur:.2f}s\n")

json.dump(durations, open(os.path.join(HERE, "durations.json"), "w"), indent=2)
print("TOTAL", round(sum(durations.values()), 2), "s")
