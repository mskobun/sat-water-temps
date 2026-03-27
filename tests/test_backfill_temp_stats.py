import gzip
import io
import os
import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from backfill.temp_stats import handle


def test_temp_stats_backfill_updates_missing_stats():
    csv_bytes = gzip.compress(
        pd.DataFrame({"LST_filter": [300.0, 302.0, 304.0]}).to_csv(index=False).encode("utf-8")
    )
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_bytes)}

    updates = []

    def fake_query_d1(sql, params, fatal=True):
        if sql.startswith("SELECT date, csv_path, mean_temp, median_temp, std_dev"):
            return {
                "result": [
                    {
                        "results": [
                            {
                                "date": "2024-12-27",
                                "csv_path": "LANDSAT/Magat/lake/Magat_lake_2024-12-27_filter.csv.gz",
                                "mean_temp": None,
                                "median_temp": None,
                                "std_dev": None,
                            }
                        ]
                    }
                ]
            }
        updates.append((sql, params, fatal))
        return {"success": True}

    with patch("backfill.temp_stats.query_d1", side_effect=fake_query_d1), patch(
        "backfill.temp_stats.get_s3_client", return_value=mock_s3
    ), patch("backfill.temp_stats.get_bucket_name", return_value="multitifs"):
        handle({"feature_id": "Magat"})

    assert len(updates) == 1
    _, params, _ = updates[0]
    assert params[0] == 300.0
    assert params[1] == 304.0
    assert params[2] == 302.0
    assert params[3] == 302.0
    assert params[4] == pytest.approx(1.632993161855452)
    assert params[5:] == ["Magat", "2024-12-27"]


def test_temp_stats_backfill_handles_transparently_decompressed_csv():
    csv_bytes = pd.DataFrame({"LST_filter": [300.0, 302.0, 304.0]}).to_csv(index=False).encode(
        "utf-8"
    )
    mock_s3 = MagicMock()
    mock_s3.get_object.return_value = {"Body": io.BytesIO(csv_bytes)}

    updates = []

    def fake_query_d1(sql, params, fatal=True):
        if sql.startswith("SELECT date, csv_path, mean_temp, median_temp, std_dev"):
            return {
                "result": [
                    {
                        "results": [
                            {
                                "date": "2026-03-22T05:33:05",
                                "csv_path": "ECO/Ambuclao/lake/Ambuclao_lake_2026081053305_filter.csv.gz",
                                "mean_temp": None,
                                "median_temp": None,
                                "std_dev": None,
                            }
                        ]
                    }
                ]
            }
        updates.append((sql, params, fatal))
        return {"success": True}

    with patch("backfill.temp_stats.query_d1", side_effect=fake_query_d1), patch(
        "backfill.temp_stats.get_s3_client", return_value=mock_s3
    ), patch("backfill.temp_stats.get_bucket_name", return_value="multitifs"):
        handle({"feature_id": "Ambuclao"})

    assert len(updates) == 1
    _, params, _ = updates[0]
    assert params[0] == 300.0
    assert params[1] == 304.0
    assert params[2] == 302.0
    assert params[3] == 302.0
    assert params[4] == pytest.approx(1.632993161855452)
    assert params[5:] == ["Ambuclao", "2026-03-22T05:33:05"]
