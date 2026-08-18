import json, os, urllib.request, wave, struct, math

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:7860"
SCRIPT = json.load(open(os.path.join(HERE, "script.json")))
VOICE = SCRIPT.get("voice") or "John.mp3"
SPEED = SCRIPT.get("speed", 1.0)
AUDIO = os.path.join(HERE, "audio")

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
    fid = resp["file_id"]; dur = float(resp.get("duration", 0.0))
    with urllib.request.urlopen(BASE + "/api/audio/" + fid, timeout=240) as r:
        wav = r.read()
    return wav, dur

# regenerate b7 only
for b in SCRIPT["beats"]:
    if b["id"] != "b7":
        continue
    print("Regenerating", b["id"])
    wav, dur = generate(b["text"], VOICE, SPEED)
    with open(os.path.join(AUDIO, "b7.wav"), "wb") as f:
        f.write(wav)
    # report WAV stats
    w = wave.open(os.path.join(AUDIO, "b7.wav"), 'rb')
    n=w.getnframes(); fr=w.getframerate(); data=struct.unpack('<%dh'%n, w.readframes(n)); w.close()
    rms=math.sqrt(sum(v*v for v in data)/len(data))
    zcr=sum(1 for i in range(1,len(data)) if (data[i-1]<0)!=(data[i]<0))/len(data)
    print(f"  new b7.wav: {dur:.2f}s  rms={rms:.1f}  zcr={zcr:.4f}  peak={max(abs(min(data)),abs(max(data)))}")
