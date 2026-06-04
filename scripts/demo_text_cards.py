#!/usr/bin/env python3
"""
demo_text_cards.py — generate text-only PIL cards for sections that
need to communicate a list / story rather than show real UI.

Replaces the previous fake UI mockups. The cards only contain
typography, no fake buttons / bubbles / badges.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DEST = Path("/Users/stom698/git/QuantDinger/sui-intent-engine/scripts")
DEST.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BG = (10, 12, 18)
FG = (235, 235, 240)
DIM = (140, 145, 160)
ACCENT = (120, 220, 180)   # green
WARN = (255, 145, 90)      # orange
BLUE = (110, 195, 255)     # blue
PINK = (255, 140, 200)     # pink

# Fonts
MONO_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/Library/Fonts/Courier New Bold.ttf",
]
SANS_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def find(p_list: list[str]) -> str:
    for p in p_list:
        if Path(p).exists():
            return p
    raise RuntimeError(f"no font found in {p_list}")


def wrap(draw, text, font, max_w):
    words = text.split()
    lines, cur = [], []
    for w in words:
        c = " ".join(cur + [w])
        bb = draw.textbbox((0, 0), c, font=font)
        if bb[2] - bb[0] <= max_w:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def measure_block(d, lines, font, line_gap=14):
    h = 0
    w = 0
    for ln in lines:
        bb = d.textbbox((0, 0), ln, font=font)
        w = max(w, bb[2] - bb[0])
        h += (bb[3] - bb[1]) + line_gap
    return w, h - line_gap


def text_card(
    out_path: Path,
    *,
    eyebrow: str,
    title: str,
    body: list[str],
    accent: tuple[int, int, int] = ACCENT,
):
    """A clean typographic card. No fake UI.
    eyebrow: small uppercase tag
    title:   big H1
    body:    list of paragraph lines
    """
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    sans = find(SANS_CANDIDATES)
    mono = find(MONO_CANDIDATES)

    # Decorative left bar
    d.rectangle([0, 0, 6, H], fill=accent)

    # Eyebrow
    f_eye = ImageFont.truetype(sans, 22)
    d.text((80, 110), eyebrow.upper(), font=f_eye, fill=accent)

    # Title
    f_title = ImageFont.truetype(sans, 76)
    title_lines = wrap(d, title, f_title, W - 200)
    y = 170
    for ln in title_lines:
        d.text((80, y), ln, font=f_title, fill=FG)
        bb = d.textbbox((0, 0), ln, font=f_title)
        y += (bb[3] - bb[1]) + 12

    # Body
    y += 30
    f_body = ImageFont.truetype(sans, 32)
    for para in body:
        wrapped = wrap(d, para, f_body, W - 200)
        for ln in wrapped:
            d.text((80, y), ln, font=f_body, fill=(210, 215, 225))
            bb = d.textbbox((0, 0), ln, font=f_body)
            y += (bb[3] - bb[1]) + 12
        y += 18  # paragraph gap

    # Footer page number
    d.text((W - 100, H - 60), "// END", font=ImageFont.truetype(mono, 18), fill=DIM)

    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ {out_path.name} ({out_path.stat().st_size//1024} KB)")


# ---------- 1. PROBLEM (10_problem) ----------
text_card(
    DEST / "demo_02_problem.png",
    eyebrow="// 01 // THE PROBLEM",
    title="Three walls around DeFi trading",
    body=[
        "1.  Centralized exchanges hold your keys. If they go down, you go down with them.",
        "2.  Trading bots speak Python, not English. Retail users can't compete.",
        "3.  Liquidity is fragmented across dozens of DEXs. Best price is rarely one click away.",
    ],
    accent=WARN,
)

# ---------- 2. TERMINAL (20_stack) — pure text log, OK to be drawn ----------
# Re-render using the same approach as before, since it's a log not a UI
TERMINAL_FG = (220, 220, 220)
TERMINAL_GREEN = (80, 200, 120)
TERMINAL_YELLOW = (229, 192, 123)
TERMINAL_DIM = (120, 120, 120)


def render_terminal(out_path: Path, lines):
    img = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(find(MONO_CANDIDATES), 22)
    title_font = ImageFont.truetype(find(MONO_CANDIDATES), 22)
    d.rectangle([0, 0, W, 36], fill=(40, 40, 40))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([20 + i * 24, 13, 30 + i * 24, 23], fill=c)
    d.text((W // 2 - 200, 9), "sui-intent-engine — start.sh", font=title_font, fill=(200, 200, 200))
    y = 80
    for text, color in lines:
        d.text((40, y), text, font=font, fill=color)
        bbox = d.textbbox((0, 0), text, font=font)
        y += (bbox[3] - bbox[1]) + 12
        if y > H - 60:
            break
    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ {out_path.name} ({out_path.stat().st_size//1024} KB)")


terminal_lines = [
    ("$ ./start.sh", TERMINAL_FG),
    ("", TERMINAL_FG),
    ("[start] SUI Intent Engine — full stack", TERMINAL_FG),
    ("[start] root: /Users/stom698/git/QuantDinger/sui-intent-engine", TERMINAL_DIM),
    ("[start] python deps already installed (conda:crawl4ai)", TERMINAL_FG),
    ("[start] node deps already installed (src/frontend/node_modules)", TERMINAL_FG),
    ("[start] starting backend-A (QuantCore AI) on :8000", TERMINAL_YELLOW),
    ("[start] backend-A (QuantCore AI) :8000 up (pid=88291, after 3s)", TERMINAL_GREEN),
    ("[start] starting backend-B (SuiIntent) on :8001", TERMINAL_YELLOW),
    ("[start] backend-B (SuiIntent) :8001 up (pid=88843, after 3s)", TERMINAL_GREEN),
    ("[start] starting frontend (Vite + React) on :3000", TERMINAL_YELLOW),
    ("[start] frontend (Vite + React) :3000 up (pid=88912, after 2s)", TERMINAL_GREEN),
    ("", TERMINAL_FG),
    ("[start] stack is up", TERMINAL_GREEN),
    ("  Frontend    → http://localhost:3000", TERMINAL_FG),
    ("  Backend A   → http://localhost:8000  (QuantCore AI, /docs for Swagger)", TERMINAL_FG),
    ("  Backend B   → http://localhost:8001  (SuiIntent,   /docs for Swagger)", TERMINAL_FG),
    ("", TERMINAL_FG),
    ("logs:   logs/{backend-A,backend-B,frontend}.log", TERMINAL_DIM),
    ("stop:   ./stop.sh", TERMINAL_DIM),
    ("", TERMINAL_FG),
    ("$ _", TERMINAL_FG),
]
render_terminal(DEST / "demo_03_stack.png", terminal_lines)

# ---------- 3. ROADMAP (60_roadmap) ----------
text_card(
    DEST / "demo_07_roadmap.png",
    eyebrow="// 06 // WHAT IS NEXT",
    title="Roadmap — twelve months out",
    body=[
        "Q3 2026    Cross chain intents — bridge to Ethereum and Solana, single PTB, multi-hop.",
        "Q4 2026    Mobile SDK — one tap trading from your phone. Native iOS + Android.",
        "Q1 2027    Strategy marketplace — share profitable prompts, charge usage fees.",
        "Q1 2027    On chain backtests — verifiable by anyone, replay on Sui.",
        "Q2 2027    Multi LLM — bring your own key, BYO-model, run local.",
    ],
    accent=BLUE,
)

# ---------- 4. CLOSING — re-uses landing ----------
import shutil
shutil.copy(DEST / "demo_01_landing.png", DEST / "demo_08_close.png")
print(f"  ✓ demo_08_close.png (re-uses landing)")

# Remove the fake AI mockup — replaced by the real app screenshot
old_ai = DEST / "demo_03_ai.png"
print(f"  keeping: {old_ai.name} (real app screenshot, post ENTER APP)")

# Remove the old PIL mockup that PIL no longer generates
# (no-op — we just don't generate it)

print("\nCards in:", DEST)
for p in sorted(DEST.glob("demo_*.png")):
    print(f"  {p.name}  {p.stat().st_size//1024:>4} KB")
