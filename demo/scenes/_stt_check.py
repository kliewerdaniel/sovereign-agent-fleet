import sys
def main():
    wav = sys.argv[1]
    from mlx_audio.stt import load as load_stt
    model = load_stt("mlx-community/whisper-large-v3-turbo-asr-fp16")
    res = model.generate(wav)
    print(getattr(res, "text", str(res)).strip())
if __name__ == "__main__":
    main()
