"""Strip waypoints from GPX content, keeping tracks and routes intact."""

import re

_WPT_RE = re.compile(r"\s*<wpt\b[^>]*>.*?</wpt>|\s*<wpt\b[^>]*/>", re.DOTALL)


def remove_waypoints(content: str) -> tuple[str, int]:
    """Return GPX content without <wpt> elements and the number removed."""
    cleaned = _WPT_RE.sub("", content)
    removed = content.count("<wpt") - cleaned.count("<wpt")
    return cleaned, removed


def count_trackpoints(content: str) -> int:
    return content.count("<trkpt")
