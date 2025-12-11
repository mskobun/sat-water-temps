#!/usr/bin/env python3
"""
Migrate metadata from R2 to D1 (Hybrid Architecture)

This script migrates ONLY metadata to D1, not temperature point data.
Temperature CSVs remain in R2 for efficient storage.

This script:
1. Lists all features from R2
2. For each feature, reads metadata JSONs
3. Inserts metadata and file paths into D1

Usage:
    python migrate_csv_to_d1.py [--feature FEATURE_ID] [--dry-run]
"""

import os
import json
import re
import argparse
import boto3
from datetime import datetime
from dotenv import load_dotenv
import requests
from typing import List, Dict, Optional

load_dotenv()

# Configuration
R2_BUCKET = "multitifs"
BUCKET_PREFIX = "ECO"
D1_DATABASE_ID = os.environ.get("D1_DATABASE_ID")
CLOUDFLARE_ACCOUNT_ID = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
CLOUDFLARE_API_TOKEN = os.environ.get("CLOUDFLARE_API_TOKEN")


def get_r2_client():
    """Initialize R2 client via S3-compatible API"""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("R2_ENDPOINT"),
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


def query_d1(sql: str, params: List = None) -> Dict:
    """Execute SQL query against D1 database"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{D1_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"sql": sql}
    if params:
        payload["params"] = params

    response = requests.post(url, headers=headers, json=payload)

    if not response.ok:
        try:
            error_data = response.json()
            print(f"    D1 API Error: {error_data}")
        except:
            print(f"    D1 Error Response: {response.text}")
        response.raise_for_status()

    return response.json()


def list_features(s3_client) -> List[str]:
    """List all feature IDs from R2"""
    features = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=R2_BUCKET, Prefix=f"{BUCKET_PREFIX}/", Delimiter="/"
    ):
        for prefix in page.get("CommonPrefixes", []):
            feature_id = prefix["Prefix"].replace(f"{BUCKET_PREFIX}/", "").rstrip("/")
            if feature_id:
                features.append(feature_id)

    return features


def list_csvs_for_feature(s3_client, feature_id: str) -> List[str]:
    """List all CSV files for a feature"""
    prefix = f"{BUCKET_PREFIX}/{feature_id}/lake/"
    csvs = []

    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("_filter.csv") and "/metadata/" not in key:
                csvs.append(key)

    return csvs


def extract_date_from_filename(filename: str) -> Optional[str]:
    """Extract date from filename like name_location_DATE_filter.csv"""
    match = re.search(r"_(\d{13})_filter\.csv", filename)
    return match.group(1) if match else None


def count_csv_rows(s3_client, csv_key: str) -> int:
    """Count rows in CSV without loading all data"""
    try:
        obj = s3_client.get_object(Bucket=R2_BUCKET, Key=csv_key)
        content = obj["Body"].read().decode("utf-8")
        lines = content.strip().split("\n")
        # -1 for header row
        return len(lines) - 1 if len(lines) > 1 else 0
    except Exception as e:
        print(f"    Warning: Could not count CSV rows: {e}")
        return 0


def get_metadata_from_r2(s3_client, feature_id: str, date: str) -> Optional[Dict]:
    """Get metadata JSON for a specific date"""
    name, location = (
        feature_id.split("/") if "/" in feature_id else (feature_id, "lake")
    )
    metadata_key = f"{BUCKET_PREFIX}/{feature_id}/lake/metadata/{name}_{location}_{date}_filter_metadata.json"

    try:
        obj = s3_client.get_object(Bucket=R2_BUCKET, Key=metadata_key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3_client.exceptions.NoSuchKey:
        print(f"  Warning: Metadata not found for {date}")
        return None


def insert_feature(feature_id: str, latest_date: str, dry_run: bool = False):
    """Insert or update feature record"""
    name, location = (
        feature_id.split("/") if "/" in feature_id else (feature_id, "lake")
    )

    sql = """
    INSERT INTO features (id, name, location, latest_date, last_updated)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        latest_date = excluded.latest_date,
        last_updated = excluded.last_updated
    """
    params = [feature_id, name, location, latest_date, int(datetime.now().timestamp())]

    if dry_run:
        print(f"  [DRY RUN] Insert feature: {feature_id}")
        return

    query_d1(sql, params)


def insert_metadata(
    feature_id: str, date: str, metadata: Dict, data_points: int, dry_run: bool = False
):
    """Insert temperature metadata with R2 file paths"""
    if dry_run:
        print(f"  [DRY RUN] Insert metadata for {date}")
        return

    # Construct R2 paths (these files already exist in R2)
    csv_path = f"{feature_id}/csv/{date}.csv"
    tif_path = f"{feature_id}/tif/{date}.tif"
    png_path = f"{feature_id}/png/{date}.png"

    sql = """
    INSERT OR REPLACE INTO temperature_metadata 
    (feature_id, date, min_temp, max_temp, mean_temp, median_temp, std_dev,
     data_points, water_pixel_count, land_pixel_count, wtoff, 
     csv_path, tif_path, png_path)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = [
        feature_id,
        date,
        metadata.get("min_temp"),
        metadata.get("max_temp"),
        metadata.get("mean_temp"),
        metadata.get("median_temp"),
        metadata.get("std_dev"),
        data_points or metadata.get("data_points", 0),
        metadata.get("water_pixel_count", 0),
        metadata.get("land_pixel_count", 0),
        1 if metadata.get("wtoff", False) else 0,
        csv_path,
        tif_path,
        png_path,
    ]

    query_d1(sql, params)


