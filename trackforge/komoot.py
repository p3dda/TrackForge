"""Fetch GPX data for public or link-shared Komoot tours."""

import re
from urllib.parse import parse_qs, urlsplit
from xml.sax.saxutils import escape

import httpx

_TOUR_ID_RE = re.compile(r"komoot\.[a-z.]+(?:/[a-z]{2}-[a-z]{2})?/tour/(\d+)", re.IGNORECASE)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


class KomootError(Exception):
    pass


def extract_tour_id(url: str) -> str:
    match = _TOUR_ID_RE.search(url)
    if not match:
        raise KomootError(
            "Keine Tour-ID in der URL gefunden. Erwartet wird ein Link wie "
            "https://www.komoot.com/tour/123456789"
        )
    return match.group(1)


def extract_share_token(url: str) -> str | None:
    query = parse_qs(urlsplit(url).query)
    tokens = query.get("share_token")
    return tokens[0] if tokens else None


def fetch_gpx(
    url: str, transport: httpx.BaseTransport | None = None
) -> tuple[str, str]:
    """Return (gpx_content, tour_name) for a public or link-shared Komoot tour URL.

    `transport` allows injecting an httpx.MockTransport in tests.
    """
    tour_id = extract_tour_id(url)
    share_token = extract_share_token(url)
    params = {"share_token": share_token} if share_token else {}
    with httpx.Client(
        headers=_HEADERS, timeout=30, follow_redirects=True, transport=transport
    ) as client:
        resp = client.get(
            f"https://www.komoot.com/api/v007/tours/{tour_id}.gpx", params=params
        )
        if resp.status_code == 200 and "<gpx" in resp.text:
            name = _gpx_name(resp.text) or f"komoot-tour-{tour_id}"
            return resp.text, name
        if resp.status_code == 404:
            raise KomootError(f"Tour {tour_id} wurde nicht gefunden.")
        # The .gpx endpoint requires auth even for public tours;
        # build the GPX from the public coordinates JSON instead.
        return _fetch_via_json(client, tour_id, params)


def _fetch_via_json(
    client: httpx.Client, tour_id: str, extra_params: dict | None = None
) -> tuple[str, str]:
    resp = client.get(
        f"https://www.komoot.com/api/v007/tours/{tour_id}",
        params={"_embedded": "coordinates", **(extra_params or {})},
    )
    if resp.status_code in (401, 403):
        raise KomootError(
            "Die Tour ist privat oder nicht freigegeben. Verwende einen "
            "Komoot-Share-Link (mit share_token) oder lade die GPX-Datei "
            "selbst herunter und ziehe sie hier hinein."
        )
    if resp.status_code != 200:
        raise KomootError(f"Komoot antwortete mit HTTP {resp.status_code}.")
    data = resp.json()
    name = data.get("name") or f"komoot-tour-{tour_id}"
    items = data.get("_embedded", {}).get("coordinates", {}).get("items", [])
    if not items:
        raise KomootError("Die Tour enthält keine Koordinaten.")
    return _build_gpx(name, items), name


def _build_gpx(name: str, items: list[dict]) -> str:
    points = []
    for pt in items:
        ele = f"<ele>{pt['alt']}</ele>" if "alt" in pt else ""
        points.append(
            f'      <trkpt lat="{pt["lat"]}" lon="{pt["lng"]}">{ele}</trkpt>'
        )
    body = "\n".join(points)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="TrackForge" '
        'xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <trk>\n    <name>{escape(name)}</name>\n    <trkseg>\n"
        f"{body}\n"
        "    </trkseg>\n  </trk>\n</gpx>\n"
    )


def _gpx_name(content: str) -> str | None:
    match = re.search(r"<name>(.*?)</name>", content, re.DOTALL)
    return match.group(1).strip() if match else None
