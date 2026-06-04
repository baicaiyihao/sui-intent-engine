#!/usr/bin/env python3
"""
render_captions.py — render each SRT entry as a transparent PNG with
white text + black outline, bottom-center positioned, sized to match
the video resolution.

Output: out/caption_NN.png (one per SRT entry), where NN is the
1-based entry index. Each PNG is RGBA, full video resolution, with
text drawn at the bottom-center and the rest fully transparent.

We need this because ffmpeg 8.1.1 on macOS (brew) is built without
--enable-libass / --enable-libfreetype, so the `subtitles=` filter
is unavailable. We pre-render text into PNGs and use `overlay` with
`enable='between(t,start,end)'` instead.

Usage:
  python3 render_captions.py <video_path> <srt_path> <out_dir>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# Try a small font stack. We prefer Helvetica-Bold (system), then Arial Bold
# (Supplemental), then DejaVuSans-Bold (brew). Fall back to PIL default.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
    "/opt/homebrew/share/fonts/DejaVuSans-Bold.ttf",
]


def find_font() -> str:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError("No usable bold font found on this system")


def srt_time_to_seconds(s: str) -> float:
    """'00:00:03,000' -> 3.0"""
    h, m, rest = s.split(":")
    sec, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(sec) + int(ms) / 1000.0


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    """Return [(start, end, caption), ...] from SRT text."""
    out = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip() != ""]
        if len(lines) < 2:
            continue
        # Skip the numeric index line (first line)
        timing_line = next((ln for ln in lines if "-->" in ln), None)
        if not timing_line:
            continue
        start_s, _, end_s = timing_line.partition("-->")
        start = srt_time_to_seconds(start_s.strip())
        end = srt_time_to_seconds(end_s.strip())
        # All remaining lines (after the timing line) are the caption body
        body_lines = [ln for ln in lines if "-->" not in ln and not ln.strip().isdigit()]
        caption = " ".join(ln.strip() for ln in body_lines)
        out.append((start, end, caption))
    return out


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """Word-wrap `text` to fit `max_width` pixels at `font` size."""
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for word in words:
        candidate = " ".join(cur + [word])
        bbox = draw.textbbox((0, 0), candidate, font=font, stroke_width=0)
        if bbox[2] - bbox[0] <= max_width:
            cur.append(word)
        else:
            if cur:
                lines.append(" ".join(cur))
            # If a single word is wider than max_width, it still goes on its own line
            cur = [word]
    if cur:
        lines.append(" ".join(cur))
    return lines


def render_caption_png(
    caption: str,
    out_path: Path,
    width: int,
    height: int,
    font: ImageFont.FreeTypeFont,
    *,
    margin_bottom_ratio: float = 0.07,
    side_margin_ratio: float = 0.06,
    stroke_px: int = 4,
    line_spacing: int = 8,
) -> None:
    """Render a single caption into a transparent RGBA PNG of (width,height)."""
    # Pick a font size proportional to the video height. 1920x1080 → 38pt
    font_size = max(28, int(height * 0.035))
    font = ImageFont.truetype(font.path, font_size) if hasattr(font, "path") else font

    max_text_w = int(width * (1 - 2 * side_margin_ratio))

    # Temporary image to measure text (can be 1x1 — we only need bbox)
    measure = Image.new("RGBA", (1, 1))
    mdraw = ImageDraw.Draw(measure)

    lines = wrap_text(mdraw, caption, font, max_text_w)

    # Measure each line and the total text block
    line_bboxes = [mdraw.textbbox((0, 0), ln, font=font, stroke_width=stroke_px) for ln in lines]
    block_w = max((b[2] - b[0]) for b in line_bboxes)
    line_heights = [b[3] - b[1] for b in line_bboxes]
    block_h = sum(line_heights) + line_spacing * (len(lines) - 1)

    # Canvas (transparent)
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(canvas)

    # Position: horizontally centered, vertically near bottom
    x = (width - block_w) // 2
    y = int(height * (1 - margin_bottom_ratio)) - block_h

    # Draw each line with stroke (outline) + fill
    cur_y = y
    for ln, bbox in zip(lines, line_bboxes):
        # bbox = (l, t, r, b). The text may be offset by negative l, t from
        # PIL's text rendering quirks. Offset our x to compensate.
        ln_w = bbox[2] - bbox[0]
        ln_h = bbox[3] - bbox[1]
        ln_x = x + (block_w - ln_w) // 2 - bbox[0]
        ln_y = cur_y - bbox[1]
        cdraw.text(
            (ln_x, ln_y),
            ln,
            font=font,
            fill=(255, 255, 255, 255),
            stroke_width=stroke_px,
            stroke_fill=(0, 0, 0, 255),
        )
        cur_y += ln_h + line_spacing

    canvas.save(out_path, "PNG", optimize=True)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: render_captions.py <video_path> <srt_path> <out_dir>", file=sys.stderr)
        return 1

    video_path = Path(sys.argv[1])
    srt_path = Path(sys.argv[2])
    out_dir = Path(sys.argv[3])
    out_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        print(f"missing video: {video_path}", file=sys.stderr)
        return 1
    if not srt_path.exists():
        print(f"missing srt: {srt_path}", file=sys.stderr)
        return 1

    # Probe video resolution with ffprobe (avoids importing av/imageio)
    import subprocess
    out = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0", str(video_path),
    ]).decode().strip()
    w_str, h_str = out.split("x")
    width, height = int(w_str), int(h_str)
    print(f"[captions] video {width}x{height}")

    font_path = find_font()
    font = ImageFont.truetype(font_path, 40)
    print(f"[captions] font: {font_path}")

    entries = parse_srt(srt_path.read_text())
    print(f"[captions] {len(entries)} entries from srt")

    for i, (start, end, caption) in enumerate(entries, 1):
        png_path = out_dir / f"caption_{i:02d}.png"
        render_caption_png(caption, png_path, width, height, font)
        print(f"[captions] {i:02d}  {start:5.2f}-{end:5.2f}s  → {png_path.name}  ({len(caption)} chars)")

    # Write timings json for the assembler
    import json
    timings = {
        i: {"start": s, "end": e, "png": str(out_dir / f"caption_{i:02d}.png")}
        for i, (s, e, _) in enumerate(entries, 1)
    }
    (out_dir / "caption_timings.json").write_text(json.dumps(timings, indent=2))
    print(f"[captions] timings → {out_dir / 'caption_timings.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
