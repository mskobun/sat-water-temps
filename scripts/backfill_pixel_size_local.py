"""Backfill pixel_size + pixel_size_x in the LOCAL D1 SQLite database.

Downloads each TIF from R2, computes separate X/Y pixel sizes, updates SQLite.

Usage:
    uv run python scripts/backfill_pixel_size_local.py          # dry run
    uv run python scripts/backfill_pixel_size_local.py --apply  # update SQLite
"""

import argparse
import math
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


def compute_pixel_size(tif_path):
    """Return (pixel_size_x, pixel_size_y) in WGS84 degrees."""
    with rasterio.open(tif_path) as src:
        tf = src.transform
        crs = src.crs

        if crs and crs.is_projected:
            bounds = src.bounds
            mid_lat = (bounds.top + bounds.bottom) / 2
            pixel_m = abs(tf.a)
            pixel_deg_x = pixel_m / (111320 * math.cos(math.radians(mid_lat)))
            pixel_deg_y = pixel_m / 110540
            return pixel_deg_x, pixel_deg_y
        else:
            return abs(tf.a), abs(tf.e)


def main():
    parser = argparse.ArgumentParser(description="Backfill pixel_size_x in local D1")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

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

    rows = conn.execute(
        "SELECT feature_id, date, tif_path, source FROM temperature_metadata "
        "WHERE pixel_size_x IS NULL AND tif_path IS NOT NULL"
    ).fetchall()

    print(f"Found {len(rows)} record(s) to backfill\n")

    updated = 0
    failed = 0

    for row in rows:
        feature_id = row["feature_id"]
        date = row["date"]
        tif_key = row["tif_path"]
        source = row["source"] or "ecostress"

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            s3.download_file(R2_BUCKET_NAME, tif_key, tmp_path)
            px, py = compute_pixel_size(tmp_path)

            if dry_run:
                print(f"  [DRY] {feature_id} {date} ({source}): x={px:.8f} y={py:.8f}")
            else:
                conn.execute(
                    "UPDATE temperature_metadata SET pixel_size = ?, pixel_size_x = ? "
                    "WHERE feature_id = ? AND date = ?",
                    [py, px, feature_id, date],
                )
                if updated % 50 == 0:
                    conn.commit()
                print(f"  {feature_id} {date} ({source}): x={px:.8f} y={py:.8f}")
            updated += 1

        except Exception as e:
            print(f"  FAILED {feature_id} {date}: {e}")
            failed += 1

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"\nDone{' (DRY RUN)' if dry_run else ''}:  updated={updated}  failed={failed}")
    if dry_run and updated > 0:
        print("Run with --apply to actually update.")


if __name__ == "__main__":
    main()
