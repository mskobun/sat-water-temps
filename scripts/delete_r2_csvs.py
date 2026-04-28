"""Delete gzipped CSV files from R2.

Scans ECO/ and LANDSAT/ prefixes for .csv.gz files.
Default mode is dry run — shows what would be deleted and total size.

Usage:
    uv run --with python-dotenv,boto3 python scripts/delete_r2_csvs.py              # dry run
    uv run --with python-dotenv,boto3 python scripts/delete_r2_csvs.py --delete     # actually delete

Reads .env from project root. Requires:
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import boto3

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

R2_ENDPOINT = os.environ["R2_ENDPOINT"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")

PREFIXES = ["ECO/", "LANDSAT/"]


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def list_csv_keys(s3):
    """Yield (key, size_bytes) for all .csv.gz files under known prefixes."""
    for prefix in PREFIXES:
        kwargs = {"Bucket": R2_BUCKET_NAME, "Prefix": prefix}
        while True:
            resp = s3.list_objects_v2(**kwargs)
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".csv.gz") or key.endswith(".csv"):
                    yield key, obj["Size"]
            if not resp.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = resp["NextContinuationToken"]


def main():
    parser = argparse.ArgumentParser(description="Delete gzipped CSVs from R2")
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Actually delete files (default is dry run)",
    )
    args = parser.parse_args()

    s3 = get_s3()
    keys = list(list_csv_keys(s3))

    if not keys:
        print("No CSV files found in R2.")
        return

    total_bytes = sum(size for _, size in keys)
    total_gb = total_bytes / (1024**3)

    print(f"Found {len(keys)} CSV file(s) totalling {total_gb:.3f} GB ({total_bytes:,} bytes)\n")

    for key, size in keys:
        size_kb = size / 1024
        print(f"  {key}  ({size_kb:.1f} KB)")

    if not args.delete:
        print(f"\nDry run — pass --delete to remove these {len(keys)} files and free {total_gb:.3f} GB")
        return

    print(f"\nDeleting {len(keys)} files…")
    # R2 supports batch delete of up to 1000 keys at a time
    batch_size = 1000
    deleted = 0
    for i in range(0, len(keys), batch_size):
        batch = keys[i : i + batch_size]
        s3.delete_objects(
            Bucket=R2_BUCKET_NAME,
            Delete={"Objects": [{"Key": k} for k, _ in batch], "Quiet": True},
        )
        deleted += len(batch)
        print(f"  Deleted {deleted}/{len(keys)}")

    print(f"\nDone. Freed {total_gb:.3f} GB across {len(keys)} files.")


if __name__ == "__main__":
    main()
