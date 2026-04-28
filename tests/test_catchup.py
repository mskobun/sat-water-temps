import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.catchup import (
    CatchupSettings,
    calculate_catchup_window,
    completed_feature_days,
    combined_bbox,
    feature_id_for_polygon,
    filter_uncompleted_bodies,
)


def test_combined_bbox_covers_all_polygons():
    polygons = [
        {"bbox": [1, 2, 3, 4]},
        {"bbox": [-1, 5, 2, 8]},
    ]

    assert combined_bbox(polygons) == (-1, 2, 3, 8)


def test_feature_id_for_lake_omits_location():
    assert feature_id_for_polygon({"name": "Magat", "location": "lake"}) == "Magat"


def test_feature_id_for_non_lake_includes_location():
    assert feature_id_for_polygon({"name": "Magat", "location": "river"}) == "Magat/river"


def test_calculate_catchup_window_uses_overlap_and_caps_oldest_chunk_first():
    window = calculate_catchup_window(
        latest_processed="2026-03-30",
        latest_catalog="2026-04-30",
        settings=CatchupSettings(enabled=True, overlap_days=3, max_days=21),
        fallback_start="2026-04-23",
        fallback_end="2026-04-24",
    )

    assert window.start_date == "2026-03-27"
    assert window.end_date == "2026-04-16"
    assert window.reason == "catchup"


def test_calculate_catchup_window_without_prior_data_limits_to_max_days():
    window = calculate_catchup_window(
        latest_processed=None,
        latest_catalog="2026-04-30",
        settings=CatchupSettings(enabled=True, overlap_days=3, max_days=21),
        fallback_start="2026-04-23",
        fallback_end="2026-04-24",
    )

    assert window.start_date == "2026-04-10"
    assert window.end_date == "2026-04-30"


def test_calculate_catchup_window_clamps_when_processed_is_after_catalog():
    window = calculate_catchup_window(
        latest_processed="2026-04-30",
        latest_catalog="2026-04-20",
        settings=CatchupSettings(enabled=True, overlap_days=3, max_days=21),
        fallback_start="2026-04-23",
        fallback_end="2026-04-24",
    )

    assert window.start_date == "2026-04-17"
    assert window.end_date == "2026-04-20"


def test_calculate_catchup_window_falls_back_when_disabled():
    window = calculate_catchup_window(
        latest_processed="2026-03-30",
        latest_catalog="2026-04-30",
        settings=CatchupSettings(enabled=False, overlap_days=3, max_days=21),
        fallback_start="2026-04-23",
        fallback_end="2026-04-24",
    )

    assert window.start_date == "2026-04-23"
    assert window.end_date == "2026-04-24"
    assert window.reason == "catchup_disabled"


def test_completed_feature_days_reads_metadata_and_completed_jobs(monkeypatch):
    def fake_query(sql, params, fatal=False):
        assert params == [
            "ecostress",
            "2026-03-27",
            "2026-04-16",
            "ecostress_process",
            "2026-03-27",
            "2026-04-16",
        ]
        return {
            "result": [
                {
                    "results": [
                        {"feature_id": "Magat", "day": "2026-03-30"},
                        {"feature_id": "Magat/river", "day": "2026-03-29"},
                    ]
                }
            ]
        }

    monkeypatch.setattr("common.catchup.query_d1", fake_query)

    assert completed_feature_days(
        "ecostress",
        "ecostress_process",
        "2026-03-27",
        "2026-04-16",
    ) == {("Magat", "2026-03-30"), ("Magat/river", "2026-03-29")}


def test_filter_uncompleted_bodies_skips_completed_feature_days(monkeypatch):
    monkeypatch.setattr(
        "common.catchup.completed_feature_days",
        lambda *args, **kwargs: {("Magat", "2026-03-30")},
    )
    bodies = [
        {"name": "Magat", "location": "lake", "date": "2026-03-30T02:30:11"},
        {"name": "Angat", "location": "lake", "date": "2026-03-30T02:30:11"},
    ]

    remaining = list(
        filter_uncompleted_bodies(
            bodies,
            source="ecostress",
            job_type="ecostress_process",
            start_day="2026-03-27",
            end_day="2026-04-16",
        )
    )

    assert remaining == [bodies[1]]
