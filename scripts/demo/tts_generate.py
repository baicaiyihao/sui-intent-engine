#!/usr/bin/env python3
"""
Generate TTS audio for each section in narration.txt using MiniMax TTS API.

Reads narration.txt (format: section_id|text), calls MiniMax /v1/t2a_v2
for each, strips the 1140-byte ID3v2 header (which ffmpeg can't parse),
and writes WAV files to out/<section_id>.wav.

Outputs:
  out/<section_id>.wav   per-section audio
  out/timing.json        {section_id: {duration_sec, file}} for the orchestrator
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# Load .env
ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / "src" / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("MINIMAX_API_KEY", "")
BASE_URL = os.environ.get("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
if not API_KEY:
    sys.exit("ERROR: MINIMAX_API_KEY not set in src/.env")

# TTS config
MODEL = "speech-02-hd"
VOICE = "English_PassionateWarrior"   # male, deep, professional
SAMPLE_RATE = 24000

OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)
NARRATION = Path(__file__).parent / "narration.txt"


def call_tts(text: str) -> bytes:
    """Call MiniMax TTS, return raw MP3 bytes (hex-decoded, ID3v2 stripped)."""
    payload = {
        "model": MODEL,
        "text": text,
        "stream": False,
        "voice_setting": {
            "voice_id": VOICE,
            "speed": 0.95,      # slightly slower for clarity
            "vol": 1.0,
            "pitch": 0,
        },
        "audio_setting": {
            "sample_rate": SAMPLE_RATE,
            "bitrate": 128000,
            "format": "mp3",
            "channel": 1,
        },
    }
    req = urllib.request.Request(
        f"{BASE_URL}/t2a_v2",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())

    if body.get("base_resp", {}).get("status_code", 0) != 0:
        raise RuntimeError(f"TTS error: {body.get('base_resp')}")

    audio_hex = body["data"]["audio"]
    raw = bytes.fromhex(audio_hex)

    # Strip the 1140-byte ID3v2 tag (MiniMax wraps with AIGC metadata that
    # breaks ffmpeg's MP3 parser)
    if raw[:3] == b"ID3":
        # ID3v2 size is a synchsafe integer in bytes 6-9
        size = (raw[6] << 21) | (raw[7] << 14) | (raw[8] << 7) | raw[9]
        mp3_start = 10 + size
        return raw[mp3_start:]
    return raw


def mp3_to_wav(mp3_bytes: bytes, wav_path: Path):
    """Use ffmpeg to convert MP3 to WAV (24kHz mono PCM)."""
    import subprocess
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "mp3", "-i", "pipe:0",
            "-ar", str(SAMPLE_RATE), "-ac", "1", "-f", "wav",
            str(wav_path),
        ],
        input=mp3_bytes,
        check=True,
    )


def get_wav_duration(wav_path: Path) -> float:
    import subprocess
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path),
    ]).decode().strip()
    return float(out)


def main():
    if not NARRATION.exists():
        sys.exit(f"missing {NARRATION}")

    sections = []
    for line in NARRATION.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sid, text = line.split("|", 1)
        sections.append((sid.strip(), text.strip()))

    print(f"[tts] generating {len(sections)} sections via MiniMax {MODEL} voice={VOICE}")
    timing = {}
    for sid, text in sections:
        print(f"[tts]   {sid} ({len(text)} chars)...", flush=True)
        t0 = time.time()
        mp3 = call_tts(text)
        wav_path = OUT_DIR / f"{sid}.wav"
        mp3_to_wav(mp3, wav_path)
        dur = get_wav_duration(wav_path)
        timing[sid] = {"duration_sec": round(dur, 2), "file": str(wav_path), "text": text}
        print(f"[tts]   {sid}: {dur:.2f}s  (took {time.time()-t0:.1f}s API+convert)")

    (OUT_DIR / "timing.json").write_text(json.dumps(timing, indent=2))
    total = sum(t["duration_sec"] for t in timing.values())
    print(f"[tts] done. total narration {total:.1f}s across {len(sections)} sections.")


if __name__ == "__main__":
    main()
