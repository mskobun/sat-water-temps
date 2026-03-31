import gzip
import os

import boto3

# Module-level cache (persists across warm invocations)
_s3_client = None


def get_s3_client():
    """Create and cache R2 S3 client. Persists across warm Lambda invocations."""
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=os.environ.get("R2_ENDPOINT"),
            aws_access_key_id=os.environ.get("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
        )
    return _s3_client


def upload_to_r2(s3_client, bucket_name, key, file_path, content_type=None):
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    with open(file_path, "rb") as f:
        s3_client.upload_fileobj(f, bucket_name, key, ExtraArgs=extra_args)
    print(f"Uploaded {file_path} to {key}")


def upload_csv_to_r2(s3_client, bucket_name, key, csv_file_path):
    """Upload CSV to R2 with gzip compression.

    Stored with ContentEncoding: gzip so R2 transparently decompresses on
    read -- the worker receives plain CSV without needing to decompress.
    """
    with open(csv_file_path, "rb") as f:
        compressed = gzip.compress(f.read())
    s3_client.put_object(
        Bucket=bucket_name, Key=key, Body=compressed,
        ContentType="text/csv",
        ContentEncoding="gzip",
    )
    print(f"Uploaded {csv_file_path} to {key} (gzip, {len(compressed):,} bytes)")
