"""Landsat processor — handles Landsat SQS messages routed from the main processor.

For each (AID, date) message:
1. Open COGs from s3://usgs-landsat via rasterio with requester-pays
2. Mosaic multiple scenes if needed
3. Clip to polygon, apply QA_PIXEL bitmask, compute stats
4. Output TIF/CSV/PNGs matching ECOSTRESS format
5. Upload to R2 and insert metadata into D1
"""

import json
import os
import time

import boto3
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from rasterio.session import AWSSession
from shapely.geometry import shape, mapping

from processor import (
    _get_aid_folder_mapping,
    _get_s3_client,
    tif_to_png,
    upload_to_r2,
    compute_filter_stats,
    insert_metadata_to_d1,
    GLOBAL_MIN,
    GLOBAL_MAX,
)
from d1 import log_job_to_d1


R2_PREFIX = "LANDSAT"

# Landsat ST_B10 scale factors
SCALE_FACTOR = 0.00341802
ADD_OFFSET = 149.0

# QA_PIXEL bitmask positions
QA_BIT_FILL = 0          # Bit 0: fill
QA_BIT_DILATED_CLOUD = 1 # Bit 1: dilated cloud
QA_BIT_CLOUD = 3          # Bit 3: cloud
QA_BIT_CLOUD_SHADOW = 4   # Bit 4: cloud shadow
QA_BIT_WATER = 7           # Bit 7: water


def _check_bit(array, bit):
    """Check if a specific bit is set in the array."""
    return (array & (1 << bit)) != 0


def apply_landsat_filters(lst_kelvin, qa_pixel):
    """Apply QA_PIXEL bitmask filtering to Landsat data.

    Returns:
        filtered_lst: LST array with rejected pixels set to NaN
        filter_flags: 4-bit flags per pixel (bit 0=fill/cloud/shadow, bit 2=non-water, bit 3=nodata)
        water_mask_active: whether water filtering was applied
    """
    filter_flags = np.zeros(lst_kelvin.shape, dtype=np.uint8)

    # Bit 3: NoData (fill pixels or zero LST)
    fill_mask = _check_bit(qa_pixel, QA_BIT_FILL)
    nodata_mask = fill_mask | np.isnan(lst_kelvin) | (lst_kelvin <= 0)
    filter_flags = np.where(nodata_mask, filter_flags | 8, filter_flags)

    # Bit 1: Cloud filtering (dilated cloud, cloud, cloud shadow)
    cloud_mask = (
        _check_bit(qa_pixel, QA_BIT_DILATED_CLOUD) |
        _check_bit(qa_pixel, QA_BIT_CLOUD) |
        _check_bit(qa_pixel, QA_BIT_CLOUD_SHADOW)
    )
    filter_flags = np.where(cloud_mask, filter_flags | 2, filter_flags)

    # Bit 2: Water mask — keep only water pixels
    water_mask = _check_bit(qa_pixel, QA_BIT_WATER)
    has_water = bool(np.any(water_mask))
    if has_water:
        non_water_mask = ~water_mask
        filter_flags = np.where(non_water_mask, filter_flags | 4, filter_flags)
    else:
        # No water detected — don't apply water filter
        pass

    # Apply all filters to LST
    filtered_lst = lst_kelvin.copy()
    reject_mask = filter_flags > 0
    filtered_lst[reject_mask] = np.nan

    return filtered_lst, filter_flags, has_water


def _open_cog(href):
    """Open a COG from S3 with requester-pays."""
    aws_session = AWSSession(boto3.Session(), requester_pays=True)
    env = rasterio.Env(AWSSession=aws_session, AWS_REQUEST_PAYER='requester')
    env.__enter__()
    return rasterio.open(href)


