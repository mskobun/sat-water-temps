import gzip
import os

import boto3
from botocore.exceptions import ClientError

# Module-level cache (persists across warm Lambda invocations)
_s3_client = None


class Boto3R2Backend:
    """R2 via boto3 S3-compatible API (production / remote bucket)."""

    def __init__(self, client):
        self._client = client

    def upload_file_from_path(
        self, bucket: str, key: str, path: str, content_type=None
    ) -> None:
        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type
        with open(path, "rb") as f:
            self._client.upload_fileobj(f, bucket, key, ExtraArgs=extra_args or None)

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type=None,
        content_encoding=None,
    ) -> None:
        kw = {"Bucket": bucket, "Key": key, "Body": body}
        if content_type:
            kw["ContentType"] = content_type
        if content_encoding:
            kw["ContentEncoding"] = content_encoding
        self._client.put_object(**kw)

    def get_object_bytes(self, bucket: str, key: str) -> bytes:
        try:
            return self._client.get_object(Bucket=bucket, Key=key)["Body"].read()
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise FileNotFoundError(key) from e
            raise


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


def get_r2_backend():
    """Object storage for processors: cloud (boto3) or local (Wrangler R2 --local)."""
    if os.environ.get("PROCESSOR_RUNTIME", "cloud").lower() == "local":
        from common.local_wrangler import WranglerLocalR2Backend

        return WranglerLocalR2Backend()
    return Boto3R2Backend(get_s3_client())


def upload_to_r2(storage, bucket_name, key, file_path, content_type=None):
    storage.upload_file_from_path(bucket_name, key, file_path, content_type)
    print(f"Uploaded {file_path} to {key}")


def upload_csv_to_r2(storage, bucket_name, key, csv_file_path):
    """Upload CSV to R2 with gzip compression.

    Stored with ContentEncoding: gzip so R2 transparently decompresses on
    read -- the worker receives plain CSV without needing to decompress.
    """
    with open(csv_file_path, "rb") as f:
        compressed = gzip.compress(f.read())
    storage.put_object(
        bucket_name,
        key,
        compressed,
        content_type="text/csv",
        content_encoding="gzip",
    )
    print(f"Uploaded {csv_file_path} to {key} (gzip, {len(compressed):,} bytes)")
