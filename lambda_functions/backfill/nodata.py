"""Backfill: reclassify zero-valid-pixel observations and clean up stale data.

SQS message: {"type": "backfill:nodata", "feature_id": "Magat"}

A) Finds temperature_metadata rows with data_points=0, deletes their R2 files
   (CSV, TIF, PNGs), removes the metadata row, and updates the corresponding
   processing_job to status='nodata'.

B) Reclassifies "Missing required layers" failures from 'failed' to 'nodata'.

C) Updates features.latest_date to reflect remaining observations.
"""

import json

from backfill.base import get_s3_client, get_bucket_name
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


def _r2_keys_for_observation(csv_path, tif_path, png_path, filter_stats_json):
    """Compute all R2 keys associated with an observation."""
    keys = []
    if csv_path:
        keys.append(csv_path)
    if tif_path:
        keys.append(tif_path)
    if png_path:
        for suffix in ["_relative.png", "_fixed.png", "_gray.png"]:
            keys.append(png_path + suffix)
    return keys


def handle(body: dict):
    feature_id = body["feature_id"]
    print(f"[backfill:nodata][{feature_id}] Starting nodata backfill")

    s3 = get_s3_client()
    bucket = get_bucket_name()

    # --- A) Remove zero-valid-pixel observations ---
    result = query_d1(
        "SELECT date, csv_path, tif_path, png_path, filter_stats "
        "FROM temperature_metadata "
        "WHERE feature_id = ? AND data_points = 0",
        [feature_id],
        fatal=True,
    )
    try:
        zero_rows = result["result"][0]["results"]
    except (KeyError, IndexError):
        zero_rows = []

    deleted = 0
    reclassified_success = 0

    for row in zero_rows:
        date = row["date"]
        print(f"  [{feature_id}] Removing zero-data observation {date}")

        # Delete R2 files
        keys = _r2_keys_for_observation(
            row.get("csv_path"), row.get("tif_path"),
            row.get("png_path"), row.get("filter_stats"),
        )
        _delete_r2_keys(s3, bucket, keys)

        # Build filter_stats metadata for the job
        filter_stats = row.get("filter_stats")
        metadata_json = None
        if filter_stats:
            try:
                parsed = json.loads(filter_stats) if isinstance(filter_stats, str) else filter_stats
                metadata_json = json.dumps({"filter_stats": parsed})
            except (json.JSONDecodeError, TypeError):
                pass

        # Delete temperature_metadata row
        query_d1(
            "DELETE FROM temperature_metadata WHERE feature_id = ? AND date = ?",
            [feature_id, date],
            fatal=False,
        )

        # Reclassify matching processing_job from success → nodata
        update_params = [date, feature_id]
        update_sql = (
            "UPDATE processing_jobs SET status = 'nodata'"
        )
        if metadata_json:
            update_sql += ", metadata = ?"
            update_params = [metadata_json, date, feature_id]

        update_sql += " WHERE date = ? AND feature_id = ? AND status = 'success'"
        query_d1(update_sql, update_params, fatal=False)

        deleted += 1
        reclassified_success += 1

    # --- B) Reclassify "Missing required layers" failures ---
    result = query_d1(
        "SELECT id FROM processing_jobs "
        "WHERE feature_id = ? AND status = 'failed' "
        "AND error_message LIKE 'Missing required layers%'",
        [feature_id],
        fatal=True,
    )
    try:
        missing_rows = result["result"][0]["results"]
    except (KeyError, IndexError):
        missing_rows = []

    reclassified_failed = 0
    for row in missing_rows:
        query_d1(
            "UPDATE processing_jobs SET status = 'nodata' WHERE id = ?",
            [row["id"]],
            fatal=False,
        )
        reclassified_failed += 1

    # --- C) Update features.latest_date ---
    if deleted > 0:
        result = query_d1(
            "SELECT MAX(date) as latest FROM temperature_metadata WHERE feature_id = ?",
            [feature_id],
            fatal=False,
        )
        try:
            latest = result["result"][0]["results"][0]["latest"]
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
        f"[backfill:nodata][{feature_id}] Done: "
        f"deleted={deleted} reclassified_success={reclassified_success} "
        f"reclassified_failed={reclassified_failed}"
    )
