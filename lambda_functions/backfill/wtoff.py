"""Backfill: remove legacy wtoff=1 observations.

SQS message: {"type": "backfill:wtoff", "feature_id": "Magat"}

When the water mask detected no water pixels, older processor runs still wrote
a row with `wtoff = 1` and files named `..._filter_wtoff.tif/csv.gz/png`.
The current processor rejects those scenes as nodata instead. This handler
cleans up the leftovers:

1. Deletes R2 CSV / TIF / PNG artifacts for each wtoff=1 row.
2. Rewrites (or deletes) each affected per-year Parquet file in R2 to drop
   rows whose `date` matches a doomed observation.
3. Deletes the temperature_metadata row.
4. Reclassifies the matching processing_jobs row from 'success' -> 'nodata'.
5. Recomputes features.latest_date.

This must run BEFORE the 0022_drop_wtoff.sql migration is applied in prod,
because it filters D1 by `WHERE wtoff = 1`.
"""

import io
from collections import defaultdict

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from backfill.base import get_s3_client, get_bucket_name
from common.dates import to_parquet_date_utc
from common.parquet import (
    align_parquet_table_to_feature_schema,
    parquet_date_type,
    parquet_feature_schema,
)
from d1 import query_d1


def _delete_r2_keys(s3_client, bucket, keys):
    """Delete a list of R2 keys, ignoring missing ones."""
    for key in keys:
        if not key:
            continue
        try:
            s3_client.delete_object(Bucket=bucket, Key=key)
            print(f"    Deleted R2: {key}")
        except Exception as e:
            print(f"    Warning: could not delete {key}: {e}")


def _r2_keys_for_observation(csv_path, tif_path, png_path):
    keys = []
    if csv_path:
        keys.append(csv_path)
    if tif_path:
        keys.append(tif_path)
    if png_path:
        for suffix in ("_relative.png", "_fixed.png", "_gray.png"):
            keys.append(png_path + suffix)
    return keys


def _year_key_for(parquet_path, date_str):
    """Mirror common.parquet.upload_parquet_to_r2: `{base}_YYYY.parquet`."""
    year = to_parquet_date_utc(date_str).year
    return parquet_path.replace(".parquet", f"_{year}.parquet")


def _rewrite_parquet_excluding_dates(s3_client, bucket, year_key, doomed_dates):
    """Drop rows whose `date` is in doomed_dates from a per-year Parquet.

    `doomed_dates` is an iterable of date strings (e.g. "2024-03-15"). The
    year-file is read fully into memory, filtered at the row level (not row
    group — `upload_parquet_to_r2` sorts by (lon, lat) and writes a single
    sorted group), and either rewritten sorted by (lon, lat) or deleted
    entirely if empty. If the year-file is missing the call is a no-op.
    """
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=year_key)
    except s3_client.exceptions.NoSuchKey:
        print(f"    Parquet already absent: {year_key}")
        return
    except Exception as e:
        # Some S3 clients surface missing objects as ClientError 404
        msg = str(e)
        if "NoSuchKey" in msg or "404" in msg:
            print(f"    Parquet already absent: {year_key}")
            return
        raise

    raw = obj["Body"].read()
    existing = pq.read_table(pa.BufferReader(raw))
    existing = align_parquet_table_to_feature_schema(existing)
    before = existing.num_rows

    ts_type = parquet_date_type()
    doomed_values = pa.array(
        [to_parquet_date_utc(d) for d in doomed_dates],
        type=ts_type,
    )
    keep_mask = pc.invert(pc.is_in(existing.column("date"), value_set=doomed_values))
    filtered = existing.filter(keep_mask)
    after = filtered.num_rows
    removed = before - after

    if after == 0:
        try:
            s3_client.delete_object(Bucket=bucket, Key=year_key)
            print(f"    Deleted empty parquet {year_key} (removed {removed} rows)")
        except Exception as e:
            print(f"    Warning: could not delete {year_key}: {e}")
        return

    # Re-sort by (longitude, latitude) — same ordering as upload_parquet_to_r2
    sort_indices = pc.sort_indices(
        filtered,
        sort_keys=[("longitude", "ascending"), ("latitude", "ascending")],
    )
    filtered = filtered.take(sort_indices)

    buf = io.BytesIO()
    pq.write_table(filtered, buf, compression="zstd")
    buf.seek(0)
    s3_client.put_object(
        Bucket=bucket,
        Key=year_key,
        Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )
    print(
        f"    Rewrote parquet {year_key}: {before} -> {after} rows "
        f"(removed {removed})"
    )


