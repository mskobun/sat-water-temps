"""Backfill handler: generate Parquet files from existing CSV.gz files in R2.

SQS message: {"type": "backfill:parquet", "feature_id": "NamTheun2"}

For each feature, looks up csv_path→date from D1, downloads the CSVs,
extracts longitude/latitude/temperature columns, and writes a single
Parquet file with one row group per date (using the full D1 timestamp).
"""

import io

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from backfill.base import (
    get_s3_client,
    get_bucket_name,
    get_csv_date_mapping,
    update_parquet_path_in_d1,
)


def handle(body: dict):
    """Handle a backfill:parquet message for one feature."""
    feature_id = body["feature_id"]
    if "/" in feature_id:
        name, location = feature_id.split("/", 1)
    else:
        name, location = feature_id, "lake"

    print(f"[backfill:parquet][{feature_id}] Starting Parquet backfill")

    s3 = get_s3_client()
    bucket = get_bucket_name()

    # Get authoritative csv_path→date mapping from D1
    csv_date_map = get_csv_date_mapping(feature_id)
    if not csv_date_map:
        print(f"[backfill:parquet][{feature_id}] No CSV records in D1, skipping")
        return

    print(f"[backfill:parquet][{feature_id}] Found {len(csv_date_map)} CSV record(s) in D1")

    schema = pa.schema([
        ("longitude", pa.float32()),
        ("latitude", pa.float32()),
        ("temperature", pa.float32()),
        ("date", pa.string()),
    ])

    # Build one Parquet file per source prefix (ECO vs LANDSAT)
    keys_by_prefix: dict[str, list[tuple[str, str]]] = {}
    for csv_path, date in csv_date_map.items():
        prefix = "LANDSAT" if csv_path.startswith("LANDSAT/") else "ECO"
        keys_by_prefix.setdefault(prefix, []).append((csv_path, date))

    for prefix, entries in keys_by_prefix.items():
        parquet_key = f"{prefix}/{name}/{location}/{name}_{location}.parquet"
        buf = io.BytesIO()
        writer = pq.ParquetWriter(buf, schema, compression="zstd")
        dates_written = []

        for csv_path, date in sorted(entries, key=lambda e: e[1]):
            try:
                resp = s3.get_object(Bucket=bucket, Key=csv_path)
                csv_text = resp["Body"].read().decode("utf-8")
                df = pd.read_csv(io.StringIO(csv_text))

                # Find the right columns
                lng_col = next((c for c in df.columns if c in ("longitude", "x")), None)
                lat_col = next((c for c in df.columns if c in ("latitude", "y")), None)
                temp_col = next(
                    (c for c in df.columns if c in ("LST_filter", "temperature")), None
                )

                if not all([lng_col, lat_col, temp_col]):
                    print(f"[backfill:parquet][{feature_id}] Skipping {csv_path}: missing columns")
                    continue

                df_clean = df[[lng_col, lat_col, temp_col]].dropna()
                if df_clean.empty:
                    print(f"[backfill:parquet][{feature_id}] Skipping {csv_path}: no valid rows")
                    continue

                table = pa.table({
                    "longitude": pa.array(df_clean[lng_col].values, type=pa.float32()),
                    "latitude": pa.array(df_clean[lat_col].values, type=pa.float32()),
                    "temperature": pa.array(df_clean[temp_col].values, type=pa.float32()),
                    "date": pa.array([date] * len(df_clean), type=pa.string()),
                }, schema=schema)

                writer.write_table(table)
                dates_written.append(date)
            except Exception as e:
                print(f"[backfill:parquet][{feature_id}] Error processing {csv_path}: {e}")
                continue

        writer.close()

        if not dates_written:
            print(f"[backfill:parquet][{feature_id}] No valid dates for {prefix}, skipping")
            continue

        buf.seek(0)
        s3.put_object(
            Bucket=bucket, Key=parquet_key, Body=buf.getvalue(),
            ContentType="application/octet-stream",
        )
        print(
            f"[backfill:parquet][{feature_id}] Uploaded {parquet_key} "
            f"({len(dates_written)} row groups, {len(buf.getvalue()):,} bytes)"
        )

        # Update D1 parquet_path for each date
        for date in dates_written:
            update_parquet_path_in_d1(feature_id, date, parquet_key)

        print(f"[backfill:parquet][{feature_id}] Updated {len(dates_written)} D1 records")
