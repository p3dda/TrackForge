import httpx
import pytest

from trackforge.komoot import (
    KomootError,
    extract_share_token,
    extract_tour_id,
    fetch_gpx,
)

TOUR_JSON = {
    "id": "123456789",
    "name": "Testtour an der Sieg",
    "_embedded": {
        "coordinates": {
            "items": [
                {"lat": 50.7, "lng": 7.1, "alt": 60.0, "t": 0},
                {"lat": 50.71, "lng": 7.11, "alt": 61.5, "t": 10},
            ]
        }
    },
}


def make_transport(gpx_status=403, json_status=200, json_body=TOUR_JSON):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".gpx"):
            return httpx.Response(gpx_status)
        return httpx.Response(json_status, json=json_body)

    return httpx.MockTransport(handler)


class TestUrlParsing:
    def test_plain_tour_url(self):
        assert extract_tour_id("https://www.komoot.com/tour/123456789") == "123456789"

    def test_locale_prefix(self):
        assert (
            extract_tour_id("https://www.komoot.com/de-de/tour/2813570197?x=1")
            == "2813570197"
        )

    def test_komoot_de_domain(self):
        assert extract_tour_id("https://www.komoot.de/tour/42") == "42"

    def test_invalid_url_raises(self):
        with pytest.raises(KomootError):
            extract_tour_id("https://example.com/foo")

    def test_share_token_extracted(self):
        url = "https://www.komoot.com/de-de/tour/1?share_token=aXyZ&ref=wtd"
        assert extract_share_token(url) == "aXyZ"

    def test_no_share_token(self):
        assert extract_share_token("https://www.komoot.com/tour/1") is None


class TestFetchGpx:
    def test_builds_gpx_from_coordinates_json(self):
        gpx, name = fetch_gpx(
            "https://www.komoot.com/tour/123456789", transport=make_transport()
        )
        assert name == "Testtour an der Sieg"
        assert gpx.count("<trkpt") == 2
        assert "<wpt" not in gpx
        assert '<trkpt lat="50.7" lon="7.1"><ele>60.0</ele></trkpt>' in gpx

    def test_gpx_endpoint_used_when_available(self):
        raw_gpx = '<?xml version="1.0"?><gpx><trk><name>Direkt</name></trk></gpx>'

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith(".gpx"):
                return httpx.Response(200, text=raw_gpx)
            raise AssertionError("JSON fallback should not be called")

        gpx, name = fetch_gpx(
            "https://www.komoot.com/tour/1", transport=httpx.MockTransport(handler)
        )
        assert gpx == raw_gpx
        assert name == "Direkt"

    def test_share_token_passed_to_api(self):
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen[request.url.path] = dict(request.url.params)
            if request.url.path.endswith(".gpx"):
                return httpx.Response(403)
            return httpx.Response(200, json=TOUR_JSON)

        fetch_gpx(
            "https://www.komoot.com/de-de/tour/123456789?share_token=tok123",
            transport=httpx.MockTransport(handler),
        )
        assert all(p.get("share_token") == "tok123" for p in seen.values())

    def test_private_tour_raises(self):
        with pytest.raises(KomootError, match="privat"):
            fetch_gpx(
                "https://www.komoot.com/tour/1",
                transport=make_transport(json_status=403, json_body={}),
            )

    def test_unknown_tour_raises(self):
        with pytest.raises(KomootError, match="nicht gefunden"):
            fetch_gpx(
                "https://www.komoot.com/tour/1",
                transport=make_transport(gpx_status=404),
            )

    def test_tour_without_coordinates_raises(self):
        body = {"name": "leer", "_embedded": {"coordinates": {"items": []}}}
        with pytest.raises(KomootError, match="Koordinaten"):
            fetch_gpx(
                "https://www.komoot.com/tour/1",
                transport=make_transport(json_body=body),
            )

    def test_tour_name_is_xml_escaped(self):
        body = dict(TOUR_JSON, name="Tour <mit> & Sonderzeichen")
        gpx, _ = fetch_gpx(
            "https://www.komoot.com/tour/1", transport=make_transport(json_body=body)
        )
        assert "<name>Tour &lt;mit&gt; &amp; Sonderzeichen</name>" in gpx
