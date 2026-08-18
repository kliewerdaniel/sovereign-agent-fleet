import wave, struct, numpy as np, glob, os

def analyze(path):
    w = wave.open(path,'rb'); fr=w.getframerate(); n=w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32); w.close()
    x = x - x.mean()
    # RMS
    rms = np.sqrt(np.mean(x**2))
    # high-freq energy ratio (>4kHz) via FFT
    X = np.fft.rfft(x * np.hanning(len(x)))
    freqs = np.fft.rfftfreq(len(x), 1/fr)
    mag = np.abs(X)
    total = mag.sum()
    hf = mag[freqs > 4000].sum()
    hf_ratio = hf/total if total>0 else 0
    # spectral flatness (geometric/arithmetic mean of power) — low = tonal/clean, high = noise/garble
    power = mag**2 + 1e-12
    g = np.exp(np.mean(np.log(power)))
    a = np.mean(power)
    flatness = g/a
    # crest factor (peak/rms) — high = spikes/transients/clipping-ish
    crest = (np.max(np.abs(x)) / rms) if rms>0 else 0
    return rms, hf_ratio, flatness, crest

for p in sorted(glob.glob('audio/b*.wav')):
    rms, hf, flat, crest = analyze(p)
    print(f"{os.path.basename(p):10s} rms={rms:8.1f}  hf_ratio={hf:.4f}  flatness={flat:.5f}  crest={crest:6.1f}")
