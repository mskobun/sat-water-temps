"""Generate a Parquet file for a feature by downloading all CSVs from R2.

Creates one row group per date with columns: longitude, latitude, LST_filter, date.

Usage:
    uv run --with pyarrow python scripts/generate_parquet.py NamTheun2

Requires env vars:
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
"""

import gzip
import io
import os
import sys

import boto3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

R2_ENDPOINT = os.environ["R2_ENDPOINT"]
R2_ACCESS_KEY_ID = os.environ["R2_ACCESS_KEY_ID"]
R2_SECRET_ACCESS_KEY = os.environ["R2_SECRET_ACCESS_KEY"]
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")

KEEP_COLS = ["longitude", "latitude", "LST_filter"]


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def list_csvs(s3, feature: str) -> list[str]:
    """List all .csv.gz keys for a feature's lake location."""
    prefix = f"ECO/{feature}/lake/"
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".csv.gz"):
                keys.append(obj["Key"])
    return sorted(keys)


def download_csv(s3, key: str) -> pd.DataFrame:
    """Download a .csv.gz from R2 and parse into a DataFrame."""
    from botocore.config import Config
    resp = s3.get_object(Bucket=R2_BUCKET_NAME, Key=key)
    try:
        raw = resp["Body"].read()
    except Exception as e:
        print(f"    Warning: error reading {key}: {e}")
        return pd.DataFrame()
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except gzip.BadGzipFile:
        text = raw.decode("utf-8")
    df = pd.read_csv(io.StringIO(text))

    # Keep only the columns we need
    available = [c for c in KEEP_COLS if c in df.columns]
    if not available:
        return pd.DataFrame()
    df = df[available].dropna()

    # Extract date from filename: {feature}_lake_{timestamp}_filter...
    filename = key.split("/")[-1]
    # e.g. NamTheun2_lake_2026030024658_filter_wtoff.csv.gz
    parts = filename.split("_")
    # timestamp is the 3rd part (index 2)
    date_str = parts[2] if len(parts) > 2 else "unknown"
    df["date"] = date_str

    return df


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_parquet.py <feature_name>")
        sys.exit(1)

    feature = sys.argv[1]
    output_path = f"output/{feature}.parquet"
    os.makedirs("output", exist_ok=True)

    s3 = get_s3()
    keys = list_csvs(s3, feature)
    print(f"Found {len(keys)} CSVs for {feature}")

    if not keys:
        print("No CSVs found.")
        sys.exit(1)

    schema = pa.schema([
        ("longitude", pa.float32()),
        ("latitude", pa.float32()),
        ("LST_filter", pa.float32()),
        ("date", pa.string()),
    ])

    writer = pq.ParquetWriter(
        output_path,
        schema,
        compression="zstd",
    )

    total_rows = 0
    for i, key in enumerate(keys):
        df = download_csv(s3, key)
        if df.empty:
            print(f"  [{i+1}/{len(keys)}] {key} — empty, skipping")
            continue

        table = pa.Table.from_pandas(df, schema=schema, preserve_index=False)
        writer.write_table(table)  # Each write = one row group
        total_rows += len(df)
        print(f"  [{i+1}/{len(keys)}] {key} — {len(df):,} rows")

    writer.close()

    file_size = os.path.getsize(output_path)
    print(f"\nDone: {output_path}")
    print(f"  Total rows: {total_rows:,}")
    print(f"  Row groups: {len(keys)} (one per date)")
    print(f"  File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")

    # Also show what the individual CSVs total to for comparison
    print(f"\n  Compare: sum of .csv.gz files on R2:")
    total_gz = 0
    for key in keys:
        head = s3.head_object(Bucket=R2_BUCKET_NAME, Key=key)
        total_gz += head["ContentLength"]
    print(f"  Total .csv.gz size: {total_gz:,} bytes ({total_gz / 1024:.1f} KB)")
    print(f"  Parquet / CSV.gz ratio: {file_size / total_gz:.2f}x")


if __name__ == "__main__":
    main()
