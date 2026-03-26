"""Backfill source_crs + transform_a..f in LOCAL D1 SQLite from GeoTIFFs in R2.

Same idea as lambda_functions/backfill/raster_meta.py but writes to the Wrangler
SQLite file instead of remote D1.

Usage:
    uv run python scripts/backfill_raster_meta_local.py              # dry run, NamTheun2%
    uv run python scripts/backfill_raster_meta_local.py --apply
    uv run python scripts/backfill_raster_meta_local.py --apply Magat

Requires: R2_* env vars (see backfill_pixel_size_local.py).
"""

import argparse
import os
import sqlite3
import sys
import tempfile

import boto3
import rasterio
from dotenv import load_dotenv

load_dotenv()

DB_PATH = ".wrangler/state/v3/d1/miniflare-D1DatabaseObject/4096e3fb508d875520342c6f716b66d65fa16296ae16d7c2d6d40eba30883e65.sqlite"

R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def affine_row(tf):
    return (
        float(tf.a),
        float(tf.b),
        float(tf.c),
        float(tf.d),
        float(tf.e),
        float(tf.f),
    )


def main():
    parser = argparse.ArgumentParser(description="Backfill raster CRS/transform in local D1")
    parser.add_argument(
        "feature_prefix",
        nargs="?",
        default="NamTheun2",
        help="Match feature_id LIKE '<prefix>%%' (default: NamTheun2)",
    )
    parser.add_argument("--apply", action="store_true", help="Write updates to SQLite")
    args = parser.parse_args()
    dry_run = not args.apply
    prefix = args.feature_prefix

    if not os.path.exists(DB_PATH):
        print(f"Error: DB not found at {DB_PATH}")
        sys.exit(1)

    for var in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(var):
            print(f"Error: {var} not set")
            sys.exit(1)

    s3 = get_s3_client()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    like_pat = f"{prefix}%"
    rows = conn.execute(
        "SELECT feature_id, date, tif_path, source_crs FROM temperature_metadata "
        "WHERE feature_id LIKE ? AND tif_path IS NOT NULL "
        "ORDER BY date",
        [like_pat],
    ).fetchall()

    print(f"Found {len(rows)} row(s) with tif_path for feature_id LIKE {like_pat!r}\n")

    updated = 0
    failed = 0

    for row in rows:
        feature_id = row["feature_id"]
        date = row["date"]
        tif_key = row["tif_path"]
        if row["source_crs"] and not args.apply:
            pass

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
                tmp_path = tmp.name
            s3.download_file(R2_BUCKET_NAME, tif_key, tmp_path)

            with rasterio.open(tmp_path) as src:
                crs_str = src.crs.to_string() if src.crs else None
                a, b, c, d, e, f = affine_row(src.transform)

            if dry_run:
                print(
                    f"  [DRY] {feature_id} {date}: crs={crs_str} "
                    f"a={a:.6f} b={b:.6f} c={c:.2f} d={d:.6f} e={e:.6f} f={f:.2f}"
                )
            else:
                conn.execute(
                    "UPDATE temperature_metadata SET source_crs = ?, "
                    "transform_a = ?, transform_b = ?, transform_c = ?, "
                    "transform_d = ?, transform_e = ?, transform_f = ? "
                    "WHERE feature_id = ? AND date = ?",
                    [crs_str, a, b, c, d, e, f, feature_id, date],
                )
                print(f"  OK {feature_id} {date}: crs={crs_str}")
            updated += 1
        except Exception as ex:
            print(f"  FAILED {feature_id} {date} {tif_key}: {ex}")
            failed += 1
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"\nDone: processed={updated} failed={failed} apply={not dry_run}")


if __name__ == "__main__":
    main()
