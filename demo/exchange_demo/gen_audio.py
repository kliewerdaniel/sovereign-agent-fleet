"""Generate Brit-voice narration per beat via local Piper TTS -> audio/<beat>.wav
and durations.json.

Switched off qwenTTS (HTTP server wedged/deadlocked intermittently). Piper is a
local CLI, fully deterministic, no server, no flakiness. Output is resampled to
24000 Hz mono pcm_s16le to match the b1-b4 WAVs already produced by qwenTTS so
assemble.py can concat everything uniformly.

Duration is measured from the real output WAV via ffprobe (not trusted metadata).
"""
import json
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
VO = os.path.join(HERE, "audio")
os.makedirs(VO, exist_ok=True)

PIPER = "/Users/danielkliewer/.hermes/hermes-agent/venv/bin/piper"
VOICE_DIR = "/Users/danielkliewer/piper_voices"
VOICE_ONNX = os.path.join(VOICE_DIR, "en_GB-northern_english_male-medium.onnx")
# target spec to match b1-b4 (qwenTTS 24kHz mono pcm_s16le)
TARGET_RATE = 24000
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"

script = json.load(open(os.path.join(HERE, "script.json")))
durations = {}
if os.path.exists(os.path.join(HERE, "durations.json")):
    durations = json.load(open(os.path.join(HERE, "durations.json")))

import re
SENT_RE = re.compile(r"(?<=[.!?])\s+")


def split_words(text, max_words):
    words = text.split()
    return [" ".join(words[i:i + max_words]) for i in range(0, len(words), max_words)]


# chunk budget: Piper is cheap/deterministic, so we only need to keep sentences
# readable. 35 words per chunk is fine (no server to wedge).
BEAT_MAXW = {"b1": 35, "b2": 35, "b3": 35, "b4": 35, "b5": 35, "b6": 35}


def chunk(text, max_words=35):
    parts = SENT_RE.split(text)
    chunks, cur = [], ""
    for p in parts:
        if len((cur + " " + p).strip().split()) > max_words and cur:
            chunks.append(cur.strip()); cur = p
        else:
            cur = (cur + " " + p).strip()
    if cur:
        chunks.append(cur.strip())
    flat = []
    for c in chunks:
        if len(c.split()) > max_words:
            flat.extend(split_words(c, max_words))
        else:
            flat.append(c)
    return [c for c in flat if c]


def _piper_wav(text, out_path):
    """Run Piper, resample to target spec, return nothing (writes out_path)."""
    raw = out_path + ".raw.wav"
    p = subprocess.run(
        [PIPER, "-m", VOICE_ONNX, "-f", raw],
        input=text, capture_output=True, text=True,
    )
    if p.returncode != 0:
        raise RuntimeError(f"piper failed({p.returncode}): {p.stderr[:200]}")
    # resample 22.05k -> 24k mono pcm_s16le to match b1-b4
    subprocess.run([
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", raw, "-ar", str(TARGET_RATE), "-ac", "1",
        "-c:a", "pcm_s16le", out_path,
    ], check=True)
    os.remove(raw)


def _duration(path):
    res = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    return float(res.stdout.strip())


def generate_beat(bid, text):
    chunks = chunk(text, BEAT_MAXW.get(bid, 35))
    part_paths = []
    total = 0.0
    for i, c in enumerate(chunks):
        p = os.path.join(VO, f"_{bid}_{i}.wav")
        _piper_wav(c, p)
        dur = _duration(p)
        total += dur
        part_paths.append(p)
    final = os.path.join(VO, f"{bid}.wav")
    if len(part_paths) == 1:
        os.replace(part_paths[0], final)
    else:
        listf = os.path.join(VO, f"_{bid}_list.txt")
        with open(listf, "w") as lf:
            for p in part_paths:
                lf.write(f"file '{os.path.abspath(p)}'\n")
        subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "concat", "-safe", "0", "-i", listf,
                        "-c", "copy", final], check=True)
        for p in part_paths + [listf]:
            os.remove(p)
    durations[bid] = round(total, 3)
    print(f"{bid}: {len(chunks)} chunks, {total:.2f}s -> audio/{bid}.wav", flush=True)


failed = []
ONLY = os.environ.get("ONLY_BEAT")
items = script["monologue"].items()
if ONLY:
    items = [(k, v) for k, v in items if k == ONLY]
for bid, text in items:
    final = os.path.join(VO, f"{bid}.wav")
    if os.path.exists(final):
        print(f"{bid}: already generated, skip", flush=True)
        continue
    try:
        generate_beat(bid, text)
    except Exception as e:  # noqa: BLE001
        print(f"{bid}: FAILED -> {e}; will retry at end", flush=True)
        failed.append(bid)

# one more pass over failed beats
for bid in list(failed):
    final = os.path.join(VO, f"{bid}.wav")
    if os.path.exists(final):
        continue
    try:
        generate_beat(bid, script["monologue"][bid])
        failed.remove(bid)
    except Exception as e:  # noqa: BLE001
        print(f"{bid}: still FAILED -> {e}", flush=True)

json.dump(durations, open(os.path.join(HERE, "durations.json"), "w"), indent=2)
print("wrote durations.json:", durations, "failed:", failed, flush=True)
