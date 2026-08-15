# -*- coding: utf-8 -*-
"""TTS audio QC gate: transcribe each scene wav, word-ratio check vs script."""
import os, subprocess, sys
ROOT = "/Users/danielkliewer/Documents/Projects/sovereign-agent-fleet"
AU = os.path.join(ROOT, "demo", "audio")
SCRIPT = os.path.join(ROOT, "demo", "scenes", "scripts.txt")
PY = "/opt/homebrew/bin/python3.14"

# intended narration keyed by scene id
expected = {}
for line in open(SCRIPT):
    line = line.rstrip("\n")
    if not line or "|" not in line:
        continue
    sid, text = line.split("|", 1)
    expected[sid] = text

# standalone transcriber
TR = '''import sys
def main():
    wav = sys.argv[1]
    from mlx_audio.stt import load as load_stt
    model = load_stt("mlx-community/whisper-large-v3-turbo-asr-fp16")
    res = model.generate(wav)
    print(getattr(res, "text", str(res)).strip())
if __name__ == "__main__":
    main()
'''
TR_PATH = os.path.join(ROOT, "demo", "scenes", "_stt_check.py")
open(TR_PATH, "w").write(TR)

all_ok = True
for sid in sorted(expected):
    wav = os.path.join(AU, sid + ".wav")
    if not os.path.exists(wav):
        print(f"{sid}: MISSING wav"); all_ok = False; continue
    try:
        text = subprocess.run([PY, TR_PATH, wav], capture_output=True, text=True,
                              timeout=300, env={k: v for k, v in os.environ.items()
                                               if k not in ("PYTHONPATH", "PYTHONHOME")}).stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"{sid}: TRANSCRIBE TIMEOUT"); all_ok = False; continue
    wc, exp = len(text.split()), len(expected[sid].split())
    ratio = wc / exp if exp else 0
    ok = (wc >= 3) and (0.5 <= ratio <= 2.2)
    all_ok = all_ok and ok
    print(f"{sid}: {'PASS' if ok else 'FAIL'} words={wc} expected~{exp} ratio={ratio:.2f} | {text[:80]!r}")

print("\nAUDIO_QC:", "ALL PASS" if all_ok else "FAILURES PRESENT")
sys.exit(0 if all_ok else 1)
