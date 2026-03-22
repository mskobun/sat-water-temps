"""Backfill pixel_size for temperature_metadata records that are missing it.

Downloads each TIF from R2, reads the raster transform, computes pixel_size
in WGS84 degrees, and updates D1.

- ECOSTRESS TIFs are already in WGS84: pixel_size = avg(|tf.a|, |tf.e|)
- Landsat TIFs are in UTM: convert meters → degrees using centroid latitude

Usage:
    # Dry run (default)
    uv run python scripts/backfill_pixel_size.py

    # Actually update D1
    uv run python scripts/backfill_pixel_size.py --apply

Requires env vars:
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
    CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, D1_DATABASE_ID
"""

import argparse
import math
import os
import sys
import tempfile

import boto3
import rasterio
import requests

R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")

CF_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CF_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")
D1_DATABASE_ID = os.environ.get("D1_DATABASE_ID")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def query_d1(sql, params=None):
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{D1_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {CF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"sql": sql}
    if params:
        payload["params"] = params
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def compute_pixel_size(tif_path, source):
    """Compute WGS84 pixel size in degrees from a TIF file.

    Returns (pixel_size_x, pixel_size_y) — longitude and latitude sizes.
    """
    with rasterio.open(tif_path) as src:
        tf = src.transform
        crs = src.crs

        if crs and crs.is_projected:
            # Landsat (UTM) — convert meters to degrees
            bounds = src.bounds
            mid_lat = (bounds.top + bounds.bottom) / 2
            pixel_m = abs(tf.a)
            pixel_deg_x = pixel_m / (111320 * math.cos(math.radians(mid_lat)))
            pixel_deg_y = pixel_m / 110540
            return pixel_deg_x, pixel_deg_y
        else:
            # ECOSTRESS (WGS84) — direct from transform
            return abs(tf.a), abs(tf.e)


def main():
    parser = argparse.ArgumentParser(description="Backfill pixel_size in D1")
    parser.add_argument("--apply", action="store_true", help="Actually update D1 (default is dry run)")
    args = parser.parse_args()
    dry_run = not args.apply

    for var in ("R2_ENDPOINT", "CF_ACCOUNT_ID", "CF_API_TOKEN", "D1_DATABASE_ID"):
        if not globals().get(var) and not os.environ.get(var):
            print(f"Error: {var} not set")
            sys.exit(1)

    s3 = get_s3_client()

    # Find records missing pixel_size_x that have a tif_path
    result = query_d1(
        "SELECT feature_id, date, tif_path, source FROM temperature_metadata "
        "WHERE pixel_size_x IS NULL AND tif_path IS NOT NULL"
    )

    rows = result.get("result", [{}])[0].get("results", [])
    print(f"Found {len(rows)} record(s) missing pixel_size_x\n")

    updated = 0
    failed = 0

    for row in rows:
        feature_id = row["feature_id"]
        date = row["date"]
        tif_key = row["tif_path"]
        source = row.get("source", "ecostress")

        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            s3.download_file(R2_BUCKET_NAME, tif_key, tmp_path)
            pixel_size_x, pixel_size_y = compute_pixel_size(tmp_path, source)

            if dry_run:
                print(f"  [DRY RUN] {feature_id} {date} ({source}): pixel_size_x={pixel_size_x:.8f} pixel_size_y={pixel_size_y:.8f}")
            else:
                query_d1(
                    "UPDATE temperature_metadata SET pixel_size = ?, pixel_size_x = ? WHERE feature_id = ? AND date = ?",
                    [pixel_size_y, pixel_size_x, feature_id, date],
                )
                print(f"  {feature_id} {date} ({source}): pixel_size_x={pixel_size_x:.8f} pixel_size_y={pixel_size_y:.8f}")
            updated += 1

        except Exception as e:
            print(f"  FAILED {feature_id} {date}: {e}")
            failed += 1

        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    print(f"\nDone{' (DRY RUN)' if dry_run else ''}:  updated={updated}  failed={failed}")
    if dry_run and updated > 0:
        print("Run with --apply to actually update D1.")


if __name__ == "__main__":
    main()
