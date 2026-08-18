from faster_whisper import WhisperModel
import glob, os

model = WhisperModel("base", device="cpu", compute_type="int8")
for p in sorted(glob.glob('audio/b*.wav')):
    name = os.path.basename(p)
    segs, info = model.transcribe(p, beam_size=5)
    text = " ".join(s.text for s in segs).strip()
    print("="*70)
    print(name, "| lang:", info.language, "prob:", round(info.language_probability,2))
    print(text[:600])
