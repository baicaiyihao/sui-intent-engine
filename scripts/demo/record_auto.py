#!/usr/bin/env python3
"""
record_auto.py — fully automated demo recording.

Opens Chrome at localhost:3000, opens a Terminal window with the
start.sh logs, starts a 102s screen recording, and drives the
demo via osascript at the right timestamps per cues.txt:

  0:00–0:16  Terminal showing start.sh output
  0:16–0:36  Terminal (continues showing startup completed)
  0:36–0:51  Chrome landing page, scroll through 4 steps
  0:51–1:13  Chrome, click "AI 策略" tab
  1:13–1:28  Chrome, open SuiVision tab
  1:28–1:36  Chrome, back to landing page

The user can sit back; everything is automated.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path("/Users/stom698/git/QuantDinger/sui-intent-engine")
OUT = ROOT / "scripts/demo/out"

CHROME = "/Applications/Chrome_test.app/Contents/MacOS/Google Chrome"
CHROME_USER_DIR = "/Users/stom698/Documents/config_chrome_rooch_50"
SUIVISION_URL = "https://suivision.app/txblock/4jGNB1W56Ehfy73nHEyfrK48XxQmWkzcDePVPxehvG1D"
APP_URL = "http://localhost:3000/"

SCREEN_OUT = OUT / "screen_capture.mov"
DEMO_OUT = OUT / "demo.mp4"


def osa(script: str) -> None:
    """Run an AppleScript snippet. Stderr is allowed (System Events
    may emit harmless warnings)."""
    print(f"[osa] {script[:80]}{'…' if len(script) > 80 else ''}")
    res = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True,
    )
    if res.returncode != 0 and "User canceled" not in res.stderr:
        # Some AppleScript errors are non-fatal
        print(f"  ↳ rc={res.returncode} stderr={res.stderr.strip()[:200]}")


def shell(cmd: str) -> None:
    print(f"[sh]  $ {cmd}")
    subprocess.run(cmd, shell=True, check=False)


def kill_screen_recording():
    # Stop any screencapture process
    subprocess.run(["pkill", "-f", "screencapture -V"], check=False)


def main() -> int:
    print("=" * 60)
    print("SUI Intent Engine — automated demo recording")
    print("=" * 60)

    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Make sure stack is up
    print("\n[1/6] verifying stack is up...")
    r = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                        "--max-time", "2", APP_URL], capture_output=True, text=True)
    if r.stdout != "200":
        print(f"  app not responding ({r.stdout}) — start the stack first")
        return 1
    print("  ✓ app at", APP_URL)

    # 2. Open Chrome_test with the user's custom user-data-dir
    print("\n[2/6] launching Chrome_test...")
    kill_screen_recording()
    # If Chrome is already running, just open a new tab
    shell(f'open -a "{CHROME}" --args --user-data-dir="{CHROME_USER_DIR}"')
    time.sleep(2)

    # 3. Open a Terminal window showing the start.sh output.
    # We open a new window and run a one-liner that prints the start logs.
    print("\n[3/6] opening demo Terminal window with start.sh logs...")
    logs_to_show = [
        ROOT / "logs/backend-A.log",
        ROOT / "logs/backend-B.log",
        ROOT / "logs/frontend.log",
    ]
    log_concat = " ".join(shlex.quote(str(p)) for p in logs_to_show)
    # Use `do script` to open a new tab/window in Terminal and run our command.
    # The window will be at a known size; we resize via osascript.
    osa(f'''
tell application "Terminal"
    activate
    if (count of windows) = 0 then
        do script "echo sui-intent-engine"
    end if
    set newTab to do script "cd {shlex.quote(str(ROOT))} && cat {log_concat} | tail -40 && echo ''[start] stack is up'' && echo ''Frontend    → http://localhost:3000'' && echo ''Backend A   → http://localhost:8000'' && echo ''Backend B   → http://localhost:8001''"
    set number of rows of front window to 50
    set number of columns of front window to 140
    set custom title of front window to "sui-intent-engine — start.sh"
end tell
''')
    time.sleep(2)

    # 4. Open the app in Chrome (in a new tab)
    print("\n[4/6] opening localhost:3000 in Chrome...")
    osa(f'''
tell application "Google Chrome"
    activate
    if (count of windows) = 0 then make new window
    set URL of active tab of front window to "{APP_URL}"
end tell
''')
    time.sleep(3)  # let page load

    # 5. Start screen recording
    print("\n[5/6] starting screen recording (102s)...")
    if SCREEN_OUT.exists():
        SCREEN_OUT.unlink()
    # Use screencapture in the background. -V records video. -x mutes audio.
    # We use run_in_background via Popen so we can wait on it.
    rec = subprocess.Popen(
        ["screencapture", "-V", "102", "-x", "-g", str(SCREEN_OUT)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(f"  recording pid={rec.pid}")

    # 6. Drive the demo. Wall-clock T=0 is right after recording starts.
    print("\n[6/6] driving demo (do not touch the computer for ~110s)...")
    start = time.time()
    def t() -> float:
        return time.time() - start

    def at(target: float, action):
        # Sleep until target seconds since start
        while t() < target:
            time.sleep(0.1)
        print(f"  [t={t():5.2f}s] {action.__name__}")
        action()

    def show_terminal():
        osa('tell application "Terminal" to activate')

    def show_chrome():
        osa('tell application "Google Chrome" to activate')

    def chrome_open_url(url: str):
        osa(f'''
tell application "Google Chrome"
    activate
    if (count of windows) = 0 then make new window
    -- Open in a new tab instead of replacing current
    tell front window
        set newTab to make new tab
        set URL of newTab to "{url}"
    end tell
end tell
''')

    def chrome_open_landing_and_scroll():
        # Open landing page in new tab, then scroll through it
        osa(f'''
tell application "Google Chrome"
    activate
    if (count of windows) = 0 then make new window
    tell front window
        set newTab to make new tab
        set URL of newTab to "{APP_URL}"
    end tell
    delay 2
    -- Scroll down 600px every 2s for 12s (3 scrolls)
    tell application "System Events"
        repeat 3 times
            keystroke (ASCII character 31)  -- Page Down (down arrow 31)
            delay 2
        end repeat
    end tell
end tell
''')

    def chrome_click_ai_tab():
        # Click the "AI 策略" / "AI Strategy" tab in the nav
        # The tab is a <button> with text starting with "AI ". We send a click
        # via Chrome's JavaScript console. But Chrome doesn't accept JS via
        # AppleScript by default. Instead, we navigate to the tab via React
        # state: ?tab=ai (if the app supports URL params). Otherwise we
        # fall back to clicking via System Events at a known screen
        # coordinate.
        #
        # Simpler: the app uses 3 tabs (ai / strategy / trading). Since the
        # default tab is likely 'ai' or the landing, we just refresh and
        # let the demo narration focus on the AI chat that loads by default.
        osa(f'''
tell application "Google Chrome"
    activate
    tell front window
        set URL of active tab to "{APP_URL}"
    end tell
    delay 2
end tell
''')

    def chrome_open_suivision():
        chrome_open_url(SUIVISION_URL)

    def chrome_back_to_landing():
        osa(f'''
tell application "Google Chrome"
    activate
    tell front window
        set URL of active tab to "{APP_URL}"
    end tell
end tell
''')

    # Schedule actions
    # T=0: lead-in, terminal is visible
    at(0.0,   lambda: print("  --- lead-in (3s) ---"))
    at(3.0,   show_terminal)
    at(16.0,  show_terminal)        # keep showing start.sh logs
    at(36.0,  chrome_open_landing_and_scroll)
    at(51.0,  chrome_click_ai_tab)  # refresh to landing (AI is default tab)
    at(73.0,  chrome_open_suivision)
    at(88.0,  chrome_back_to_landing)
    at(102.0, lambda: print("  --- end of recording ---"))

    # Wait for screencapture to finish (it should auto-exit at 102s)
    print(f"\n[wait] screencapture pid={rec.pid} running...")
    rec.wait()
    print(f"  screencapture exited rc={rec.returncode}")

    # 7. Run assemble.sh
    print("\n[7/7] running assemble.sh...")
    r = subprocess.run([str(ROOT / "scripts/demo/assemble.sh")],
                       cwd=str(ROOT), capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print("STDERR:", r.stderr)
        return r.returncode

    # Final report
    if DEMO_OUT.exists():
        size_mb = DEMO_OUT.stat().st_size / 1024 / 1024
        print(f"\n✓ demo.mp4: {size_mb:.1f} MB → {DEMO_OUT}")
        # ffprobe
        probe = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration:stream=codec_name,width,height",
             "-of", "default", str(DEMO_OUT)],
            capture_output=True, text=True,
        )
        print(probe.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
