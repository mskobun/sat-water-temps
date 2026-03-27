"""Backfill mean/median/std temperature stats from archived CSV.gz files in R2.

SQS message: {"type": "backfill:temp_stats", "feature_id": "Magat"}
Optional: {"force": true} to overwrite existing values.
"""

import gzip
import io

import pandas as pd

from backfill.base import get_bucket_name, get_s3_client
from d1 import query_d1
from processor import summarize_temperature_series


def _read_csv_from_r2(s3_client, bucket: str, key: str) -> pd.DataFrame:
    resp = s3_client.get_object(Bucket=bucket, Key=key)
    raw = resp["Body"].read()
    # R2 may transparently decompress ContentEncoding:gzip objects on read,
    # so a .csv.gz key is not guaranteed to return gzipped bytes.
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return pd.read_csv(io.BytesIO(raw))


def handle(body: dict):
    feature_id = body["feature_id"]
    force = bool(body.get("force", False))

    print(f"[backfill:temp_stats][{feature_id}] Starting temperature stats backfill")

    result = query_d1(
        "SELECT date, csv_path, mean_temp, median_temp, std_dev "
        "FROM temperature_metadata "
        "WHERE feature_id = ? AND csv_path IS NOT NULL "
        "ORDER BY date",
        [feature_id],
        fatal=True,
    )
    try:
        rows = result["result"][0]["results"]
    except (KeyError, IndexError):
        rows = []

    if not rows:
        print(f"[backfill:temp_stats][{feature_id}] No rows with csv_path, skipping")
        return

    s3 = get_s3_client()
    bucket = get_bucket_name()
    updated = 0
    skipped = 0
    failed = 0

    for row in rows:
        date = row["date"]
        csv_key = row["csv_path"]
        has_existing_stats = all(row.get(key) is not None for key in ("mean_temp", "median_temp", "std_dev"))
        if has_existing_stats and not force:
            print(f"[backfill:temp_stats][{feature_id}] Skip {date}: stats already set")
            skipped += 1
            continue

        try:
            df = _read_csv_from_r2(s3, bucket, csv_key)
            temp_col = next(
                (col for col in ("LST_filter", "temperature") if col in df.columns),
                None,
            )
            if not temp_col:
                raise ValueError(f"missing temperature column in {csv_key}")

            stats = summarize_temperature_series(df[temp_col])
            query_d1(
                "UPDATE temperature_metadata "
                "SET min_temp = ?, max_temp = ?, mean_temp = ?, median_temp = ?, std_dev = ? "
                "WHERE feature_id = ? AND date = ?",
                [
                    stats["min_temp"],
                    stats["max_temp"],
                    stats["mean_temp"],
                    stats["median_temp"],
                    stats["std_dev"],
                    feature_id,
                    date,
                ],
                fatal=False,
            )
            print(
                f"[backfill:temp_stats][{feature_id}] Updated {date}: "
                f"mean={stats['mean_temp']} median={stats['median_temp']} std={stats['std_dev']}"
            )
            updated += 1
        except Exception as ex:
            print(f"[backfill:temp_stats][{feature_id}] FAILED {date} {csv_key}: {ex}")
            failed += 1

    print(
        f"[backfill:temp_stats][{feature_id}] Done: updated={updated} skipped={skipped} failed={failed}"
    )
