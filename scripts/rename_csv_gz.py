"""Rename .csv keys to .csv.gz in R2 and update csv_path in prod D1.

The backfill_gzip_csv.py script already compressed the content in place
under .csv keys. This script renames them to .csv.gz so the extension
matches the content, and updates D1 csv_path accordingly.

Usage:
    uv run python scripts/rename_csv_gz.py          # dry run
    uv run python scripts/rename_csv_gz.py --apply   # rename + update D1
"""

import argparse
import os
import sys

import boto3
import requests
from dotenv import load_dotenv

load_dotenv()

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


def d1_execute(sql, params=None):
    """Execute a SQL statement against prod D1 via the Cloudflare API."""
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/d1/database/{D1_DATABASE_ID}/query"
    body = {"sql": sql}
    if params:
        body["params"] = params
    resp = requests.post(
        url, json=body,
        headers={"Authorization": f"Bearer {CF_API_TOKEN}"},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"D1 query failed: {data.get('errors')}")
    return data


def list_gzipped_csv_keys(s3, bucket, prefix):
    """Yield .csv keys that have gzipped content (from the backfill)."""
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".csv") and not key.endswith(".csv.gz"):
                yield key


def main():
    parser = argparse.ArgumentParser(description="Rename .csv to .csv.gz in R2 + update D1")
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
        keys.extend(list_gzipped_csv_keys(s3, R2_BUCKET_NAME, prefix))

    print(f"Found {len(keys)} gzipped .csv key(s) to rename\n")

    renamed = 0
    failed = 0

    for old_key in keys:
        new_key = old_key + ".gz"
        try:
            if dry_run:
                print(f"  [DRY] {old_key} -> {new_key}")
            else:
                # Copy to new key (preserves content + metadata)
                s3.copy_object(
                    Bucket=R2_BUCKET_NAME,
                    CopySource=f"{R2_BUCKET_NAME}/{old_key}",
                    Key=new_key,
                    ContentType="text/csv",
                    ContentEncoding="gzip",
                    MetadataDirective="REPLACE",
                )
                # Delete old key
                s3.delete_object(Bucket=R2_BUCKET_NAME, Key=old_key)
                # Update D1
                d1_execute(
                    "UPDATE temperature_metadata SET csv_path = ? WHERE csv_path = ?",
                    [new_key, old_key],
                )
                print(f"  {old_key} -> {new_key}")

            renamed += 1

        except Exception as e:
            print(f"  FAILED {old_key}: {e}")
            failed += 1

    print(f"\nDone{' (DRY RUN)' if dry_run else ''}:  renamed={renamed}  failed={failed}")
    if dry_run and renamed > 0:
        print("Run with --apply to actually rename.")


if __name__ == "__main__":
    main()
