#!/usr/bin/env bash
# Assemble the 1080p fleet demo: per-scene zoompan + overlay callout + VO, then concat.
# Screenshots live in ../web/shots; callouts/vo in this dir.
set -uo pipefail
cd "$(dirname "$0")"
SHOTS=./shots; CALL=callouts; VO=vo; SEG=segs; FPS=30
rm -rf "$SEG"; mkdir -p "$SEG"
dur () { PYTHONPATH= /usr/bin/python3 -c "import json;print(json.load(open('$VO/durations.json'))['$1'])"; }

make_scene () {
  local img="$1" ov="$2" out="$3" d="$4" aud="$5"
  local n=$(( ${d%.*} * FPS ))
  ffmpeg -y -hide_banner -loglevel error \
    -loop 1 -framerate $FPS -i "$img" \
    -loop 1 -framerate $FPS -i "$ov" \
    -i "$aud" \
    -filter_complex "\
[0:v]scale=2560:1440:force_original_aspect_ratio=increase:flags=lanczos,\
zoompan=z='min(1.08,1+0.08*on/${n})':d=1:s=1920x1080:\
x='iw/2-(iw/zoom)/2':y='ih/2-(ih/zoom)/2':fps=$FPS,\
scale=1920:1080:flags=lanczos,setsar=1[v];\
[1:v]format=rgba,colorchannelmixer=aa=1[ovl];\
[v][ovl]overlay=0:0:shortest=1[outv]" \
    -map "[outv]" -map 2:a \
    -c:v libx264 -pix_fmt yuv420p -crf 20 -preset medium \
    -c:a aac -b:a 192k -movflags +faststart -t "$d" "$out"
}

for s in s1 s2 s3 s4 s5 s6 s7; do
  [ -f "$VO/$s.mp3" ] || continue
  make_scene "$SHOTS/$s.png" "$CALL/$s.png" "$SEG/$s.mp4" "$(dur $s)" "$VO/$s.mp3"
  echo "scene $s -> $SEG/$s.mp4"
done

: > $SEG/list.txt
for s in s1 s2 s3 s4 s5 s6 s7; do
  [ -f "$SEG/$s.mp4" ] && echo "file '$PWD/$SEG/$s.mp4'" >> $SEG/list.txt
done
ffmpeg -y -hide_banner -loglevel error -f concat -safe 0 -i $SEG/list.txt -c copy demo_1080p.mp4
echo "=== built demo_1080p.mp4 ==="
ffprobe -v error -show_entries format=duration -show_entries stream=codec_name,width,height -of default=nw=1 demo_1080p.mp4
