#!/usr/bin/env bash
# assemble.sh — combine screen recording + narration audio + burned-in captions
#
# We can't use ffmpeg's `subtitles=` filter because ffmpeg 8.1.1 on macOS
# (brew) is built without --enable-libass / --enable-libfreetype. So we
# pre-render each SRT entry as a transparent PNG via render_captions.py
# and composite them with the `overlay` filter using
# `enable='between(t,start,end)'`.
#
# Inputs (all in scripts/demo/out/):
#   - narration_full.wav   (TTS-mixed, 97s)
#   - screen_capture.mov   (from record_screen.sh, ~98s)
#   - demo.srt             (subtitle timings)
#
# Output: scripts/demo/out/demo.mp4

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/scripts/demo/out"

AUDIO="$OUT/narration_full.wav"
VIDEO="$OUT/screen_capture.mov"
SRT="$OUT/demo.srt"
CAPTIONS_DIR="$OUT/captions"
OUTPUT="$OUT/demo.mp4"
PYTHON="/Users/stom698/miniconda3/envs/crawl4ai/bin/python"

for f in "$AUDIO" "$VIDEO" "$SRT"; do
  [ -f "$f" ] || { echo "[assemble] missing $f"; exit 1; }
done

echo "[assemble] video:  $VIDEO"
echo "[assemble] audio:  $AUDIO"
echo "[assemble] srt:    $SRT"

# ---------- 1. render caption PNGs (idempotent) ----------
echo "[assemble] rendering caption PNGs..."
"$PYTHON" "$ROOT/scripts/demo/render_captions.py" "$VIDEO" "$SRT" "$CAPTIONS_DIR" >/dev/null

# Count entries
N=$(grep -c "^[0-9]\+$" "$SRT" || true)
[ -z "$N" ] || [ "$N" -eq 0 ] && { echo "[assemble] no entries in $SRT"; exit 1; }
echo "[assemble] $N caption entries"

# ---------- 2. build ffmpeg inputs and filter graph ----------
# Inputs:
#   0 = video
#   1 = audio
#   2..(N+1) = caption PNGs (loop 1, framerate 25 to match screencapture)
#
# Filter graph:
#   For each caption i:
#     [in_i:v] format=rgba, scale=W:H [cap_i]
#     [running][cap_i] overlay=enable='between(t,start,end)':x=0:y=0 [next_running]

# Probe video resolution
VIDEO_W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=s=x:p=0 "$VIDEO")
VIDEO_H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=s=x:p=0 "$VIDEO")
echo "[assemble] video resolution: ${VIDEO_W}x${VIDEO_H}"

# Build input args: video, audio, then N caption PNGs (loop 1, 25fps)
INPUT_ARGS=(-i "$VIDEO" -i "$AUDIO")
for i in $(seq 1 "$N"); do
  PNG="$CAPTIONS_DIR/caption_$(printf '%02d' "$i").png"
  [ -f "$PNG" ] || { echo "[assemble] missing $PNG"; exit 1; }
  INPUT_ARGS+=(-loop 1 -framerate 25 -i "$PNG")
done

# Parse SRT timings to bash variables (one per line: "START END")
# We use awk to be portable across bash 3.2 (macOS) and bash 5+ (linux).
eval "$(
  "$PYTHON" - "$SRT" <<'PY' | grep -E '^CAPTION_[0-9]+_(START|END)='
import re, sys
from pathlib import Path
srt = Path(sys.argv[1]).read_text()
def t(s):
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h)*3600 + int(m)*60 + int(sec) + int(ms)/1000.0
i = 0
for block in re.split(r"\n\s*\n", srt.strip()):
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        continue
    timing = next((ln for ln in lines if "-->" in ln), None)
    if not timing:
        continue
    s, _, e = timing.partition("-->")
    i += 1
    print(f'CAPTION_{i}_START={t(s.strip())}')
    print(f'CAPTION_{i}_END={t(e.strip())}')
PY
)"

# Build filter graph
FILTER=""
PREV="[0:v]"
for i in $(seq 1 "$N"); do
  IN_IDX=$((i + 1))   # 0=video, 1=audio, 2..N+1=PNGs
  # Read timing for this caption (1-based)
  S_VAR="CAPTION_${i}_START"
  E_VAR="CAPTION_${i}_END"
  S="${!S_VAR}"
  E="${!E_VAR}"
  # Format input: ensure rgba + scale to match video
  FILTER+="[${IN_IDX}:v]format=rgba,scale=${VIDEO_W}:${VIDEO_H}:flags=fast_bilinear[cap${i}];"
  if [ "$i" -eq "$N" ]; then
    # last one — produce [vout]
    FILTER+="${PREV}[cap${i}]overlay=enable='between(t,${S},${E})':x=0:y=0:shortest=0[vout]"
  else
    FILTER+="${PREV}[cap${i}]overlay=enable='between(t,${S},${E})':x=0:y=0:shortest=0[v${i}];"
    PREV="[v${i}]"
  fi
done

# Build the ffmpeg command
echo "[assemble] running ffmpeg (this takes ~30s)..."
ffmpeg -y -loglevel error \
  "${INPUT_ARGS[@]}" \
  -filter_complex "$FILTER" \
  -map "[vout]" -map 1:a \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  -shortest \
  "$OUTPUT"

echo "[assemble] done → $OUTPUT"
ls -la "$OUTPUT"
ffprobe "$OUTPUT" 2>&1 | grep -E "Duration|Stream" | head -3
