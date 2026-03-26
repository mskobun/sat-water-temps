# R2 Transparent Gzip Decompression

Cloudflare R2 has undocumented behavior around `ContentEncoding: gzip` that affects how gzipped objects are served. This was discovered through trial and error during our CSV compression migration.

## The behavior

When you upload a gzipped object to R2 with `ContentEncoding: gzip`, R2 **transparently decompresses** it on read. The client receives plain (decompressed) bytes and the `ContentEncoding` header is stripped from the response.

This happens regardless of `ContentType` — it is solely triggered by `ContentEncoding: gzip`.

## What works and what doesn't

| Upload metadata | R2 serves on GET | Decompressed? |
|---|---|---|
| `ContentType: application/gzip` | gzip bytes as-is | No |
| `ContentType: text/csv` | gzip bytes as-is | No |
| `ContentType: text/csv`, `ContentEncoding: gzip` | **plain text** | **Yes** |
| `ContentType: application/gzip`, `ContentEncoding: gzip` | **plain text** | **Yes** |
| `ContentType: application/octet-stream`, `ContentEncoding: gzip` | **plain text** | **Yes** |
| `ContentType: text/csv`, `ContentEncoding: identity` | gzip bytes as-is | No |

**Rule: `ContentEncoding: gzip` = R2 decompresses. Anything else = R2 serves raw bytes.**

## Checksum bug

R2 stores the checksum against the **compressed** bytes at upload time. But when it transparently decompresses on read, the served bytes no longer match that checksum. This causes boto3 (and possibly other S3 clients) to throw `FlexibleChecksumError`.

Workaround: disable checksum validation on the client:

```python
from botocore.config import Config

s3 = boto3.client("s3", ..., config=Config(
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
))
```

This is arguably an R2 bug — if R2 decompresses the body, it should recompute or strip the checksum.

## Miniflare (local dev)

Miniflare's R2 emulation does **not** do transparent decompression, even when `remote = true` in `wrangler.toml`. The R2 binding proxy serves the raw gzip bytes regardless of `ContentEncoding`. This means local dev and production behave differently.

Our `r2Text()` function in `src/lib/db.ts` handles both cases by checking for gzip magic bytes (`0x1f 0x8b`) and decompressing client-side as a fallback.

## Our approach

We store gzipped CSVs with:

```python
s3.put_object(
    Bucket=bucket, Key="path/to/file.csv.gz", Body=compressed,
    ContentType="text/csv",
    ContentEncoding="gzip",
)
```

This way R2 decompresses transparently on read, and the Cloudflare Worker receives plain CSV without spending CPU time on decompression. The `.csv.gz` extension is kept for clarity but the served content is plain text.

### Migration

Older files were uploaded with `ContentType: application/gzip` (no `ContentEncoding`), which forces workers to decompress manually. The backfill handler `backfill regzip` re-uploads these with the correct metadata:

```bash
cd lambda_functions
uv run python -m backfill regzip              # all features
uv run python -m backfill regzip NamTheun2    # one feature
uv run python -m backfill regzip --via-sqs    # fan out via SQS
```
