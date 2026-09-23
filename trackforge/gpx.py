"""Strip waypoints from GPX content, keeping tracks and routes intact."""

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
