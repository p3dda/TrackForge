"""Capture README screenshots against a running TrackForge instance.

Usage: uv run python tests/screenshot.py [base_url]
Requires: playwright (dev dependency) and `playwright install chromium`.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
DEMO_TOUR = "https://www.komoot.com/tour/13584167"

OUT.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1100, "height": 900})
    page.goto(BASE_URL)
    page.wait_for_selector("text=TrackForge", timeout=30000)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "main.png", full_page=True)
    print(f"saved {OUT / 'main.png'}")

    page.fill("input[placeholder*='komoot']", DEMO_TOUR)
    page.click("button:has-text('Laden')")
    page.wait_for_selector("text=Fertig geschmiedet", timeout=60000)
    page.wait_for_timeout(500)
    page.screenshot(path=OUT / "result.png", full_page=True)
    print(f"saved {OUT / 'result.png'}")

    browser.close()
