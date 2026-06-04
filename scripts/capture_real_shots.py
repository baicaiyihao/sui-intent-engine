#!/usr/bin/env python3
"""
capture_real_shots.py — use playwright with Chrome_test to take real
screenshots of the running app at the right states.

Replaces the fake PIL UI mockups with real captures.
"""
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright

CHROME = "/Applications/Chrome_test.app/Contents/MacOS/Google Chrome"
DEST = Path("/Users/stom698/git/QuantDinger/sui-intent-engine/scripts")
DEST.mkdir(parents=True, exist_ok=True)


async def main():
    async with async_playwright() as p:
        # launch_persistent_context takes the user-data-dir as its own arg
        ctx = await p.chromium.launch_persistent_context(
            executable_path=CHROME,
            user_data_dir="/tmp/chrome_playwright_demo",
            headless=True,
            viewport={"width": 1920, "height": 1080},
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--hide-scrollbars",
            ],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # 1. landing
        print("[shot] 01 landing")
        await page.goto("http://localhost:3000/", wait_until="networkidle", timeout=15000)
        await page.wait_for_timeout(2000)  # let live ticker load
        await page.screenshot(path=str(DEST / "demo_01_landing.png"))

        # 2. AI tab — click ENTER APP, then click AI Chat tab
        print("[shot] 03 ai (post-enter-app)")
        try:
            enter = page.get_by_text("ENTER APP").first
            await enter.click(timeout=5000)
            await page.wait_for_timeout(2000)
            # Click "AI Chat" tab inside the app
            try:
                ai_tab = page.get_by_text("AI Chat", exact=True).first
                await ai_tab.click(timeout=3000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"  AI Chat tab click failed: {e}")
        except Exception as e:
            print(f"  ENTER APP click failed: {e}")
        await page.screenshot(path=str(DEST / "demo_03_ai.png"))

        await ctx.close()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
