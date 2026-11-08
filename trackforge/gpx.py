"""Strip waypoints from GPX content, keeping tracks and routes intact."""

import math
import re
from xml.sax.saxutils import unescape

_WPT_RE = re.compile(r"\s*<wpt\b[^>]*>.*?</wpt>|\s*<wpt\b[^>]*/>", re.DOTALL)
_TRKPT_RE = re.compile(r"<trkpt\b")
_NAME_RE = re.compile(r"<name>(.*?)</name>", re.DOTALL)


def is_gpx(content: str) -> bool:
    """Return whether the content looks like a GPX document."""
    return "<gpx" in content


def remove_waypoints(content: str) -> tuple[str, int]:
    """Return GPX content without <wpt> elements and the number removed."""
    return _WPT_RE.subn("", content)


def count_trackpoints(content: str) -> int:
    """Return the number of <trkpt> elements in the GPX content."""
    return len(_TRKPT_RE.findall(content))


def gpx_name(content: str) -> str | None:
    """Return the first <name> in the GPX content, XML-unescaped."""
    match = _NAME_RE.search(content)
    return unescape(match.group(1).strip()) if match else None


_POINT_RE = re.compile(r"<(wpt|trkpt|rtept)\b([^>]*)>")
_LAT_RE = re.compile(r"\blat\s*=\s*[\"']([-+0-9.eE]+)[\"']")
_LON_RE = re.compile(r"\blon\s*=\s*[\"']([-+0-9.eE]+)[\"']")

PREVIEW_WIDTH = 600
PREVIEW_HEIGHT = 220
_PREVIEW_PAD = 24
_PREVIEW_MAX_POINTS = 600
_TRACK_COLOR = "#ffc53d"
_WPT_COLOR = "#85858b"
_BG_COLOR = "#141415"
_END_COLOR = "#ededed"


def _points(content: str) -> dict[str, list[tuple[float, float]]]:
    found: dict[str, list[tuple[float, float]]] = {"wpt": [], "trkpt": [], "rtept": []}
    for tag, attrs in _POINT_RE.findall(content):
        lat, lon = _LAT_RE.search(attrs), _LON_RE.search(attrs)
        if lat and lon:
            try:
                found[tag].append((float(lat.group(1)), float(lon.group(1))))
            except ValueError:
                continue
    return found


def track_preview_svg(content: str) -> str:
    """Return an SVG drawing of the track with its waypoints, or "" if no track.

    Uses the original (uncleaned) GPX so the removed waypoints can be shown
    as crossed-out markers next to the track line.
    """
    found = _points(content)
    track = found["trkpt"] or found["rtept"]
    if len(track) < 2:
        return ""
    waypoints = found["wpt"]
    everything = track + waypoints

    # Equirectangular projection, fitted into the preview box.
    mean_lat = sum(p[0] for p in everything) / len(everything)
    kx = math.cos(math.radians(mean_lat))
    xs = [p[1] * kx for p in everything]
    ys = [-p[0] for p in everything]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span_x, span_y = (max_x - min_x) or 1e-9, (max_y - min_y) or 1e-9
    scale = min(
        (PREVIEW_WIDTH - 2 * _PREVIEW_PAD) / span_x,
        (PREVIEW_HEIGHT - 2 * _PREVIEW_PAD) / span_y,
    )
    off_x = (PREVIEW_WIDTH - span_x * scale) / 2
    off_y = (PREVIEW_HEIGHT - span_y * scale) / 2

    def project(p: tuple[float, float]) -> tuple[float, float]:
        return off_x + (p[1] * kx - min_x) * scale, off_y + (-p[0] - min_y) * scale

    step = max(1, len(track) // _PREVIEW_MAX_POINTS)
    sampled = track[::step]
    if sampled[-1] != track[-1]:
        sampled.append(track[-1])
    coords = [project(p) for p in sampled]
    path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in coords)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PREVIEW_WIDTH} {PREVIEW_HEIGHT}">',
        f'<path d="{path}" fill="none" stroke="{_TRACK_COLOR}" stroke-width="2.5" '
        'stroke-linejoin="round" stroke-linecap="round"/>',
    ]
    for wpt in waypoints:
        x, y = project(wpt)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="{_BG_COLOR}" '
            f'stroke="{_WPT_COLOR}" stroke-width="1.5"/>'
            f'<line x1="{x - 3:.1f}" y1="{y + 3:.1f}" x2="{x + 3:.1f}" y2="{y - 3:.1f}" '
            f'stroke="{_WPT_COLOR}" stroke-width="1.5" stroke-linecap="round"/>'
        )
    for x, y in (coords[0], coords[-1]):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{_END_COLOR}" '
            f'stroke="{_BG_COLOR}" stroke-width="2"/>'
        )
    parts.append("</svg>")
    return "".join(parts)
