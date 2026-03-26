"""Backfill source_crs and affine transform (a..f) from GeoTIFFs in R2.

SQS message: {"type": "backfill:raster_meta", "feature_id": "Magat"}
Optional: {"force": true} to overwrite existing source_crs/transform columns.

Reads each row's tif_path from D1, downloads the TIF, and updates D1 with
rasterio CRS + Affine coefficients matching insert_metadata_to_d1.
"""

import os
import tempfile

import rasterio

from backfill.base import get_bucket_name, get_s3_client
from d1 import query_d1


def _affine_to_row(tf) -> tuple:
    return (
        float(tf.a),
        float(tf.b),
        float(tf.c),
        float(tf.d),
        float(tf.e),
        float(tf.f),
    )


def handle(body: dict):
    feature_id = body["feature_id"]
    force = bool(body.get("force", False))

    print(f"[backfill:raster_meta][{feature_id}] Starting raster geometry backfill")

    result = query_d1(
        "SELECT date, tif_path, source_crs FROM temperature_metadata "
        "WHERE feature_id = ? AND tif_path IS NOT NULL",
        [feature_id],
        fatal=True,
    )
    try:
        rows = result["result"][0]["results"]
    except (KeyError, IndexError):
        rows = []

    if not rows:
        print(f"[backfill:raster_meta][{feature_id}] No rows with tif_path, skipping")
        return

    s3 = get_s3_client()
    bucket = get_bucket_name()
    updated = 0
    skipped = 0
    failed = 0

    for row in rows:
        date = row["date"]
        tif_key = row["tif_path"]
        existing_crs = row.get("source_crs")
        if existing_crs and not force:
            print(f"[backfill:raster_meta][{feature_id}] Skip {date}: source_crs already set")
            skipped += 1
            continue

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
                tmp_path = tmp.name
            s3.download_file(bucket, tif_key, tmp_path)

            with rasterio.open(tmp_path) as src:
                crs_str = src.crs.to_string() if src.crs else None
                a, b, c, d, e, f = _affine_to_row(src.transform)

            query_d1(
                "UPDATE temperature_metadata SET source_crs = ?, "
                "transform_a = ?, transform_b = ?, transform_c = ?, "
                "transform_d = ?, transform_e = ?, transform_f = ? "
                "WHERE feature_id = ? AND date = ?",
                [crs_str, a, b, c, d, e, f, feature_id, date],
                fatal=False,
            )
            print(
                f"[backfill:raster_meta][{feature_id}] Updated {date}: crs={crs_str}"
            )
            updated += 1
        except Exception as ex:
            print(f"[backfill:raster_meta][{feature_id}] FAILED {date} {tif_key}: {ex}")
            failed += 1
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    print(
        f"[backfill:raster_meta][{feature_id}] Done: updated={updated} skipped={skipped} failed={failed}"
    )
