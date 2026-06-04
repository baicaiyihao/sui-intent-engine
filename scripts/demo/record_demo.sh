#!/usr/bin/env bash
# record_demo.sh — record the SUI Intent Engine demo video end-to-end
#
# Pipeline:
#   1. Pre-mix TTS audio (per-section wavs → narration_full.wav with 3s gaps)
#   2. Start the stack via ./start.sh
#   3. Open Chrome at http://localhost:3000 (fullscreen)
#   4. Record the screen for ~102s (you navigate based on the cue sheet)
#   5. assemble.sh combines: screen capture + TTS audio + burned-in captions
#
# Output: scripts/demo/out/demo.mp4 + scripts/demo/out/demo.srt

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT="$ROOT/scripts/demo/out"
mkdir -p "$OUT"

# ---------- 1. verify TTS exists ----------
if [ ! -f "$OUT/00_intro.wav" ] || [ ! -f "$OUT/timing.json" ]; then
  echo "[record] TTS audio missing — run:  python scripts/demo/tts_generate.py"
  exit 1
fi

# Use the conda env's python for any python helpers
PYTHON_BIN="${PYTHON_BIN:-/Users/stom698/miniconda3/envs/crawl4ai/bin/python}"

# ---------- 2. pre-mix the TTS audio + build srt ----------
echo "[record] pre-mixing TTS audio with 3s silence gaps..."

# Read timings
python3 - <<PY
import json, subprocess
from pathlib import Path

OUT = Path("$OUT")
timing = json.loads((OUT / "timing.json").read_text())
order = ["00_intro", "10_stack", "20_landing", "30_ai", "40_fee", "50_close"]

# Generate silence wav (24kHz mono, 3 seconds)
silence_wav = OUT / "_silence_3s.wav"
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
    "-t", "3", "-acodec", "pcm_s16le", str(silence_wav),
], check=True)

# Build concat list: silence, section 1, silence, section 2, ...
concat_list = OUT / "_concat.txt"
with concat_list.open("w") as f:
    f.write(f"file '{silence_wav}'\n")  # 3s lead-in
    for sid in order:
        f.write(f"file '{OUT / (sid + \".wav\")}'\n")
        f.write(f"file '{silence_wav}'\n")  # 3s gap after each

# Concatenate
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    "-f", "concat", "-safe", "0", "-i", str(concat_list),
    "-c", "copy", str(OUT / "narration_full.wav"),
], check=True)

# Compute srt timings (each section starts after lead-in + previous sections + gaps)
LEAD = 3.0
GAP = 3.0
cur = LEAD
srt_lines = []
for i, sid in enumerate(order, 1):
    d = timing[sid]["duration_sec"]
    start = cur
    end = cur + d
    cur = end + GAP
    def fmt(t):
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        ms = int((t - int(t)) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    text = timing[sid]["text"]
    srt_lines.append(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text}\n")

(OUT / "demo.srt").write_text("\n".join(srt_lines))
total = cur - GAP  # last section has no trailing gap
print(f"[record] narration total: {total:.1f}s (lead-in {LEAD}s + 6 sections + gaps)")
print(f"[record] srt: {OUT / 'demo.srt'}")

# Write the cue sheet (what the human should do on screen)
cues = [
    ("00_intro",  3.0,  13.5, "Just show the terminal title. Nothing to click."),
    ("10_stack", 16.5,  33.0, "Switch to a terminal, show the ./start.sh command running and the 3 'up' lines."),
    ("20_landing", 36.0, 48.5, "Show the landing page at http://localhost:3000 — scroll through the 4-step flow."),
    ("30_ai",    51.5, 70.5, "Click 'AI 策略' tab. Show the chat panel. Optionally type a quick question."),
    ("40_fee",   73.5, 85.5, "Show a SuiVision page (link in README) or just terminal with the tx hash 4jGNB1W56Ehfy73nHEyfrK48XxQmWkzcDePVPxehvG1D"),
    ("50_close", 88.5, 96.0, "Back to the landing page. Stay still for the closing tagline."),
]
cues_path = OUT / "cues.txt"
with cues_path.open("w") as f:
    f.write("Section cues — when to switch what's on screen\n")
    f.write(f"Total demo length: ~{total:.0f}s\n")
    f.write("=" * 60 + "\n")
    for sid, s, e, action in cues:
        def fmt(t):
            m = int(t // 60)
            s = int(t % 60)
            return f"{m:02d}:{s:02d}"
        f.write(f"  {sid}  {fmt(s)}–{fmt(e)}   {action}\n")
print(f"[record] cues: {cues_path}")
PY

# ---------- 3. ensure stack is running ----------
if ! curl -s -o /dev/null --max-time 2 http://localhost:3000/; then
  echo "[record] stack not running — starting via ./start.sh"
  ./start.sh
else
  echo "[record] stack already up"
fi

# ---------- 4. open Chrome at fullscreen ----------
echo "[record] opening Chrome to http://localhost:3000 ..."
osascript <<'OSA' 2>/dev/null || true
tell application "Google Chrome"
  activate
  if (count of windows) = 0 then make new window
  set URL of active tab of front window to "http://localhost:3000/"
end tell
delay 1
tell application "System Events"
  keystroke "f" using {command down, control down}  -- fullscreen (Cmd+Ctrl+F)
end tell
OSA
sleep 3   # give Chrome time to settle

# ---------- 5. record screen ----------
DURATION=102   # narration is 99.9s; record 2s extra for slop, then -shortest trims
RECORDING="$OUT/screen_capture.mov"
echo "[record] recording screen for ${DURATION}s — follow the cue sheet in $OUT/cues.txt"
echo "[record] press Ctrl-C to stop early"
screencapture -V "$DURATION" -x -g "$RECORDING" &
REC_PID=$!
trap "kill $REC_PID 2>/dev/null; wait $REC_PID 2>/dev/null; true" INT TERM
wait $REC_PID
echo "[record] capture done: $RECORDING"

# ---------- 6. assemble mp4 with audio + burned-in captions ----------
echo "[record] assembling final mp4 (this takes ~30s)..."
"$ROOT/scripts/demo/assemble.sh"
echo "[record] done → $OUT/demo.mp4"
