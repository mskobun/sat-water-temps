#!/usr/bin/env python3
"""One-off cleanup: delete duplicate midnight Landsat records from D1 and R2.

Targets `temperature_metadata` rows where:
  - source = 'landsat'
  - date ends with `T00:00:00`
  - the same feature has another Landsat row on the same calendar day

These midnight rows came from the old date-only format after normalization and
should be removed only when a timestamped replacement exists for that day.

Usage:
    uv run python scripts/delete_legacy_landsat_date_only.py
    uv run python scripts/delete_legacy_landsat_date_only.py --apply

Requires env vars:
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
    CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, D1_DATABASE_ID
"""

import argparse
import os
import sys
from typing import Iterable

import boto3
import requests
from botocore.config import Config
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
        config=Config(
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
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


def get_results(result_json):
    return result_json.get("result", [{}])[0].get("results", [])


def chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def derive_png_keys(png_path: str | None) -> set[str]:
    if not png_path:
        return set()

    base = png_path
    for suffix in ("_relative.png", "_fixed.png", "_gray.png", ".png"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break

    return {
        f"{base}_relative.png",
        f"{base}_fixed.png",
        f"{base}_gray.png",
    }


def derive_metadata_key(row: dict) -> str | None:
    sample_path = row.get("tif_path") or row.get("csv_path") or row.get("png_path")
    if not sample_path:
        return None

    parent, filename = sample_path.rsplit("/", 1)
    stem = filename
    for suffix in (".csv.gz", ".csv", ".tif", "_relative.png", "_fixed.png", "_gray.png", ".png"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    return f"{parent}/metadata/{stem}_metadata.json"


def list_duplicate_midnight_rows():
    sql = """
    SELECT feature_id, date, csv_path, tif_path, png_path, parquet_path
    FROM temperature_metadata tm
    WHERE tm.source = 'landsat'
      AND tm.date LIKE '%T00:00:00'
      AND EXISTS (
            SELECT 1
            FROM temperature_metadata tm2
            WHERE tm2.feature_id = tm.feature_id
              AND tm2.source = 'landsat'
              AND substr(tm2.date, 1, 10) = substr(tm.date, 1, 10)
              AND tm2.date != tm.date
              AND tm2.date NOT LIKE '%T00:00:00'
        )
    ORDER BY feature_id, date
    """
    return get_results(query_d1(sql))


def collect_r2_keys(rows: list[dict]) -> list[str]:
    keys = set()
    for row in rows:
        for field in ("csv_path", "tif_path"):
            value = row.get(field)
            if value:
                keys.add(value)
        keys.update(derive_png_keys(row.get("png_path")))
        metadata_key = derive_metadata_key(row)
        if metadata_key:
            keys.add(metadata_key)
    return sorted(keys)


def delete_r2_keys(s3, keys: list[str]) -> tuple[int, int]:
    deleted = 0
    errors = 0

    for batch in chunks(keys, 1000):
        resp = s3.delete_objects(
            Bucket=R2_BUCKET_NAME,
            Delete={"Objects": [{"Key": key} for key in batch], "Quiet": True},
        )
        deleted += len(resp.get("Deleted", []))
        errors += len(resp.get("Errors", []))
        for err in resp.get("Errors", []):
            print(f"  R2 delete error {err.get('Key')}: {err.get('Message')}")

    return deleted, errors


def refresh_feature_latest_dates(feature_ids: list[str]):
    sql = """
    UPDATE features
    SET latest_date = (
            SELECT MAX(date)
            FROM temperature_metadata
            WHERE feature_id = features.id
        ),
        last_updated = unixepoch()
    WHERE id = ?
    """
    for feature_id in feature_ids:
        query_d1(sql, [feature_id])


def main():
    parser = argparse.ArgumentParser(
        description="Delete duplicate midnight Landsat rows from D1 and R2"
    )
    parser.add_argument("--apply", action="store_true", help="Actually delete data (default: dry run)")
    args = parser.parse_args()
    dry_run = not args.apply

    required_vars = (
        "R2_ENDPOINT",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "D1_DATABASE_ID",
    )
    for var in required_vars:
        if not os.environ.get(var):
            print(f"Error: {var} not set")
            sys.exit(1)

    rows = list_duplicate_midnight_rows()
    if not rows:
        print("No duplicate midnight Landsat rows found.")
        return

    keys = collect_r2_keys(rows)
    feature_ids = sorted({row["feature_id"] for row in rows})

    print(f"Found {len(rows)} duplicate midnight Landsat row(s) across {len(feature_ids)} feature(s)")
    print(f"Will delete up to {len(keys)} R2 object(s)")
    print("")

    preview_count = min(10, len(rows))
    print(f"Sample rows ({preview_count}):")
    for row in rows[:preview_count]:
        print(f"  {row['feature_id']}  {row['date']}")
    if len(rows) > preview_count:
        print(f"  ... {len(rows) - preview_count} more")

    if dry_run:
        key_preview_count = min(10, len(keys))
        if key_preview_count:
            print("")
            print(f"Sample R2 keys ({key_preview_count}):")
            for key in keys[:key_preview_count]:
                print(f"  {key}")
            if len(keys) > key_preview_count:
                print(f"  ... {len(keys) - key_preview_count} more")
        print("")
        print("Dry run only. Re-run with --apply to delete the R2 objects and D1 rows.")
        return

    s3 = get_s3_client()
    deleted_objects, r2_errors = delete_r2_keys(s3, keys)
    print(f"Deleted {deleted_objects} R2 object(s)")

    if r2_errors:
        print(f"Aborting D1 delete because {r2_errors} R2 deletion error(s) occurred.")
        sys.exit(1)

    delete_sql = """
    DELETE FROM temperature_metadata AS tm
    WHERE tm.source = 'landsat'
      AND tm.date LIKE '%T00:00:00'
      AND EXISTS (
            SELECT 1
            FROM temperature_metadata tm2
            WHERE tm2.feature_id = tm.feature_id
              AND tm2.source = 'landsat'
              AND substr(tm2.date, 1, 10) = substr(tm.date, 1, 10)
              AND tm2.date != tm.date
              AND tm2.date NOT LIKE '%T00:00:00'
        )
    """
    query_d1(delete_sql)
    refresh_feature_latest_dates(feature_ids)

    print(f"Deleted {len(rows)} D1 temperature_metadata row(s)")
    print(f"Refreshed latest_date for {len(feature_ids)} feature(s)")


if __name__ == "__main__":
    main()
