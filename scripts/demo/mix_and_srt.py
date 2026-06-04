#!/usr/bin/env python3
"""
mix_and_srt.py — concatenate the per-section WAV files with 3s silence gaps,
then emit a SRT that has one entry per narration section (not per silence).

Inputs: scripts/demo/out/<section_id>.wav  (one per narration section)
        scripts/demo/out/timing.json         (durations per section)
Outputs: scripts/demo/out/narration_full.wav
         scripts/demo/out/demo.srt
"""
import json
import subprocess
from pathlib import Path

OUT = Path(__file__).parent / "out"
TIMING = json.loads((OUT / "timing.json").read_text())

# Order from narration.txt
NARRATION = (Path(__file__).parent / "narration.txt").read_text()
sections = []
for line in NARRATION.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    sid, _ = line.split("|", 1)
    sections.append(sid.strip())

assert len(sections) == len(TIMING), f"section count mismatch: {len(sections)} vs {len(TIMING)}"
for sid in sections:
    assert sid in TIMING, f"missing {sid} in timing.json"

# Generate 3s silence once
SILENCE_WAV = OUT / "_silence_3s.wav"
if not SILENCE_WAV.exists():
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
        "-t", "3", str(SILENCE_WAV),
    ], check=True)

# Build concat list and SRT timings
concat_args = []
for i, sid in enumerate(sections):
    concat_args.extend(["-i", str(OUT / f"{sid}.wav")])
    if i < len(sections) - 1:
        concat_args.extend(["-i", str(SILENCE_WAV)])

# ffmpeg concat
filter_parts = []
for i in range(len(concat_args) // 2):
    filter_parts.append(f"[{i}:a]aresample=24000,aformat=sample_fmts=s16:channel_layouts=mono[a{i}]")
concat_inputs = "".join(f"[a{i}]" for i in range(len(concat_args) // 2))
filter_parts.append(f"{concat_inputs}concat=n={len(concat_args) // 2}:v=0:a=1[aout]")
filter_str = ";".join(filter_parts)

print(f"[mix] concatenating {len(sections)} sections with 3s silence gaps...")
subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    *concat_args,
    "-filter_complex", filter_str,
    "-map", "[aout]",
    "-c:a", "pcm_s16le",
    str(OUT / "narration_full.wav"),
], check=True)
print(f"[mix] wrote {OUT / 'narration_full.wav'}")

# SRT — one entry per section
# Timestamps: from t0=0, each section takes its duration, then 3s gap
def fmt_t(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec - int(sec)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

srt_blocks = []
t = 0.0
for sid in sections:
    dur = TIMING[sid]["duration_sec"]
    start = t
    end = t + dur
    srt_blocks.append(f"{len(srt_blocks) + 1}\n{fmt_t(start)} --> {fmt_t(end)}\n{sid.replace('_', ' ').upper()}\n")
    t = end + 3.0  # 3s silence gap

(OUT / "demo.srt").write_text("\n".join(srt_blocks))
total = t - 3.0  # last section has no trailing gap
print(f"[mix] wrote SRT, total duration: {total:.1f}s")
