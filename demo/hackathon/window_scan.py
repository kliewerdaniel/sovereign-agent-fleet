import wave, struct, numpy as np, glob, os

def window_scan(path, win=0.25):
    w = wave.open(path,'rb'); fr=w.getframerate(); n=w.getnframes()
    x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32); w.close()
    x = x - x.mean()
    step = int(win*fr); out=[]
    for s in range(0, len(x)-step, step):
        seg = x[s:s+step]
        rms = np.sqrt(np.mean(seg**2))
        if rms < 50:  # silence/quiet
            out.append((s/fr, rms, 0.0, 0.0)); continue
        X = np.fft.rfft(seg*np.hanning(len(seg))); mag=np.abs(X)+1e-9
        power=mag**2
        flat = np.exp(np.mean(np.log(power)))/np.mean(power)
        crest = np.max(np.abs(seg))/rms
        out.append((s/fr, round(rms,1), round(flat,4), round(crest,1)))
    return out, fr

for p in sorted(glob.glob('audio/b*.wav')):
    rows, fr = window_scan(p)
    # flag windows with abnormally high flatness (>0.06) or crest (>40) => garble
    flagged=[r for r in rows if r[2]>0.06 or r[3]>40]
    print("="*60); print(os.path.basename(p))
    if flagged:
        for t,rms,flat,crest in flagged:
            print(f"  t={t:6.2f}s  rms={rms:7.1f}  flatness={flat}  crest={crest}  <== SUSPECT")
    else:
        # print just the max-flatness window for context
        mx=max(rows, key=lambda r:r[2])
        print(f"  clean (peak flatness {mx[2]} at t={mx[0]:.2f}s, rms={mx[1]})")