def handle(body: dict):
    feature_id = body["feature_id"]
    print(f"[backfill:wtoff][{feature_id}] Starting wtoff cleanup")

    s3 = get_s3_client()
    bucket = get_bucket_name()

    # --- Find wtoff=1 rows ---
    result = query_d1(
        "SELECT date, csv_path, tif_path, png_path, parquet_path "
        "FROM temperature_metadata "
        "WHERE feature_id = ? AND wtoff = 1",
        [feature_id],
        fatal=True,
    )
    try:
        rows = result["result"][0]["results"]
    except (KeyError, IndexError):
        rows = []

    if not rows:
        print(f"[backfill:wtoff][{feature_id}] No wtoff rows — nothing to do")
        return

    print(f"[backfill:wtoff][{feature_id}] Found {len(rows)} wtoff row(s)")

    # --- Step 1: delete per-observation R2 artifacts (CSV/TIF/PNG) ---
    # Also group doomed dates by their per-year parquet key for step 2.
    year_key_to_dates = defaultdict(set)
    for row in rows:
        date = row["date"]
        print(f"  [{feature_id}] Removing wtoff observation {date}")
        _delete_r2_keys(
            s3,
            bucket,
            _r2_keys_for_observation(
                row.get("csv_path"),
                row.get("tif_path"),
                row.get("png_path"),
            ),
        )
        parquet_path = row.get("parquet_path")
        if parquet_path:
            year_key_to_dates[_year_key_for(parquet_path, date)].add(date)

    # --- Step 2: rewrite per-year parquet files to drop doomed dates ---
    for year_key, dates in year_key_to_dates.items():
        print(f"  [{feature_id}] Cleaning parquet {year_key} ({len(dates)} date(s))")
        try:
            _rewrite_parquet_excluding_dates(s3, bucket, year_key, dates)
        except Exception as e:
            print(f"    ERROR rewriting {year_key}: {e}")

    # --- Step 3 + 4: drop D1 rows and reclassify jobs ---
    deleted = 0
    reclassified = 0
    for row in rows:
        date = row["date"]
        query_d1(
            "DELETE FROM temperature_metadata WHERE feature_id = ? AND date = ?",
            [feature_id, date],
            fatal=False,
        )
        query_d1(
            "UPDATE processing_jobs SET status = 'nodata' "
            "WHERE feature_id = ? AND date = ? AND status = 'success'",
            [feature_id, date],
            fatal=False,
        )
        deleted += 1
        reclassified += 1

    # --- Step 5: refresh features.latest_date ---
    latest_result = query_d1(
        "SELECT MAX(date) as latest FROM temperature_metadata WHERE feature_id = ?",
        [feature_id],
        fatal=False,
    )
    try:
        latest = latest_result["result"][0]["results"][0]["latest"]
    except (KeyError, IndexError, TypeError):
        latest = None
    if latest:
        query_d1(
            "UPDATE features SET latest_date = ? WHERE id = ?",
            [latest, feature_id],
            fatal=False,
        )
        print(f"  [{feature_id}] Updated latest_date to {latest}")
    else:
        print(f"  [{feature_id}] No remaining observations")

    print(
        f"[backfill:wtoff][{feature_id}] Done: "
        f"deleted={deleted} reclassified={reclassified} "
        f"parquet_years_touched={len(year_key_to_dates)}"
    )
