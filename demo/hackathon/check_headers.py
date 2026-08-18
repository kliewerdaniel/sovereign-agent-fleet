import wave, glob, os
for p in sorted(glob.glob('audio/b*.wav')):
    w = wave.open(p,'rb')
    print(os.path.basename(p),
          "ch:", w.getnchannels(),
          "sw:", w.getsampwidth(),
          "fr:", w.getframerate(),
          "nframes:", w.getnframes(),
          "dur:", round(w.getnframes()/w.getframerate(),2))
    w.close()
print("--- final video audio ---")
w = wave.open('final_audio.wav','rb')
print("ch:", w.getnchannels(), "sw:", w.getsampwidth(), "fr:", w.getframerate())
w.close()
