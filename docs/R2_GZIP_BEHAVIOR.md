# R2 Transparent Gzip Decompression

This repo stores some CSV assets in R2 as gzipped objects. Cloudflare R2 has behavior here that matters for both Workers and Lambda tooling.

## What R2 does

If an object is uploaded with `ContentEncoding: gzip`, R2 transparently decompresses it on read.

That means:

- clients receive plain bytes, not gzip bytes
- the `ContentEncoding` header is stripped from the response
- this behavior is driven by `ContentEncoding: gzip`, not by `ContentType`

## Behavior summary

| Upload metadata | GET response body | Transparent decompression |
|---|---|---|
| `ContentType: application/gzip` | gzip bytes | No |
| `ContentType: text/csv` | raw uploaded bytes | No |
| `ContentType: text/csv`, `ContentEncoding: gzip` | plain CSV text | Yes |
| `ContentType: application/gzip`, `ContentEncoding: gzip` | plain bytes | Yes |

Rule of thumb:

- `ContentEncoding: gzip` means R2 serves decompressed content
- otherwise R2 serves the uploaded bytes as-is

## Checksum mismatch caveat

R2 appears to keep checksums for the compressed upload, even when it later serves decompressed bytes. Some S3 clients can fail validation because the body they receive does not match the stored checksum metadata.

For boto3/botocore clients, the current workaround is to relax checksum validation:

```python
from botocore.config import Config

s3 = boto3.client(
    "s3",
    ...,
    config=Config(
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    ),
)
```

## Local dev difference

Miniflare/Wrangler local R2 emulation does not fully mirror this behavior. In local development you may still receive raw gzip bytes even when production R2 would transparently decompress them.

Code that reads R2 text should therefore tolerate both cases:

- already decompressed text
- raw gzip bytes that still need local decompression

## Current repo usage

The data pipeline uploads gzipped CSVs to R2 with `ContentEncoding: gzip` so production reads can stay simple and efficient.

Older assets may still need metadata fixes or re-uploading. The repo keeps backfill utilities under `lambda_functions/backfill/` for maintenance tasks like regzipping and metadata normalization.

Example:

```bash
cd lambda_functions
uv run python -m backfill regzip
uv run python -m backfill regzip NamTheun2
uv run python -m backfill regzip --via-sqs
```
