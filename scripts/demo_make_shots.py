#!/usr/bin/env python3
"""
Generate mock screenshots for the demo (terminal + AI chat) using PIL.
Real screenshots come from Chrome headless for landing + SuiVision.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DEST = Path("/Users/stom698/git/QuantDinger/sui-intent-engine/scripts")
DEST.mkdir(parents=True, exist_ok=True)

W, H = 1920, 1080
BG = (24, 24, 24)        # terminal-ish dark
FG = (220, 220, 220)     # normal text
GREEN = (80, 200, 120)   # "up" lines
YELLOW = (229, 192, 123) # accent
DIM = (120, 120, 120)    # comments

# Try a monospace font
MONO_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
    "/Library/Fonts/Courier New Bold.ttf",
    "/usr/local/share/fonts/DejaVuSansMono-Bold.ttf",
    "/opt/homebrew/share/fonts/DejaVuSansMono-Bold.ttf",
]
# Sans-serif that supports CJK glyphs (for tab labels etc.)
SANS_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]
def find_mono() -> str:
    for p in MONO_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError("no monospace font")

def find_sans() -> str:
    for p in SANS_CANDIDATES:
        if Path(p).exists():
            return p
    raise RuntimeError("no sans font")


def render_terminal(out_path: Path, lines: list[tuple[str, tuple[int, int, int]]]):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(find_mono(), 22)
    title_font = ImageFont.truetype(find_mono(), 22)
    # Title bar
    d.rectangle([0, 0, W, 36], fill=(40, 40, 40))
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([20 + i * 24, 13, 30 + i * 24, 23], fill=c)
    d.text((W // 2 - 200, 9), "sui-intent-engine — start.sh", font=title_font, fill=(200, 200, 200))

    # Body text
    y = 80
    for text, color in lines:
        d.text((40, y), text, font=font, fill=color)
        # advance — rough line height
        bbox = d.textbbox((0, 0), text, font=font)
        y += (bbox[3] - bbox[1]) + 12
        if y > H - 60:
            break
    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ {out_path.name} ({out_path.stat().st_size//1024} KB)")


def render_ai_chat(out_path: Path, messages: list[tuple[str, str]]):
    """A mock AI chat panel styled like the app."""
    img = Image.new("RGB", (W, H), (8, 8, 12))   # deep black
    d = ImageDraw.Draw(img)
    title_font = ImageFont.truetype(find_mono(), 24)
    body_mono = ImageFont.truetype(find_mono(), 22)
    body_sans = ImageFont.truetype(find_sans(), 22)
    label_font = ImageFont.truetype(find_mono(), 16)

    # Top header
    d.rectangle([0, 0, W, 64], fill=(18, 18, 24))
    d.text((40, 20), "[ 02 // AI CHAT ]   SUI INTENT ENGINE", font=title_font, fill=(120, 200, 255))
    d.text((W - 240, 20), "SUI MAINNET  •  LIVE", font=label_font, fill=(80, 200, 120))

    # Tab bar — use sans for CJK characters
    tabs = [("AI 策略", True), ("AI 量化", False), ("交易中心", False)]
    x = 40
    for label, active in tabs:
        color = (255, 255, 255) if active else (120, 120, 130)
        underline_color = (120, 200, 255) if active else (40, 40, 50)
        d.text((x, 90), label, font=body_sans, fill=color)
        bbox = d.textbbox((x, 90), label, font=body_sans)
        d.rectangle([x, 130, bbox[2], 134], fill=underline_color)
        x = bbox[2] + 40

    # Chat messages
    y = 180
    for role, text in messages:
        if role == "user":
            # right-aligned bubble
            text_w = d.textlength(text, font=body_mono)
            bubble_x = W - 80 - int(text_w) - 32
            d.rounded_rectangle([bubble_x, y, W - 80, y + 60], radius=12, fill=(30, 60, 100))
            d.text((bubble_x + 16, y + 18), text, font=body_mono, fill=(220, 235, 255))
            y += 90
        else:
            # assistant — left aligned, with "AI" label
            d.text((80, y), "AI", font=label_font, fill=(120, 200, 255))
            d.text((120, y - 4), text, font=body_mono, fill=(220, 220, 230))
            bbox = d.textbbox((80, y), text, font=body_mono)
            # rough wrap
            y += max(60, (bbox[3] - bbox[1]) + 24)
        if y > H - 200:
            break

    # Input box at bottom
    d.rectangle([40, H - 100, W - 40, H - 40], outline=(60, 60, 70), width=2)
    d.text((60, H - 80), "Type an intent in plain English…  e.g. buy 1 SUI if RSI < 30", font=body_mono, fill=(100, 100, 110))
    img.save(out_path, "PNG", optimize=True)
    print(f"  ✓ {out_path.name} ({out_path.stat().st_size//1024} KB)")


# ---------- 1. terminal showing start.sh ----------
terminal_lines = [
    ("$ ./start.sh", FG),
    ("", FG),
    ("[start] SUI Intent Engine — full stack", FG),
    ("[start] root: /Users/stom698/git/QuantDinger/sui-intent-engine", DIM),
    ("[start] python deps already installed (conda:crawl4ai)", FG),
    ("[start] node deps already installed (src/frontend/node_modules)", FG),
    ("[start] starting backend-A (QuantCore AI) on :8000", YELLOW),
    ("[start] backend-A (QuantCore AI) :8000 up (pid=88291, after 3s)", GREEN),
    ("[start] starting backend-B (SuiIntent) on :8001", YELLOW),
    ("[start] backend-B (SuiIntent) :8001 up (pid=88843, after 3s)", GREEN),
    ("[start] starting frontend (Vite + React) on :3000", YELLOW),
    ("[start] frontend (Vite + React) :3000 up (pid=88912, after 2s)", GREEN),
    ("", FG),
    ("[start] stack is up", GREEN),
    ("  Frontend    → http://localhost:3000", FG),
    ("  Backend A   → http://localhost:8000  (QuantCore AI, /docs for Swagger)", FG),
    ("  Backend B   → http://localhost:8001  (SuiIntent,   /docs for Swagger)", FG),
    ("", FG),
    ("logs:   logs/{backend-A,backend-B,frontend}.log", DIM),
    ("stop:   ./stop.sh", DIM),
    ("", FG),
    ("$ _", FG),
]
render_terminal(DEST / "demo_02_terminal.png", terminal_lines)

# ---------- 2. AI chat ----------
chat_messages = [
    ("user", "buy 1 SUI if RSI is below 30"),
    ("assistant", "Parsed intent → BUY 1 SUI @ market if RSI(14) < 30"),
    ("assistant", "Guardian: 6/6 checks passed. Slippage 0.04% within limit."),
    ("assistant", "PTB: deposit 1 SUI → place_limit_order @ 0.8336 → expiry +1h"),
    ("user", "yes, sign it"),
    ("assistant", "Wallet signature requested. Waiting for approval…"),
]
render_ai_chat(DEST / "demo_03_ai.png", chat_messages)

# ---------- 3. SuiVision — try to capture from real Chrome, fall back to mock ----------
suivision = DEST / "demo_04_suivision.png"
if not suivision.exists():
    # PIL mockup (saves time)
    img = Image.new("RGB", (W, H), (16, 18, 22))
    d = ImageDraw.Draw(img)
    title_font = ImageFont.truetype(find_mono(), 24)
    body_font = ImageFont.truetype(find_mono(), 20)
    label_font = ImageFont.truetype(find_mono(), 16)
    d.rectangle([0, 0, W, 64], fill=(20, 28, 36))
    d.text((40, 20), "SuiVision  •  Sui Mainnet Explorer", font=title_font, fill=(100, 200, 255))
    d.text((W - 280, 20), "tx 4jGNB1W5…ehvG1D", font=label_font, fill=(180, 200, 220))
    d.text((80, 120), "Transaction Block", font=title_font, fill=(220, 220, 220))
    d.text((80, 170), "Status:  SUCCESS", font=body_font, fill=(80, 220, 140))
    d.text((80, 210), "Sender:  0xc52aa1eb1eca…916bc64e", font=body_font, fill=(200, 200, 210))
    d.text((80, 250), "Gas:     0.00512 SUI", font=body_font, fill=(200, 200, 210))
    d.text((80, 290), "Timestamp: 2026-05-28 14:23:11 UTC", font=body_font, fill=(200, 200, 210))
    d.text((80, 360), "Move Calls:", font=title_font, fill=(220, 220, 220))
    calls = [
        "0x600138d3::deepbookv3_utils::deposit_then_place_limit_order_by_owner",
        "0xff1141ef::balance_manager::generate_proof_as_owner",
        "0x2c8d603b::pool::place_limit_order",
    ]
    y = 410
    for c in calls:
        d.text((120, y), "→ " + c, font=body_font, fill=(180, 220, 255))
        y += 36
    d.text((80, y + 30), "Treasury:  0xabc…fee9  (Intent Engine protocol fee)", font=body_font, fill=(180, 200, 220))
    img.save(suivision, "PNG", optimize=True)
    print(f"  ✓ {suivision.name} (mock, {suivision.stat().st_size//1024} KB)")

# ---------- 4. closing — same as landing but with closing tagline overlay ----------
# Just reuse the landing shot
import shutil
shutil.copy(DEST / "demo_01_landing.png", DEST / "demo_05_close.png")
print(f"  ✓ demo_05_close.png (re-uses landing)")

print("\nAll shots in:", DEST)
for p in sorted(DEST.glob("demo_*.png")):
    print(f"  {p.name}  {p.stat().st_size//1024:>4} KB")
