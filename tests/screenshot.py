"""Capture README screenshots against a running TrackForge instance.

Usage: uv run python tests/screenshot.py [base_url]
Requires: playwright (dev dependency) and `playwright install chromium`.
"""

import math
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
DEMO_TOUR = "https://www.komoot.com/tour/13584167"


def _demo_track(n: int = 250) -> list[tuple[float, float]]:
    """A Rhine-valley-like stage: west to east with gentle meanders."""
    pts = []
    for i in range(n):
        t = i / (n - 1)
        lon = 7.58 + t * 0.21 + math.sin(t * 9) * 0.006
        lat = (
            50.33
            + math.sin(t * 5.2 + 0.4) * 0.018
            + math.sin(t * 17) * 0.004
            + math.sin(t * 41) * 0.0012
            - t * 0.012
        )
        pts.append((lat, lon))
    return pts


_TRACK = _demo_track()
_WAYPOINTS = [
    (
        _TRACK[i][0] + (0.0042 if k % 2 else -0.0038),
        _TRACK[i][1] + (0.002 if k % 3 else -0.002),
    )
    for k, i in enumerate([22, 58, 90, 124, 158, 196, 232])
]

DEMO_GPX = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="demo" xmlns="http://www.topografix.com/GPX/1/1">
{waypoints}
  <trk><name>Rheinsteig Etappe 3</name><trkseg>
{trackpoints}
  </trkseg></trk>
</gpx>
""".format(
    waypoints="\n".join(
        f'  <wpt lat="{lat:.6f}" lon="{lon:.6f}"><name>Highlight {i + 1}</name></wpt>'
        for i, (lat, lon) in enumerate(_WAYPOINTS)
    ),
    trackpoints="\n".join(
        f'    <trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{60 + i}</ele></trkpt>'
        for i, (lat, lon) in enumerate(_TRACK)
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
        gpx_path = Path(tmp) / "Rheinsteig Etappe 3.gpx"
        gpx_path.write_text(DEMO_GPX)
        page.set_input_files("input[type=file]", gpx_path)
    page.wait_for_selector("text=Wegpunkte entfernt", timeout=30000)
    page.wait_for_timeout(500)
    page.screenshot(path=OUT / "upload-result.png", full_page=True)
    print(f"saved {OUT / 'upload-result.png'}")

    browser.close()
