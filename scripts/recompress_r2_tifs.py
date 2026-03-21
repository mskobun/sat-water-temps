"""One-time migration: recompress existing R2 TIFs.

- Landsat TIFs: reduce from 5 bands to 1 band + DEFLATE compression
- ECOSTRESS TIFs: add DEFLATE compression (keep all bands)

Usage:
    # Dry run (default) — shows what would be changed
    uv run python scripts/recompress_r2_tifs.py

    # Actually recompress and re-upload
    uv run python scripts/recompress_r2_tifs.py --apply

Requires R2 credentials in environment:
    R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
"""

import argparse
import io
import os
import sys
import tempfile

import boto3
import numpy as np
import rasterio

R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def list_tifs(s3, prefix):
    """List all .tif keys under a prefix."""
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".tif"):
                keys.append((obj["Key"], obj["Size"]))
    return keys


def recompress_tif(s3, key, is_landsat, dry_run):
    """Download, recompress, and re-upload a single TIF."""
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_in:
        tmp_in_path = tmp_in.name
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp_out:
        tmp_out_path = tmp_out.name

    try:
        s3.download_file(R2_BUCKET_NAME, key, tmp_in_path)
        original_size = os.path.getsize(tmp_in_path)

        with rasterio.open(tmp_in_path) as src:
            meta = src.meta.copy()
            already_compressed = meta.get("compress") in ("deflate", "lzw", "zstd")

            if is_landsat:
                # Read only band 1, write single-band with DEFLATE
                band1 = src.read(1)
                old_bands = src.count

                if old_bands == 1 and already_compressed:
                    return None  # Already migrated

                meta.update(count=1, compress="deflate")
                with rasterio.open(tmp_out_path, "w", **meta) as dst:
                    dst.write(band1, 1)
            else:
                # ECOSTRESS: keep all bands, add DEFLATE
                if already_compressed:
                    return None  # Already compressed

                meta.update(compress="deflate")
                with rasterio.open(tmp_out_path, "w", **meta) as dst:
                    for i in range(1, src.count + 1):
                        dst.write(src.read(i), i)

        new_size = os.path.getsize(tmp_out_path)
        reduction = (1 - new_size / original_size) * 100 if original_size > 0 else 0

        if dry_run:
            label = "1-band+DEFLATE" if is_landsat else "DEFLATE"
            print(f"  [DRY RUN] {key}: {original_size:,} -> {new_size:,} bytes ({reduction:.0f}% reduction) [{label}]")
        else:
            s3.upload_file(tmp_out_path, R2_BUCKET_NAME, key, ExtraArgs={"ContentType": "image/tiff"})
            print(f"  {key}: {original_size:,} -> {new_size:,} bytes ({reduction:.0f}% reduction)")

        return original_size - new_size

    finally:
        for p in (tmp_in_path, tmp_out_path):
            if os.path.exists(p):
                os.unlink(p)


def main():
    parser = argparse.ArgumentParser(description="Recompress R2 TIFs")
    parser.add_argument("--apply", action="store_true", help="Actually recompress (default is dry run)")
    args = parser.parse_args()

    dry_run = not args.apply

    if not R2_ENDPOINT:
        print("Error: R2_ENDPOINT not set. Export R2 credentials first.")
        sys.exit(1)

    s3 = get_s3_client()
    total_saved = 0
    total_processed = 0
    total_skipped = 0

    for prefix, is_landsat in [("LANDSAT/", True), ("ECO/", False)]:
        label = "Landsat" if is_landsat else "ECOSTRESS"
        print(f"\n{'='*60}")
        print(f"Processing {label} TIFs (prefix={prefix})")
        print(f"{'='*60}")

        tifs = list_tifs(s3, prefix)
        print(f"Found {len(tifs)} TIF(s)")

        for key, size in tifs:
            saved = recompress_tif(s3, key, is_landsat, dry_run)
            if saved is None:
                total_skipped += 1
            else:
                total_processed += 1
                total_saved += saved

    print(f"\n{'='*60}")
    print(f"Summary {'(DRY RUN)' if dry_run else ''}")
    print(f"  Processed: {total_processed}")
    print(f"  Skipped (already optimized): {total_skipped}")
    print(f"  Total space saved: {total_saved / 1024 / 1024:.1f} MB")
    if dry_run:
        print(f"\nRun with --apply to actually recompress and re-upload.")


if __name__ == "__main__":
    main()
