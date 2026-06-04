#!/usr/bin/env bash
# build_slideshow.sh — produce final demo.mp4 from 5 static screenshots
#
# Pipeline (single ffmpeg invocation):
#   - 6 image inputs (one per narration section), looped to fill duration
#   - 1 audio input (pre-mixed TTS narration_full.wav)
#   - Filter graph: black bg → 6 overlays each with enable='between(t,S,E)'
#     so the right image is shown for the right narration window
#   - 6 caption overlays (PIL-rendered, transparent PNG) on top
#
# Each image gets a window that includes its own section duration + the 3s
# silence gap that follows, so the screen doesn't flash during gaps.
#
# Output: scripts/demo/out/demo.mp4

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHOTS="$ROOT/scripts"
OUT="$ROOT/scripts/demo/out"

AUDIO="$OUT/narration_full.wav"
SRT="$OUT/demo.srt"
CAPTIONS_DIR="$OUT/captions"
OUTPUT="$OUT/demo.mp4"
PYTHON="/Users/stom698/miniconda3/envs/crawl4ai/bin/python"

for f in "$AUDIO" "$SRT" \
         "$SHOTS/demo_01_landing.png" "$SHOTS/demo_02_problem.png" \
         "$SHOTS/demo_03_stack.png" "$SHOTS/demo_03_ai.png" \
         "$SHOTS/demo_06_suivision.png" "$SHOTS/demo_07_roadmap.png" \
         "$SHOTS/demo_08_close.png"; do
  [ -f "$f" ] || { echo "[slideshow] missing $f"; exit 1; }
done

# Compute audio duration (used as the canvas / output duration)
AUDIO_DUR=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$AUDIO" | awk '{printf "%.3f", $1}')
echo "[slideshow] audio duration: ${AUDIO_DUR}s"

# ---------- 1. Re-render caption PNGs to match 1920x1080 ----------
echo "[slideshow] rendering caption PNGs..."
"$PYTHON" "$ROOT/scripts/demo/render_captions.py" \
  "$SHOTS/demo_01_landing.png" "$SRT" "$CAPTIONS_DIR" >/dev/null

# ---------- 2. Get image dimensions from the landing shot (they're all the same) ----------
IMG_W=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=s=x:p=0 "$SHOTS/demo_01_landing.png")
IMG_H=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=s=x:p=0 "$SHOTS/demo_01_landing.png")
echo "[slideshow] image ${IMG_W}x${IMG_H}"

# ---------- 3. Read SRT timings ----------
N=$(grep -c "^[0-9]\+$" "$SRT")
[ -z "$N" ] || [ "$N" -eq 0 ] && { echo "[slideshow] no srt entries"; exit 1; }

# Section id (00_intro, 10_stack, …) → image filename
# Read narration.txt to keep the order
NARRATION="$ROOT/scripts/demo/narration.txt"
eval "$(
  "$PYTHON" - "$NARRATION" <<'PY'
import re, sys, os
from pathlib import Path
text = Path(sys.argv[1]).read_text()
order = []
for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    sid = line.split("|", 1)[0].strip()
    order.append(sid)

# Map per the spec above
mapping = {
    "00_intro":   "demo_01_landing.png",
    "10_problem": "demo_02_problem.png",
    "20_stack":   "demo_03_stack.png",
    "30_landing": "demo_01_landing.png",
    "40_ai":      "demo_03_ai.png",
    "50_protocol":"demo_06_suivision.png",
    "60_roadmap": "demo_07_roadmap.png",
    "70_close":   "demo_08_close.png",
}
for sid in order:
    print(f'SHOT_{sid}={mapping.get(sid, "demo_01_landing.png")}')
PY
)"

# Read SRT times into bash vars
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

# Image input IDs (1..N), audio at 0, video output mapped from filter
# Inputs: 0=audio, 1..N=section images
# Build the ffmpeg command

