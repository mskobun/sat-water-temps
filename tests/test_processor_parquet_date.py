"""Parquet feature schema: UTC timestamp `date` column. Run backfill to migrate old files."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.parquet import (  # noqa: E402
    _row_group_first_date_key,
    align_parquet_table_to_feature_schema,
    parquet_date_type,
    parquet_feature_schema,
    upload_parquet_to_r2,
)
from common.storage import Boto3R2Backend  # noqa: E402
from common.dates import to_parquet_date_utc  # noqa: E402


@pytest.fixture
def repo_root(monkeypatch):
    root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(root)
    yield root


def test_parquet_feature_schema_date_is_timestamp_us_utc(repo_root):
    schema = parquet_feature_schema()
    assert schema.field("date").type == parquet_date_type()
    assert schema.field("date").type.equals(pa.timestamp("us", tz="UTC"))


def test_align_float32_coordinates(repo_root):
    dt = to_parquet_date_utc("2024-12-27T04:19:23")
    tbl = pa.table(
        {
            "longitude": pa.array([104.88], pa.float32()),
            "latitude": pa.array([17.99], pa.float32()),
            "temperature": pa.array([305.0], pa.float32()),
            "date": pa.array([dt], type=pa.timestamp("us", tz="UTC")),
            "row": pa.array([0], pa.int32()),
            "col": pa.array([0], pa.int32()),
        }
    )
    out = align_parquet_table_to_feature_schema(tbl)
    assert out.schema.equals(parquet_feature_schema())
    assert out.column("longitude").type == pa.float64()
    assert out.column("date")[0].as_py() == dt


def test_row_group_first_date_key_timestamp_only(repo_root):
    dt = to_parquet_date_utc("2024362041923")
    tbl_ts = pa.table({"date": pa.array([dt], type=pa.timestamp("us", tz="UTC"))})
    assert _row_group_first_date_key(tbl_ts) == dt


def test_row_group_first_date_key_rejects_string_date(repo_root):
    tbl = pa.table({"date": pa.array(["2024-12-27T04:19:23"], pa.string())})
    with pytest.raises(ValueError, match="re-run parquet backfill"):
        _row_group_first_date_key(tbl)


def test_upload_parquet_replaces_row_group_same_instant(repo_root):
    """Re-uploading the same observation time should drop the old row group, not duplicate."""
    dt = to_parquet_date_utc("2024362041923")
    existing = pa.table(
        {
            "longitude": pa.array([1.0, 2.0], pa.float64()),
            "latitude": pa.array([3.0, 4.0], pa.float64()),
            "temperature": pa.array([300.0, 301.0], pa.float32()),
            "date": pa.array([dt, dt], type=pa.timestamp("us", tz="UTC")),
            "row": pa.array([0, 1], pa.int32()),
            "col": pa.array([0, 1], pa.int32()),
        }
    )
    buf = io.BytesIO()
    pq.write_table(existing, buf, compression="zstd")
    existing_bytes = buf.getvalue()

    captured = {}

    def get_object(Bucket, Key):
        return {"Body": io.BytesIO(existing_bytes)}

    def put_object(Bucket, Key, Body, ContentType=None):
        captured["body"] = Body

    s3 = MagicMock()
    s3.get_object.side_effect = get_object
    s3.put_object.side_effect = put_object

    df = pd.DataFrame(
        {
            "longitude": [9.0],
            "latitude": [9.0],
            "LST_filter": [299.0],
            "row": [5],
            "col": [5],
        }
    )

    upload_parquet_to_r2(Boto3R2Backend(s3), "bucket", "ECO/X/lake/X_lake.parquet", df, "2024362041923")

    assert "body" in captured
    pf = pq.ParquetFile(io.BytesIO(captured["body"]))
    assert pf.metadata.num_row_groups == 1
    table = pf.read()
    assert table.num_rows == 1
    assert table.column("longitude")[0].as_py() == 9.0
