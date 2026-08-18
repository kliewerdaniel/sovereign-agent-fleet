import json, os, urllib.request, wave, struct, math

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "http://127.0.0.1:7860"
SCRIPT = json.load(open(os.path.join(HERE, "script.json")))
VOICE = SCRIPT.get("voice") or "John.mp3"
SPEED = SCRIPT.get("speed", 1.0)
AUDIO = os.path.join(HERE, "audio")

# Rephrase b2 to break the deterministic TTS cache (same meaning, new wording).
NEW_B2 = ("The thesis sounds simple and is hard to engineer. Don't trust the model; "
          "trust the execution protocol. Thinking is probabilistic and can be mistaken, "
          "or subverted, or adversarial. Authority is deterministic and lives inside a "
          "policy function the model never reaches.")

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

for b in SCRIPT["beats"]:
    if b["id"] != "b2":
        continue
    b["text"] = NEW_B2
    print("Regenerating b2 with:", NEW_B2)
    wav, dur = generate(b["text"], VOICE, SPEED)
    out = os.path.join(AUDIO, "b2.wav")
    with open(out, "wb") as f:
        f.write(wav)
    w = wave.open(out, 'rb'); n=w.getnframes(); fr=w.getframerate()
    data=struct.unpack('<%dh'%n, w.readframes(n)); w.close()
    rms=math.sqrt(sum(v*v for v in data)/len(data))
    zcr=sum(1 for i in range(1,len(data)) if (data[i-1]<0)!=(data[i]<0))/len(data)
    print(f"  new b2.wav: {dur:.2f}s  rms={rms:.1f}  zcr={zcr:.4f}  peak={max(abs(min(data)),abs(max(data)))}")

# persist rephrased text so durations.json/captions stay consistent (optional)
json.dump(SCRIPT, open(os.path.join(HERE, "script.json"), "w"), indent=2)
print("script.json updated with rephrased b2")