INPUT_ARGS=(-i "$AUDIO")
for i in $(seq 1 "$N"); do
  # Get section id at position i
  read_section_id() {
    "$PYTHON" - "$NARRATION" "$i" <<'PY'
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
i = int(sys.argv[2])
n = 0
for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    n += 1
    if n == i:
        print(line.split("|", 1)[0].strip())
        break
PY
  }
  SID=$(read_section_id)
  IMG_VAR="SHOT_${SID}"
  IMG="$SHOTS/${!IMG_VAR}"
  INPUT_ARGS+=(-loop 1 -framerate 25 -i "$IMG")
done

# Filter graph: black bg → overlay each image at its time window → overlay captions
# ffmpeg filter chains are separated by ';'. We'll collect each chain into
# a list and join with ';' at the end — much easier to reason about than
# prepending/appending separators inside the loop.
CHAINS=()
# Chain 1: solid black background
CHAINS+=("color=black:size=${IMG_W}x${IMG_H}:duration=${AUDIO_DUR}:rate=25[bg]")

# Image overlays: each is its own chain "<prev>[imgN]overlay=...[vimgN]"
# The first chain takes [bg] as input, subsequent ones take [vimg(N-1)].
PREV="[bg]"
for i in $(seq 1 "$N"); do
  S_VAR="CAPTION_${i}_START"
  NEXT_S_VAR="CAPTION_$((i+1))_START"
  if [ "$i" -eq "$N" ]; then
    END_T="${AUDIO_DUR}"
  else
    END_T="${!NEXT_S_VAR}"
  fi
  START_T="${!S_VAR}"
  IN_IDX=$i
  # scale/format the image input first
  CHAINS+=("[${IN_IDX}:v]format=yuv420p,scale=${IMG_W}:${IMG_H}[img${i}]")
  # then overlay it on top of the running prev
  if [ "$i" -eq "$N" ]; then
    CHAINS+=("${PREV}[img${i}]overlay=enable='between(t,${START_T},${END_T})':x=0:y=0[vimg${i}]")
    LAST_IMG_TAG="[vimg${i}]"
  else
    CHAINS+=("${PREV}[img${i}]overlay=enable='between(t,${START_T},${END_T})':x=0:y=0[vimg${i}]")
    PREV="[vimg${i}]"
  fi
done

# Caption overlays on top of the last image layer
PREV="$LAST_IMG_TAG"
for i in $(seq 1 "$N"); do
  S_VAR="CAPTION_${i}_START"
  E_VAR="CAPTION_${i}_END"
  S="${!S_VAR}"
  E="${!E_VAR}"
  CAP_IDX=$((N + i))
  CHAINS+=("[${CAP_IDX}:v]format=rgba,scale=${IMG_W}:${IMG_H}[cap${i}]")
  if [ "$i" -eq "$N" ]; then
    CHAINS+=("${PREV}[cap${i}]overlay=enable='between(t,${S},${E})':x=0:y=0[vout]")
  else
    CHAINS+=("${PREV}[cap${i}]overlay=enable='between(t,${S},${E})':x=0:y=0[vcap${i}]")
    PREV="[vcap${i}]"
  fi
done

# Join all chains with ';'
FILTER=$(IFS=';'; echo "${CHAINS[*]}")

# Append caption PNG inputs
for i in $(seq 1 "$N"); do
  PNG="$CAPTIONS_DIR/caption_$(printf '%02d' "$i").png"
  INPUT_ARGS+=(-loop 1 -framerate 25 -i "$PNG")
done

echo "[slideshow] running ffmpeg (this takes ~30s)..."
ffmpeg -y -loglevel error \
  "${INPUT_ARGS[@]}" \
  -filter_complex "$FILTER" \
  -map "[vout]" -map 0:a \
  -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  -t "${AUDIO_DUR}" \
  "$OUTPUT"

echo "[slideshow] done → $OUTPUT"
ls -la "$OUTPUT"
ffprobe "$OUTPUT" 2>&1 | grep -E "Duration|Stream" | head -3
