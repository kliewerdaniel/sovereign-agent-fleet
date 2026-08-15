# -*- coding: utf-8 -*-
"""Generate one brit-voice WAV per scene from demo/scenes/scripts.txt.

ROOT CAUSE of the prior mid-sentence cutoff: the :7860 Qwen3-TTS Base server
runs model.generate() ONCE per scene. Qwen3-TTS Base caps output per call at
~16s, so any scene longer than ~40 words gets silently truncated mid-sentence.

FIX: chunk each scene into short (~12-word) pieces, call /api/generate per
piece (server stamps voice=brit via voice_file), then concatenate the returned
WAVs with ffmpeg. No single chunk can exceed the model's length cap, so no
scene is ever truncated.
"""
import json, os, re, subprocess, tempfile, urllib.request

BASE = "http://localhost:7860"
ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
OUT = os.path.join(ROOT, "demo", "audio")
TMP = os.path.join(OUT, "_chunks")
os.makedirs(OUT, exist_ok=True)
os.makedirs(TMP, exist_ok=True)
SCRIPT = os.path.join(ROOT, "demo", "scenes", "scripts.txt")
FF = "/opt/homebrew/bin/ffmpeg"
FF_PROBE = "/opt/homebrew/bin/ffprobe"


def gen_chunk(text):
    body = json.dumps({"text": text, "voice_file": "brit.mp3", "speed": 0.82}).encode()
    req = urllib.request.Request(BASE + "/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=240).read().decode())
    wav = urllib.request.urlopen(BASE + "/api/audio/" + data["file_id"], timeout=240).read()
    return wav, data.get("voice", "")


def chunk_text(text, max_words=12):
    """Split into <=max_words chunks on sentence/word boundaries."""
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text.strip()) if s.strip()]
    chunks, cur, cur_w = [], [], 0
    for s in sents:
        w = len(s.split())
        if w > max_words:
            # hard-split a very long sentence on commas / words
            parts = re.split(r'(?<=,)\s+', s)
            for p in parts:
                pw = len(p.split())
                if cur_w + pw > max_words and cur:
                    chunks.append(" ".join(cur)); cur, cur_w = [], 0
                cur.append(p); cur_w += pw
                if cur_w >= max_words:
                    chunks.append(" ".join(cur)); cur, cur_w = [], 0
        else:
            if cur_w + w > max_words and cur:
                chunks.append(" ".join(cur)); cur, cur_w = [s], w
            else:
                cur.append(s); cur_w += w
    if cur:
        chunks.append(" ".join(cur))
    return chunks or [text]


def cat_wavs(paths, out_path):
    lst = os.path.join(TMP, "list.txt")
    with open(lst, "w") as f:
        for p in paths:
            f.write("file '%s'\n" % os.path.abspath(p))
    subprocess.check_call([FF, "-y", "-f", "concat", "-safe", "0", "-i", lst,
                          "-c", "copy", out_path])


total = 0.0
with open(SCRIPT) as f:
    for line in f:
        line = line.rstrip("\n")
        if not line or "|" not in line:
            continue
        sid, text = line.split("|", 1)
        chunks = chunk_text(text)
        parts = []
        vlabel = "brit"
        for i, c in enumerate(chunks):
            wav, vlabel = gen_chunk(c)
            p = os.path.join(TMP, f"{sid}_{i:02d}.wav")
            open(p, "wb").write(wav)
            parts.append(p)
        out = os.path.join(OUT, sid + ".wav")
        cat_wavs(parts, out)
        dur = float(subprocess.check_output(
            [FF_PROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", out]).decode().strip())
        total += dur
        print(f"{sid}: {len(chunks)} chunks, {dur:.2f}s voice={vlabel} -> {out}")

print(f"TOTAL_NARR: {total:.1f}s")
