"""Shared utilities for backfill handlers."""

import json
import os

import boto3
from botocore.config import Config

from d1 import query_d1


def get_s3_client():
    """Create an R2 S3 client (does not use the cached processor one)."""
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("R2_ENDPOINT"),
        aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
        config=Config(request_checksum_calculation="when_required", response_checksum_validation="when_required"),
    )


def get_bucket_name():
    return os.environ.get("R2_BUCKET_NAME", "multitifs")


def get_sqs_client():
    return boto3.client("sqs", region_name=os.environ.get("AWS_REGION", "us-west-2"))


def get_queue_url():
    return os.environ.get("SQS_QUEUE_URL")


def send_sqs_message(body: dict):
    """Send a single SQS message."""
    sqs = get_sqs_client()
    queue_url = get_queue_url()
    if not queue_url:
        raise RuntimeError("SQS_QUEUE_URL not set")
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))


def list_features():
    """Return all feature IDs from D1."""
    result = query_d1("SELECT DISTINCT id FROM features ORDER BY id", [], fatal=True)
    try:
        rows = result["result"][0]["results"]
        return [row["id"] for row in rows]
    except (KeyError, IndexError):
        return []


def list_csv_keys_for_feature(s3_client, bucket_name, feature_id):
    """List all CSV.gz keys in R2 for a given feature."""
    # feature_id is like "NamTheun2" or "NamTheun2/lake"
    if "/" in feature_id:
        name, location = feature_id.split("/", 1)
    else:
        name, location = feature_id, "lake"

    keys = []
    for prefix_root in ["ECO", "LANDSAT"]:
        prefix = f"{prefix_root}/{name}/{location}/"
        paginator_kwargs = {"Bucket": bucket_name, "Prefix": prefix}
        try:
            resp = s3_client.list_objects_v2(**paginator_kwargs)
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if key.endswith(".csv.gz"):
                    keys.append(key)
            # Handle pagination
            while resp.get("IsTruncated"):
                resp = s3_client.list_objects_v2(
                    **paginator_kwargs,
                    ContinuationToken=resp["NextContinuationToken"],
                )
                for obj in resp.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith(".csv.gz"):
                        keys.append(key)
        except Exception:
            pass
    return keys


def get_csv_date_mapping(feature_id):
    """Return {csv_path: date} for all rows of a feature from D1."""
    result = query_d1(
        "SELECT csv_path, date FROM temperature_metadata WHERE feature_id = ?",
        [feature_id],
        fatal=True,
    )
    try:
        rows = result["result"][0]["results"]
        return {row["csv_path"]: row["date"] for row in rows if row["csv_path"]}
    except (KeyError, IndexError):
        return {}


def update_parquet_path_in_d1(feature_id, date, parquet_path):
    """Set parquet_path on an existing temperature_metadata row."""
    query_d1(
        "UPDATE temperature_metadata SET parquet_path = ? WHERE feature_id = ? AND date = ?",
        [parquet_path, feature_id, date],
        fatal=False,
    )