def migrate_feature(s3_client, feature_id: str, dry_run: bool = False):
    """Migrate all data for a single feature"""
    print(f"\n{'=' * 60}")
    print(f"Migrating feature: {feature_id}")
    print(f"{'=' * 60}")

    csvs = list_csvs_for_feature(s3_client, feature_id)
    print(f"  Found {len(csvs)} CSV files")

    if not csvs:
        print("  No data to migrate")
        return

    dates = []
    latest_date = None

    # First pass: collect dates and find latest
    for csv_key in csvs:
        date = extract_date_from_filename(csv_key)
        if not date:
            print(f"  Warning: Could not extract date from {csv_key}")
            continue

        dates.append(date)
        if not latest_date or date > latest_date:
            latest_date = date

    # Insert feature record FIRST (required for foreign key constraint)
    if latest_date:
        insert_feature(feature_id, latest_date, dry_run)

    # Second pass: insert metadata only (CSV data stays in R2)
    for csv_key in csvs:
        date = extract_date_from_filename(csv_key)
        if not date:
            continue

        print(f"  Processing {date}...")

        # Count CSV rows (don't load full data)
        data_points = count_csv_rows(s3_client, csv_key)
        print(f"    CSV: {data_points} temperature points (staying in R2)")

        # Get metadata JSON
        metadata = get_metadata_from_r2(s3_client, feature_id, date)

        # Insert metadata with file paths
        if metadata or data_points > 0:
            insert_metadata(feature_id, date, metadata or {}, data_points, dry_run)

    print(f"  ✓ Migrated metadata for {len(dates)} dates")


def main():
    parser = argparse.ArgumentParser(description="Migrate CSV data from R2 to D1")
    parser.add_argument("--feature", help="Migrate specific feature only")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    args = parser.parse_args()

    # Validate environment
    required_vars = [
        "D1_DATABASE_ID",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_API_TOKEN",
        "R2_ENDPOINT",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
    ]
    missing = [var for var in required_vars if not os.environ.get(var)]
    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        return 1

    s3_client = get_r2_client()

    if args.feature:
        features = [args.feature]
    else:
        print("Discovering features from R2...")
        features = list_features(s3_client)
        print(f"Found {len(features)} features")

    if args.dry_run:
        print("\n*** DRY RUN MODE - No changes will be made ***\n")
    else:
        response = input(f"Migrate {len(features)} features? (y/n): ")
        if response.lower() != "y":
            print("Aborted")
            return 0

    success_count = 0
    fail_count = 0

    for feature_id in features:
        try:
            migrate_feature(s3_client, feature_id, args.dry_run)
            success_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            fail_count += 1

    print("\n" + "=" * 60)
    print("Migration complete!")
    print(f"  ✓ Success: {success_count} features")
    if fail_count > 0:
        print(f"  ✗ Failed: {fail_count} features")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