def process_one_record(body):
    """Process a single Landsat SQS message body.

    body = {
        "source": "landsat",
        "aid": 1,
        "date": "2024-12-27",
        "name": "Magat",
        "location": "lake",
        "scenes": [
            {
                "scene_id": "LC09_...",
                "hrefs": {"lwir11": "s3://...", "qa": "s3://...", "qa_pixel": "s3://..."},
                "cloud_cover": 11.47
            }
        ]
    }
    """
    aid = body["aid"]
    date = body["date"]
    name = body["name"]
    location = body.get("location", "lake")
    scenes = body["scenes"]
    feature_id = f"{name}/{location}" if location != "lake" else name

    print(f"[Landsat][{feature_id}] Processing {len(scenes)} scene(s) for date={date}")

    start_time = time.time()

    log_job_to_d1(
        job_type="landsat_process",
        feature_id=feature_id,
        date=date,
        status="started",
        fatal=False,
    )

    work_dir = f"/tmp/landsat_{aid}_{date}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Load polygon for clipping
        mapping_data = _get_aid_folder_mapping()
        with open("static/polygons_new.geojson") as f:
            roi = json.load(f)
        polygon_geom = shape(roi["features"][aid - 1]["geometry"])
        polygon_geojson = [mapping(polygon_geom)]

        # Open all ST_B10 and QA_PIXEL rasters with requester-pays session
        aws_session = AWSSession(boto3.Session(), requester_pays=True)

        with rasterio.Env(AWSSession=aws_session, AWS_REQUEST_PAYER='requester'):
            # Read and mosaic ST_B10
            st_datasets = []
            qa_pixel_datasets = []

            for scene in scenes:
                hrefs = scene["hrefs"]
                st_datasets.append(rasterio.open(hrefs["lwir11"]))
                qa_pixel_datasets.append(rasterio.open(hrefs["qa_pixel"]))

            # Mosaic if multiple scenes
            if len(st_datasets) == 1:
                st_src = st_datasets[0]
                qa_src = qa_pixel_datasets[0]
            else:
                # Merge ST_B10
                st_mosaic, st_transform = merge(st_datasets)
                # Create a temporary dataset for the mosaic
                st_profile = st_datasets[0].profile.copy()
                st_profile.update(
                    height=st_mosaic.shape[1],
                    width=st_mosaic.shape[2],
                    transform=st_transform,
                )
                st_path = os.path.join(work_dir, "st_mosaic.tif")
                with rasterio.open(st_path, "w", **st_profile) as dst:
                    dst.write(st_mosaic)
                st_src = rasterio.open(st_path)

                # Merge QA_PIXEL
                qa_mosaic, qa_transform = merge(qa_pixel_datasets)
                qa_profile = qa_pixel_datasets[0].profile.copy()
                qa_profile.update(
                    height=qa_mosaic.shape[1],
                    width=qa_mosaic.shape[2],
                    transform=qa_transform,
                )
                qa_path = os.path.join(work_dir, "qa_mosaic.tif")
                with rasterio.open(qa_path, "w", **qa_profile) as dst:
                    dst.write(qa_mosaic)
                qa_src = rasterio.open(qa_path)

            # Clip to polygon
            st_clipped, st_transform = mask(st_src, polygon_geojson, crop=True)
            qa_clipped, _ = mask(qa_src, polygon_geojson, crop=True, nodata=0)

            st_meta = st_src.meta.copy()
            st_meta.update(
                height=st_clipped.shape[1],
                width=st_clipped.shape[2],
                transform=st_transform,
            )

            # Close source datasets
            for ds in st_datasets + qa_pixel_datasets:
                ds.close()
            if len(scenes) > 1:
                st_src.close()
                qa_src.close()

        # Scale to Kelvin
        st_data = st_clipped[0].astype(np.float32)
        qa_data = qa_clipped[0].astype(np.uint16)

        # Apply scale: DN * 0.00341802 + 149.0
        # Treat 0 as nodata before scaling
        valid_mask = st_data > 0
        lst_kelvin = np.full_like(st_data, np.nan, dtype=np.float32)
        lst_kelvin[valid_mask] = st_data[valid_mask] * SCALE_FACTOR + ADD_OFFSET

        # Apply QA filters
        filtered_lst, filter_flags, has_water = apply_landsat_filters(lst_kelvin, qa_data)

        # Compute filter statistics
        # Flatten for stats (exclude padding from mask operation)
        flat_flags = filter_flags.flatten()
        total_pixels = int(np.sum(st_clipped[0] != 0))  # Non-fill pixels within clip
        filter_stats = compute_filter_stats(flat_flags, len(flat_flags))

        # Build 5-band TIF for tif_to_png() compatibility
        # Band 1 = filtered LST, bands 2-5 = NaN placeholders
        rows, cols = filtered_lst.shape
        bands = np.full((5, rows, cols), np.nan, dtype=np.float32)
        bands[0] = filtered_lst

        suffix = "" if has_water else "_wtoff"
        base_name = f"{name}_{location}_{date}_filter{suffix}"
        filter_tif_path = os.path.join(work_dir, f"{base_name}.tif")

        tif_meta = st_meta.copy()
        tif_meta.update(dtype=rasterio.float32, count=5, nodata=np.nan)

        with rasterio.open(filter_tif_path, "w", **tif_meta) as dst:
            for i in range(5):
                dst.write(bands[i], i + 1)

        # Generate CSV
        row_idx, col_idx = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
        lons, lats = rasterio.transform.xy(st_transform, row_idx.flatten(), col_idx.flatten())

        df = pd.DataFrame({
            "longitude": lons,
            "latitude": lats,
            "LST_filter": filtered_lst.flatten(),
            "QA_PIXEL": qa_data.flatten(),
        })
        # Drop NaN LST rows (filtered or nodata)
        df_valid = df.dropna(subset=["LST_filter"])

        filter_csv_path = os.path.join(work_dir, f"{base_name}.csv")
        df_valid.to_csv(filter_csv_path, index=False)

        # Upload to R2
        s3_client = _get_s3_client()
        bucket_name = os.environ.get("R2_BUCKET_NAME", "multitifs")

        tif_key = f"{R2_PREFIX}/{name}/{location}/{base_name}.tif"
        upload_to_r2(s3_client, bucket_name, tif_key, filter_tif_path, "image/tiff")

        csv_key = f"{R2_PREFIX}/{name}/{location}/{base_name}.csv"
        upload_to_r2(s3_client, bucket_name, csv_key, filter_csv_path, "text/csv")

        # PNGs
        png_r2_keys = {}
        for scale in ["relative", "fixed", "gray"]:
            try:
                png_bytes = tif_to_png(filter_tif_path, color_scale=scale)
                png_path = os.path.join(work_dir, f"{base_name}_{scale}.png")
                with open(png_path, "wb") as f:
                    f.write(png_bytes.getvalue())
                png_key = f"{R2_PREFIX}/{name}/{location}/{base_name}_{scale}.png"
                upload_to_r2(s3_client, bucket_name, png_key, png_path, "image/png")
                png_r2_keys[scale] = png_key
            except Exception as e:
                print(f"[Landsat][{feature_id}] PNG generation failed for {scale}: {e}")

        if not png_r2_keys:
            raise Exception("Failed to generate any PNG visualizations")

        # Metadata
        hist = filter_stats["histogram"]
        valid_pixels = hist.get("0", 0)
        land_pixels = sum(hist.get(str(i), 0) for i in range(16) if i & 4) if has_water else 0

        metadata = {
            "date": date,
            "min_temp": float(np.nanmin(filtered_lst)) if not np.all(np.isnan(filtered_lst)) else None,
            "max_temp": float(np.nanmax(filtered_lst)) if not np.all(np.isnan(filtered_lst)) else None,
            "data_points": int(len(df_valid)),
            "water_pixel_count": valid_pixels,
            "land_pixel_count": land_pixels,
            "wtoff": not has_water,
            "filter_stats": filter_stats,
        }

        # Upload metadata JSON
        metadata_path = os.path.join(work_dir, f"{base_name}_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)
        meta_key = f"{R2_PREFIX}/{name}/{location}/metadata/{base_name}_metadata.json"
        upload_to_r2(s3_client, bucket_name, meta_key, metadata_path, "application/json")

        # Insert into D1 with source='landsat'
        insert_metadata_to_d1(feature_id, date, metadata, csv_key, tif_key, png_r2_keys,
                              source="landsat")

        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="landsat_process",
            feature_id=feature_id,
            date=date,
            status="success",
            duration_ms=duration_ms,
        )
        print(f"[Landsat][{feature_id}] ✓ Processed successfully in {duration_ms}ms")

    except Exception as e:
        import traceback
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="landsat_process",
            feature_id=feature_id,
            date=date,
            status="failed",
            duration_ms=duration_ms,
            error_message=str(e),
        )
        print(f"[Landsat][{feature_id}] ✗ Failed: {e}")
        print(f"[Landsat][{feature_id}] Traceback: {traceback.format_exc()}")
        raise

    finally:
        import shutil
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
