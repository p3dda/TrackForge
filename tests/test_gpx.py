from trackforge.gpx import count_trackpoints, gpx_name, is_gpx, remove_waypoints

GPX_WITH_WAYPOINTS = """<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">
  <wpt lat="50.7" lon="7.1">
    <name>Kontrolle 1</name>
    <desc>Multi
line</desc>
  </wpt>
  <wpt lat="50.8" lon="7.2"/>
  <trk>
    <name>Testtrack</name>
    <trkseg>
      <trkpt lat="50.7" lon="7.1"><ele>60</ele></trkpt>
      <trkpt lat="50.71" lon="7.11"><ele>61</ele></trkpt>
    </trkseg>
  </trk>
</gpx>
"""


def test_removes_paired_and_self_closing_waypoints():
    cleaned, removed = remove_waypoints(GPX_WITH_WAYPOINTS)
    assert removed == 2
    assert "<wpt" not in cleaned


def test_keeps_track_intact():
    cleaned, _ = remove_waypoints(GPX_WITH_WAYPOINTS)
    assert count_trackpoints(cleaned) == 2
    assert "<name>Testtrack</name>" in cleaned
    assert '<trkpt lat="50.7" lon="7.1"><ele>60</ele></trkpt>' in cleaned


def test_no_waypoints_is_noop():
    cleaned, removed = remove_waypoints(GPX_WITH_WAYPOINTS)
    again, removed_again = remove_waypoints(cleaned)
    assert removed_again == 0
    assert again == cleaned


def test_multiline_waypoint_content_is_removed():
    cleaned, _ = remove_waypoints(GPX_WITH_WAYPOINTS)
    assert "Kontrolle 1" not in cleaned
    assert "Multi" not in cleaned


def test_similar_tag_names_are_not_counted():
    content = "<gpx><wptx/><trkptx/><trkpt/></gpx>"
    cleaned, removed = remove_waypoints(content)
    assert removed == 0
    assert cleaned == content
    assert count_trackpoints(content) == 1


def test_is_gpx():
    assert is_gpx(GPX_WITH_WAYPOINTS)
    assert not is_gpx("<html></html>")


def test_gpx_name_is_unescaped():
    assert gpx_name("<gpx><trk><name> A &amp; B </name></trk></gpx>") == "A & B"
    assert gpx_name("<gpx></gpx>") is None
