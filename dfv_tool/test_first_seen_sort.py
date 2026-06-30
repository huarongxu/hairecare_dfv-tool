"""
Adversarial tests for First Time / Duration columns and table sorting.

Run:  .venv\\Scripts\\python.exe dfv_tool\\test_first_seen_sort.py

Covers edge cases: ISO year boundaries, 53-week years, same-week (duration 0),
future first-date guard, int vs str product keys, brand-new items, stable sort
with ties, and the dashboard template wiring.
"""
import os
import sys
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pipeline
import history
import dashboard


def _now_week():
    return pipeline._iso_week_label(datetime.now())


def test_week_helpers():
    # Same ISO week (Mon 2026-06-08 .. Fri 2026-06-12) -> 0
    assert pipeline._week_span(datetime(2026, 6, 8), datetime(2026, 6, 12)) == 0
    # W24 -> W27 = 3 weeks
    assert pipeline._week_span(datetime(2026, 6, 9), datetime(2026, 6, 30)) == 3
    # Year boundary: 2025-12-31 is ISO W1/2026; +1 week -> 1
    assert pipeline._week_span(datetime(2025, 12, 31), datetime(2026, 1, 7)) == 1
    # Future first-date must be guarded to 0 (never negative)
    assert pipeline._week_span(datetime(2026, 12, 31), datetime(2026, 6, 30)) == 0

    # Labels
    assert pipeline._iso_week_label(datetime(2026, 6, 9)) == "W24/2026"
    assert pipeline._iso_week_label(datetime(2025, 12, 31)) == "W01/2026"  # ISO rolls to 2026
    assert pipeline._iso_week_label(datetime(2020, 12, 31)) == "W53/2020"  # 53-week year

    # Date parsing
    assert pipeline._parse_run_date("2026-06-09 14:58") == datetime(2026, 6, 9, 14, 58)
    assert pipeline._parse_run_date("2026-06-09 14:58:30") == datetime(2026, 6, 9, 14, 58, 30)
    assert pipeline._parse_run_date("2026-06-09") == datetime(2026, 6, 9)
    assert pipeline._parse_run_date("garbage") is None
    assert pipeline._parse_run_date(None) is None
    print("PASS test_week_helpers")


def test_priority_buckets():
    # 0-2 Low (incl. brand-new 0), 3-4 Mid, >4 High; empty/None -> ""
    assert pipeline._priority(0) == "Low"
    assert pipeline._priority(1) == "Low"
    assert pipeline._priority(2) == "Low"
    assert pipeline._priority(3) == "Mid"
    assert pipeline._priority(4) == "Mid"
    assert pipeline._priority(5) == "High"
    assert pipeline._priority(99) == "High"
    assert pipeline._priority(None) == ""
    assert pipeline._priority("") == ""
    print("PASS test_priority_buckets")


def test_enrich_first_seen():
    # Inject a fake history map (overrides the imported lookup at call time).
    original = history.get_first_seen_map
    history.get_first_seen_map = lambda: {
        ("83929605", "A673"): "2026-06-09 14:58",   # historical -> W24/2026
        ("999", "X1"): "2025-12-31 09:00",          # year-boundary -> W01/2026
    }
    try:
        df = pd.DataFrame([
            {"APO_Product": "83929605", "APO_Location": "A673"},  # known historical
            {"APO_Product": "NEW1", "APO_Location": "Z9"},        # brand new
            {"APO_Product": 999, "APO_Location": "X1"},           # int product matches str key
        ])
        out = pipeline.enrich_first_seen(df.copy())

        r0, r1, r2 = out.iloc[0], out.iloc[1], out.iloc[2]
        assert r0["First_Time"] == "W24/2026", r0["First_Time"]
        assert r0["Duration"] >= 3, r0["Duration"]
        # Brand-new item: first appearance is the current run -> current week, duration 0
        assert r1["First_Time"] == _now_week(), r1["First_Time"]
        assert r1["Duration"] == 0, r1["Duration"]
        # Int product number must match the string key in history
        assert r2["First_Time"] == "W01/2026", r2["First_Time"]

        # Priority is derived from Duration
        assert r0["Priority"] in ("Mid", "High"), r0["Priority"]  # duration >=3
        assert r1["Priority"] == "Low", r1["Priority"]            # brand new, duration 0

        # Empty input returns empty (no crash)
        assert pipeline.enrich_first_seen(pd.DataFrame()).empty
    finally:
        history.get_first_seen_map = original
    print("PASS test_enrich_first_seen")


def test_sort_owner_then_duration_desc():
    # Adversarial: owner ties, duration ties (stable order must be preserved).
    data = pd.DataFrame([
        {"Owner": "Becky", "Duration": 3, "id": 1},
        {"Owner": "Becky", "Duration": 7, "id": 2},
        {"Owner": "Alice", "Duration": 1, "id": 3},
        {"Owner": "Becky", "Duration": 7, "id": 4},  # tie with id 2 -> id 2 stays first
        {"Owner": "Alice", "Duration": 1, "id": 5},  # tie with id 3 -> id 3 stays first
        {"Owner": "GC DRP", "Duration": 0, "id": 6},
    ])
    s = data.sort_values(["Owner", "Duration"], ascending=[True, False], kind="mergesort")
    # Owner asc: Alice, Becky, GC DRP; within owner Duration desc; ties stable.
    assert list(s["id"]) == [3, 5, 2, 4, 1, 6], list(s["id"])
    print("PASS test_sort_owner_then_duration_desc")


def test_dashboard_template_wiring():
    t = dashboard._get_template()
    assert "filtered = filtered.slice().sort" in t, "dashboard sort missing"
    assert "<th>First Time</th><th>Duration</th><th>Priority</th>" in t, "dashboard headers missing"
    # Duration cell must be centered
    assert "'<td style=\"text-align:center\">' + (e.duration" in t, "duration not centered"
    # Priority colored tag classes present
    assert ".tag-high" in t and ".tag-mid" in t and ".tag-low" in t, "priority tag css missing"
    print("PASS test_dashboard_template_wiring")


if __name__ == "__main__":
    test_week_helpers()
    test_priority_buckets()
    test_enrich_first_seen()
    test_sort_owner_then_duration_desc()
    test_dashboard_template_wiring()
    print("\nALL ADVERSARIAL TESTS PASSED")
