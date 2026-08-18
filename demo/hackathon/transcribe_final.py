from faster_whisper import WhisperModel
import wave, struct, math, json, os

DUR = json.load(open('durations.json'))
ORDER = list(DUR.keys())  # b1..b8 in order

w = wave.open('final_audio.wav','rb')
fr = w.getframerate(); n = w.getnframes()
data = struct.unpack('<%dh' % n, w.readframes(n))
w.close()

def seg_text(path):
    m = WhisperModel("base", device="cpu", compute_type="int8")
    segs, info = m.transcribe(path, beam_size=5)
    return " ".join(s.text for s in segs).strip(), info.language_probability

# split final_audio.wav into per-beat files at 24000Hz
pos = 0
for key in ORDER:
    d = int(round(DUR[key]*fr))
    seg = data[pos:pos+d]
    out = f'_final_{key}.wav'
    ow = wave.open(out,'wb'); ow.setnchannels(1); ow.setsampwidth(2); ow.setframerate(fr)
    ow.writeframes(struct.pack('<%dh'%len(seg), *seg)); ow.close()
    pos += d
    txt, lp = seg_text(out)
    print("="*70)
    print(key, "| len", round(DUR[key],2), "lang_prob", round(lp,2))
    print(txt[:500])
    os.remove(out)
