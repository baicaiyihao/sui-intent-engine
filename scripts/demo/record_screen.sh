#!/usr/bin/env bash
# record_screen.sh — record the screen for ~98s
#
# Before running:
#   1. Make sure the stack is up:  ./start.sh
#   2. Open Chrome to http://localhost:3000
#   3. Have a terminal visible with ./start.sh output (for the 10_stack section)
#   4. Read scripts/demo/out/cues.txt — it tells you when to switch
#
# Output: scripts/demo/out/screen_capture.mov
# After: run ./assemble.sh to make the final mp4

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="$ROOT/scripts/demo/out"
mkdir -p "$OUT"

DURATION=102   # narration is 99.9s; record 2s extra for slop, then -shortest trims
RECORDING="$OUT/screen_capture.mov"

echo "[record] $DURATION s screen recording → $RECORDING"
echo "[record] open Chrome + follow $OUT/cues.txt"
echo "[record] press Ctrl-C to stop early"

# -V: video mode, -x: no sound, -g: show cursor
screencapture -V "$DURATION" -x -g "$RECORDING"
echo "[record] done → $RECORDING"
ls -la "$RECORDING"
