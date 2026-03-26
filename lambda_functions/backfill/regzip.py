"""Backfill handler: re-upload .csv.gz files with ContentEncoding: gzip.

SQS message: {"type": "backfill:regzip", "feature_id": "NamTheun2"}

R2 transparently decompresses objects stored with ContentEncoding: gzip,
so the worker receives plain CSV without needing to decompress itself.
Files stored as application/gzip (no ContentEncoding) force the worker to
decompress, which causes timeouts.

This handler checks each .csv.gz file's metadata and re-uploads any that
are missing ContentEncoding: gzip.
"""

import gzip

from botocore.config import Config

from backfill.base import (
    get_bucket_name,
    list_csv_keys_for_feature,
)

# Need a separate client with checksum validation disabled — some objects
# have stale checksums from R2 transparently decompressing old
# ContentEncoding:gzip uploads.
import boto3
import os


def _get_s3_client():
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


def handle(body: dict):
    """Handle a backfill:regzip message for one feature."""
    feature_id = body["feature_id"]
    print(f"[backfill:regzip][{feature_id}] Starting regzip backfill")

    s3 = _get_s3_client()
    bucket = get_bucket_name()

    keys = list_csv_keys_for_feature(s3, bucket, feature_id)
    if not keys:
        print(f"[backfill:regzip][{feature_id}] No .csv.gz files found")
        return

    print(f"[backfill:regzip][{feature_id}] Found {len(keys)} .csv.gz file(s)")

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

            resp = s3.get_object(Bucket=bucket, Key=key)
            data = resp["Body"].read()

            # Data might be raw gzip blob or plain CSV (if R2 already decompressed)
            if data[:2] == b"\x1f\x8b":
                compressed = data
            else:
                compressed = gzip.compress(data)

            s3.put_object(
                Bucket=bucket, Key=key, Body=compressed,
                ContentType="text/csv",
                ContentEncoding="gzip",
            )
            print(f"[backfill:regzip][{feature_id}]   Fixed {key}")
            fixed += 1
        except Exception as e:
            print(f"[backfill:regzip][{feature_id}]   ERROR {key}: {e}")
            errors += 1

    print(
        f"[backfill:regzip][{feature_id}] Done: "
        f"{fixed} fixed, {already_ok} already ok, {errors} errors"
    )
