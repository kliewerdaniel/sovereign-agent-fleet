import wave, struct, math

def stats(path):
    w = wave.open(path, 'rb')
    n = w.getnframes()
    fr = w.getframerate()
    ch = w.getnchannels()
    sw = w.getsampwidth()
    raw = w.readframes(n)
    w.close()
    if sw == 2:
        fmt = '<%dh' % (n*ch)
        data = struct.unpack(fmt, raw)
    else:
        return {'err': 'width'}
    peak = max(abs(min(data)), abs(max(data)))
    # RMS
    s = 0.0
    for v in data:
        s += v*v
    rms = math.sqrt(s/len(data)) if data else 0
    # clipping: fraction of samples within 1% of full scale
    fs = 32767
    clip = sum(1 for v in data if abs(v) > 0.99*fs) / len(data)
    # zero crossings (speech has moderate rate; distortion/noise => high or flat)
    zc = 0
    for i in range(1, len(data)):
        if (data[i-1] < 0) != (data[i] < 0):
            zc += 1
    zcr = zc / len(data)
    dur = n/fr
    return {'rms': round(rms,1), 'peak': peak, 'clip%': round(clip*100,2),
            'zcr': round(zcr,4), 'dur': round(dur,2), 'n': n}

import glob, os
for p in sorted(glob.glob('audio/b*.wav')):
    print(os.path.basename(p), stats(p))
