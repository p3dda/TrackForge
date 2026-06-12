"""Capture README screenshots against a running TrackForge instance.

Usage: uv run python tests/screenshot.py [base_url]
Requires: playwright (dev dependency) and `playwright install chromium`.
"""

import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
DEMO_TOUR = "https://www.komoot.com/tour/13584167"

DEMO_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="demo" xmlns="http://www.topografix.com/GPX/1/1">
{waypoints}
  <trk><name>Brevet 200k</name><trkseg>
{trackpoints}
  </trkseg></trk>
</gpx>
""".format(
    waypoints="\n".join(
        f'  <wpt lat="50.{70 + i}" lon="7.{10 + i}"><name>Kontrolle {i + 1}</name></wpt>'
        for i in range(7)
    ),
    trackpoints="\n".join(
        f'    <trkpt lat="50.{700 + i}" lon="7.{100 + i}"><ele>{60 + i}</ele></trkpt>'
        for i in range(250)
    ),
)

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

    # Upload a GPX file that actually contains waypoints
    page.goto(BASE_URL)
    page.wait_for_selector("text=TrackForge", timeout=30000)
    with tempfile.TemporaryDirectory() as tmp:
        gpx_path = Path(tmp) / "Brevet 200k.gpx"
        gpx_path.write_text(DEMO_GPX)
        page.set_input_files("input[type=file]", gpx_path)
    page.wait_for_selector("text=Wegpunkte entfernt", timeout=30000)
    page.wait_for_timeout(500)
    page.screenshot(path=OUT / "upload-result.png", full_page=True)
    print(f"saved {OUT / 'upload-result.png'}")

    browser.close()
