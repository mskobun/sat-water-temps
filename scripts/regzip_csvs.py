#!/usr/bin/env python3
"""One-off script: ensure all .csv.gz files in R2 use ContentEncoding: gzip.

R2 transparently decompresses objects stored with ContentEncoding: gzip,
so the worker receives plain CSV without needing to decompress itself.
Files stored as application/gzip (no ContentEncoding) force the worker to
decompress, which causes timeouts.

This script checks each .csv.gz file's metadata and re-uploads any that
are missing ContentEncoding: gzip. It handles three cases:
  1. Raw gzip blob (ContentType: application/gzip, no ContentEncoding)
  2. Plain CSV (R2 already decompressed a ContentEncoding:gzip upload)
  3. Already correct (ContentEncoding: gzip) — skipped

Usage:
    uv run python scripts/regzip_csvs.py                # dry run
    uv run python scripts/regzip_csvs.py --apply        # actually re-upload
    uv run python scripts/regzip_csvs.py --prefix ECO   # only ECO/
"""

import argparse
import gzip
import os
import sys

import boto3
from botocore.config import Config
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _get_s3_client():
    """R2 client with checksum validation disabled.

    Some objects have stale checksums due to R2 transparently decompressing
    ContentEncoding:gzip uploads, so the stored checksum (computed on the
    compressed bytes) doesn't match the served (decompressed) bytes.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("R2_ENDPOINT"),
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def list_csv_gz_keys(s3, bucket, prefix=""):
    keys = []
    kwargs = {"Bucket": bucket, "Prefix": prefix}
    while True:
        resp = s3.list_objects_v2(**kwargs)
        for obj in resp.get("Contents", []):
            if obj["Key"].endswith(".csv.gz"):
                keys.append(obj["Key"])
        if not resp.get("IsTruncated"):
            break
        kwargs["ContinuationToken"] = resp["NextContinuationToken"]
    return keys


def main():
    parser = argparse.ArgumentParser(
        description="Ensure .csv.gz files in R2 use ContentEncoding: gzip"
    )
    parser.add_argument("--apply", action="store_true", help="Actually re-upload (default: dry run)")
    parser.add_argument("--prefix", default="", help="R2 key prefix to filter (e.g. 'LANDSAT' or 'ECO')")
    args = parser.parse_args()

    s3 = _get_s3_client()
    bucket = os.environ.get("R2_BUCKET_NAME", "multitifs")

    keys = list_csv_gz_keys(s3, bucket, args.prefix)
    print(f"Found {len(keys)} .csv.gz files under prefix='{args.prefix or '(all)'}'")

    fixed = 0
    already_ok = 0
    errors = 0

    for key in keys:
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            content_encoding = (head.get("ContentEncoding") or "").lower()

            if content_encoding == "gzip":
                already_ok += 1
                continue

            # Need to fix: download, ensure gzipped, re-upload with ContentEncoding
            resp = s3.get_object(Bucket=bucket, Key=key)
            data = resp["Body"].read()

            # Data might be raw gzip blob or plain CSV (if R2 already decompressed)
            if data[:2] == b"\x1f\x8b":
                # Already gzip bytes — re-upload as-is with correct metadata
                compressed = data
            else:
                # Plain CSV — compress it
                compressed = gzip.compress(data)

            if args.apply:
                s3.put_object(
                    Bucket=bucket, Key=key, Body=compressed,
                    ContentType="text/csv",
                    ContentEncoding="gzip",
                )
                print(f"  Fixed {key} (CE={content_encoding or 'none'}, {len(data):,} -> {len(compressed):,} bytes)")
            else:
                print(f"  [dry run] {key} (CE={content_encoding or 'none'}, {len(data):,} -> {len(compressed):,} bytes)")
            fixed += 1
        except Exception as e:
            print(f"  ERROR {key}: {e}")
            errors += 1

    print(f"\nDone: {fixed} to fix, {already_ok} already correct, {errors} errors")
    if not args.apply and fixed > 0:
        print("Run with --apply to actually re-upload")


if __name__ == "__main__":
    main()
