from __future__ import annotations

import json

from dev_toolkit.timing_tools import append_timing_item, parse_timing_data


def test_parse_timing_data_accepts_json_list() -> None:
    raw = json.dumps([
        {"name": "release preflight", "status": "PASS_WITH_DEBT", "duration_seconds": "1.2345"},
        {"tool": "sandbox", "success": True, "seconds": 2},
    ])

    timing = parse_timing_data(raw)

    assert timing["warnings"] == []
    assert timing["items"] == [
        {"name": "release preflight", "status": "PASS_WITH_DEBT", "duration_seconds": 1.234},
        {"name": "sandbox", "status": "pass", "duration_seconds": 2.0},
    ]
    assert timing["summary"] == {"count": 2, "timed_count": 2, "total_duration_seconds": 3.234}


def test_parse_timing_data_accepts_items_object() -> None:
    timing = parse_timing_data(json.dumps({"items": [{"target": "dev_toolkit/test_x.py", "duration": 0.5}]}))

    assert timing["items"][0]["name"] == "dev_toolkit/test_x.py"
    assert timing["items"][0]["duration_seconds"] == 0.5


def test_parse_timing_data_bad_json_warns_without_failure() -> None:
    timing = parse_timing_data("{bad")

    assert timing["items"] == []
    assert timing["summary"]["count"] == 0
    assert timing["warnings"]


def test_append_timing_item_recomputes_summary() -> None:
    timing = parse_timing_data("")

    append_timing_item(timing, {"name": "pytest", "success": False, "duration_seconds": 4.25})

    assert timing["items"] == [{"name": "pytest", "status": "fail", "duration_seconds": 4.25}]
    assert timing["summary"] == {"count": 1, "timed_count": 1, "total_duration_seconds": 4.25}
