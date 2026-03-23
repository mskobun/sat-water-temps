"""Backfill: gzip-compress existing CSV files in R2.

Downloads each CSV, gzip-compresses it, and re-uploads in place with
ContentEncoding=gzip. Skips files that are already gzipped.

Usage:
    uv run python scripts/backfill_gzip_csv.py          # dry run
    uv run python scripts/backfill_gzip_csv.py --apply   # compress in place
"""

import argparse
import gzip
import os
import sys

import boto3
from dotenv import load_dotenv

load_dotenv()

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


def list_csv_keys(s3, bucket, prefix):
    """Yield all .csv keys under a prefix."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv"):
                yield obj["Key"]


def main():
    parser = argparse.ArgumentParser(description="Gzip-compress CSVs in R2")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    dry_run = not args.apply

    for var in ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(var):
            print(f"Error: {var} not set")
            sys.exit(1)

    s3 = get_s3_client()

    keys = []
    for prefix in ("ECO/", "LANDSAT/"):
        keys.extend(list_csv_keys(s3, R2_BUCKET_NAME, prefix))

    print(f"Found {len(keys)} CSV file(s)\n")

    skipped = 0
    compressed = 0
    total_original = 0
    total_compressed = 0
    failed = 0

    for key in keys:
        try:
            head = s3.head_object(Bucket=R2_BUCKET_NAME, Key=key)
            if head.get("ContentEncoding") == "gzip":
                skipped += 1
                continue

            original_size = head["ContentLength"]
            resp = s3.get_object(Bucket=R2_BUCKET_NAME, Key=key)
            raw = resp["Body"].read()
            gz = gzip.compress(raw)

            total_original += original_size
            total_compressed += len(gz)
            savings = (1 - len(gz) / original_size) * 100 if original_size else 0

            if dry_run:
                print(f"  [DRY] {key}: {original_size:,} -> {len(gz):,} ({savings:.0f}% savings)")
            else:
                s3.put_object(
                    Bucket=R2_BUCKET_NAME,
                    Key=key,
                    Body=gz,
                    ContentType="text/csv",
                    ContentEncoding="gzip",
                )
                print(f"  {key}: {original_size:,} -> {len(gz):,} ({savings:.0f}% savings)")

            compressed += 1

        except Exception as e:
            print(f"  FAILED {key}: {e}")
            failed += 1

    print(f"\nDone{' (DRY RUN)' if dry_run else ''}:")
    print(f"  compressed={compressed}  skipped={skipped}  failed={failed}")
    if total_original > 0:
        total_savings = (1 - total_compressed / total_original) * 100
        print(f"  total: {total_original:,} -> {total_compressed:,} bytes ({total_savings:.0f}% savings)")
    if dry_run and compressed > 0:
        print("Run with --apply to actually compress.")


if __name__ == "__main__":
    main()
