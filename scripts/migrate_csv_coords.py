#!/usr/bin/env python3
"""
Migration script to convert existing CSVs from pixel coordinates (x, y)
to geographic coordinates (longitude, latitude).

Requires:
- boto3
- rasterio
- pandas

Usage:
    export R2_ENDPOINT=https://xxx.r2.cloudflarestorage.com
    export R2_ACCESS_KEY_ID=xxx
    export R2_SECRET_ACCESS_KEY=xxx
    export R2_BUCKET_NAME=multitifs

    python scripts/migrate_csv_coords.py
"""

import os
import sys
import tempfile
import boto3
import rasterio
import pandas as pd
from io import BytesIO
import dotenv

dotenv.load_dotenv()
# R2 configuration from environment
R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")


def get_s3_client():
    """Create S3 client for R2"""
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def list_tif_files(s3_client, prefix="ECO/"):
    """List all TIF files in the bucket"""
    tif_files = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".tif") and "_filter" in key:
                tif_files.append(key)

    return tif_files


def get_csv_key_from_tif(tif_key):
    """Derive CSV key from TIF key"""
    # TIF: ECO/name/location/name_location_date_filter.tif
    # CSV: ECO/name/location/name_location_date_filter.csv
    return tif_key.replace(".tif", ".csv")


def migrate_csv(s3_client, tif_key, csv_key):
    """Migrate a single CSV file to use lon/lat coordinates"""
    print(f"Processing: {csv_key}")

    # Download TIF to get transform
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_tif:
        try:
            s3_client.download_file(R2_BUCKET_NAME, tif_key, tmp_tif.name)
        except Exception as e:
            print(f"  ERROR downloading TIF: {e}")
            return False

        # Read transform from TIF
        try:
            with rasterio.open(tmp_tif.name) as src:
                transform = src.transform
                rows, cols = src.height, src.width
        except Exception as e:
            print(f"  ERROR reading TIF: {e}")
            os.unlink(tmp_tif.name)
            return False

        os.unlink(tmp_tif.name)

    # Download CSV
    try:
        response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=csv_key)
        csv_content = response["Body"].read().decode("utf-8")
    except Exception as e:
        print(f"  ERROR downloading CSV: {e}")
        return False

    # Parse CSV
    try:
        df = pd.read_csv(BytesIO(csv_content.encode()))
    except Exception as e:
        print(f"  ERROR parsing CSV: {e}")
        return False

    # Check if already migrated
    if "longitude" in df.columns and "latitude" in df.columns:
        print(f"  SKIP: Already has longitude/latitude columns")
        return True

    # Check if has x/y columns
    if "x" not in df.columns or "y" not in df.columns:
        print(f"  SKIP: No x/y columns found")
        return False

    # Convert pixel coordinates to geographic coordinates
    # rasterio.transform.xy expects (rows, cols) i.e. (y, x)
    lons, lats = rasterio.transform.xy(transform, df["y"].values, df["x"].values)

    # Add new columns
    df["longitude"] = lons
    df["latitude"] = lats

    # Remove old columns (optional - keeping for backward compat during transition)
    # df = df.drop(columns=["x", "y"])

    # Upload updated CSV
    try:
        updated_csv = df.to_csv(index=False)
        s3_client.put_object(
            Bucket=R2_BUCKET_NAME,
            Key=csv_key,
            Body=updated_csv.encode("utf-8"),
            ContentType="text/csv",
        )
        print(f"  OK: Migrated {len(df)} rows")
        return True
    except Exception as e:
        print(f"  ERROR uploading CSV: {e}")
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate CSVs from pixel to geographic coordinates"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List files without modifying"
    )
    parser.add_argument("--limit", type=int, help="Limit number of files to process")
    args = parser.parse_args()

    # Validate environment
    if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        print("ERROR: Missing R2 credentials in environment")
        print("Required: R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY")
        sys.exit(1)

    print(f"Connecting to R2 bucket: {R2_BUCKET_NAME}")
    s3_client = get_s3_client()

    # List all TIF files
    print("Listing TIF files...")
    tif_files = list_tif_files(s3_client)
    print(f"Found {len(tif_files)} TIF files")

    if args.limit:
        tif_files = tif_files[: args.limit]
        print(f"Limited to {args.limit} files")

    if args.dry_run:
        print("\n=== DRY RUN - Files that would be processed ===")
        for tif_key in tif_files:
            csv_key = get_csv_key_from_tif(tif_key)
            print(f"  {csv_key}")
        print(f"\nTotal: {len(tif_files)} files")
        return

    # Process each TIF/CSV pair
    success = 0
    failed = 0

    for tif_key in tif_files:
        csv_key = get_csv_key_from_tif(tif_key)

        result = migrate_csv(s3_client, tif_key, csv_key)
        if result:
            success += 1
        else:
            failed += 1

    print(f"\n=== Migration Complete ===")
    print(f"Success: {success}")
    print(f"Failed:  {failed}")


if __name__ == "__main__":
    main()
