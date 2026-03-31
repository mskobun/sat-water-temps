"""ECOSTRESS processor — handles ECOSTRESS SQS messages from the CMR-STAC initiator.

For each (AID, date) message:
1. Open COGs from NASA Earthdata Cloud via earthaccess
2. Clip to polygon using rasterio.mask
3. Apply ECOSTRESS-specific QC/cloud/water filtering
4. Output TIF/CSV/PNGs + Parquet
5. Upload to R2 and insert metadata into D1
"""

import json
import os
import time

import earthaccess
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import shape, mapping

from common.polygons import get_aid_folder_mapping
from common.storage import get_s3_client, upload_to_r2, upload_csv_to_r2
from common.metadata import affine_transform_to_dict, insert_metadata_to_d1
from common.visualization import tif_to_png
from common.parquet import upload_parquet_to_r2
from common.statistics import compute_filter_stats, summarize_temperature_series
from common.exceptions import NoDataError
from ecostress.filters import apply_ecostress_filters
from d1 import log_job_to_d1


R2_PREFIX = "ECO"


def _open_ecostress_cog(href, session_env):
    """Open an ECOSTRESS COG from Earthdata Cloud."""
    return rasterio.open(href)


def process_one_record(body):
    """Process a single ECOSTRESS SQS message body.

    body = {
        "source": "ecostress",
        "aid": 1,
        "date": "2024-12-27T04:19:23",
        "name": "Magat",
        "location": "lake",
        "granules": [{
            "granule_id": "...",
            "hrefs": {"SurfaceTemperature": "https://...", "QC": "https://...", ...}
        }]
    }
    """
    aid = body["aid"]
    date_str = body["date"]
    date_day = date_str[:10]
    name = body["name"]
    location = body.get("location", "lake")
    granules = body["granules"]
    feature_id = f"{name}/{location}" if location != "lake" else name

    print(f"[ECOSTRESS][{feature_id}] Processing {len(granules)} granule(s) for date={date_str}")

    start_time = time.time()

    log_job_to_d1(
        job_type="ecostress_process",
        feature_id=feature_id,
        date=date_str,
        status="started",
        fatal=False,
    )

    work_dir = f"/tmp/ecostress_{aid}_{date_day}"
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Load polygon for clipping
        with open("static/polygons_new.geojson") as f:
            roi = json.load(f)
        polygon_geom = shape(roi["features"][aid - 1]["geometry"])
        clip_shapes = [mapping(polygon_geom)]

        # Authenticate with Earthdata for S3 access
        auth = earthaccess.login()

        # Get S3 credentials for LPDAAC (ECOSTRESS COGs)
        s3_creds = auth.get_s3_credentials(daac="LPDAAC")
        env_kwargs = {
            "aws_access_key_id": s3_creds["accessKeyId"],
            "aws_secret_access_key": s3_creds["secretAccessKey"],
            "aws_session_token": s3_creds["sessionToken"],
        }

        # Use first granule (or mosaic if multiple — rare for ECOSTRESS)
        granule = granules[0]
        hrefs = granule["hrefs"]

        with rasterio.Env(**env_kwargs):
            # Read and clip each band
            with rasterio.open(hrefs["SurfaceTemperature"]) as src:
                lst_clipped, lst_transform = mask(src, clip_shapes, crop=True)
                lst_meta = src.meta.copy()
                lst_meta.update(
                    height=lst_clipped.shape[1],
                    width=lst_clipped.shape[2],
                    transform=lst_transform,
                )
            lst_data = lst_clipped[0].astype(np.float32)

            with rasterio.open(hrefs["QC"]) as src:
                qc_clipped, _ = mask(src, clip_shapes, crop=True)
            qc_data = qc_clipped[0]

            with rasterio.open(hrefs["WaterMask"]) as src:
                water_clipped, _ = mask(src, clip_shapes, crop=True)
            water_data = water_clipped[0]

            with rasterio.open(hrefs["CloudMask"]) as src:
                cloud_clipped, _ = mask(src, clip_shapes, crop=True)
            cloud_data = cloud_clipped[0]

        # Apply ECOSTRESS-specific filters
        filtered_lst, filter_flags, has_water = apply_ecostress_filters(
            lst_data, qc_data, water_data, cloud_data
        )

        # Compute filter statistics
        flat_flags = filter_flags.flatten()
        filter_stats = compute_filter_stats(flat_flags, len(flat_flags))

        rows, cols = filtered_lst.shape
        suffix = "" if has_water else "_wtoff"
        base_name = f"{name}_{location}_{date_day}_filter{suffix}"
        filter_tif_path = os.path.join(work_dir, f"{base_name}.tif")

        # Write filtered TIF
        tif_meta = lst_meta.copy()
        tif_meta.update(dtype=rasterio.float32, count=1, nodata=np.nan, compress='deflate')

        with rasterio.open(filter_tif_path, "w", **tif_meta) as dst:
            dst.write(filtered_lst, 1)

        # Generate CSV with geographic coordinates (ECOSTRESS is already geographic CRS)
        row_idx, col_idx = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
        lons, lats = rasterio.transform.xy(lst_transform, row_idx.flatten(), col_idx.flatten())

        df = pd.DataFrame({
            "longitude": lons,
            "latitude": lats,
            "row": row_idx.flatten(),
            "col": col_idx.flatten(),
            "LST_filter": filtered_lst.flatten(),
        })
        df_valid = df.dropna(subset=["LST_filter"])

        if len(df_valid) == 0:
            raise NoDataError(filter_stats)

        filter_csv_path = os.path.join(work_dir, f"{base_name}.csv")
        df_valid.to_csv(filter_csv_path, index=False)

        # Upload to R2
        s3_client = get_s3_client()
        bucket_name = os.environ.get("R2_BUCKET_NAME", "multitifs")

        tif_key = f"{R2_PREFIX}/{name}/{location}/{base_name}.tif"
        upload_to_r2(s3_client, bucket_name, tif_key, filter_tif_path, "image/tiff")

        csv_key = f"{R2_PREFIX}/{name}/{location}/{base_name}.csv.gz"
        upload_csv_to_r2(s3_client, bucket_name, csv_key, filter_csv_path)

        # Parquet (per-year sorted file)
        parquet_base_key = f"{R2_PREFIX}/{name}/{location}/{name}_{location}.parquet"
        parquet_key = upload_parquet_to_r2(s3_client, bucket_name, parquet_base_key, df_valid, date_str)

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
                print(f"[ECOSTRESS][{feature_id}] PNG generation failed for {scale}: {e}")

        if not png_r2_keys:
            raise Exception("Failed to generate any PNG visualizations")

        # Metadata
        hist = filter_stats["histogram"]
        valid_pixels = hist.get("0", 0)
        land_pixels = sum(hist.get(str(i), 0) for i in range(16) if i & 4) if has_water else 0

        # WGS84 pixel size in degrees (ECOSTRESS rasters are geographic)
        tf = lst_transform
        pixel_size_deg_x = abs(tf.a)
        pixel_size_deg_y = abs(tf.e)

        temperature_stats = summarize_temperature_series(df_valid["LST_filter"])
        metadata = {
            "date": date_str,
            **temperature_stats,
            "data_points": int(len(df_valid)),
            "water_pixel_count": valid_pixels,
            "land_pixel_count": land_pixels,
            "wtoff": not has_water,
            "filter_stats": filter_stats,
            "pixel_size": float(pixel_size_deg_y),
            "pixel_size_x": float(pixel_size_deg_x),
            "source_crs": lst_meta["crs"].to_string() if lst_meta.get("crs") else None,
            "transform": affine_transform_to_dict(lst_transform),
        }

        # Upload metadata JSON
        metadata_path = os.path.join(work_dir, f"{base_name}_metadata.json")
        with open(metadata_path, "w") as f:
            json.dump(metadata, f)
        meta_key = f"{R2_PREFIX}/{name}/{location}/metadata/{base_name}_metadata.json"
        upload_to_r2(s3_client, bucket_name, meta_key, metadata_path, "application/json")

        # Insert into D1 with source='ecostress'
        insert_metadata_to_d1(feature_id, date_str, metadata, csv_key, tif_key, png_r2_keys,
                              source="ecostress", parquet_path=parquet_key)

        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="ecostress_process",
            feature_id=feature_id,
            date=date_str,
            status="success",
            duration_ms=duration_ms,
        )
        print(f"[ECOSTRESS][{feature_id}] ✓ Processed successfully in {duration_ms}ms")

    except NoDataError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="ecostress_process",
            feature_id=feature_id,
            date=date_str,
            status="nodata",
            duration_ms=duration_ms,
            metadata_json=json.dumps({"filter_stats": e.filter_stats}),
        )
        print(f"[ECOSTRESS][{feature_id}] ○ No valid pixels (nodata) in {duration_ms}ms")
        raise

    except Exception as e:
        import traceback
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="ecostress_process",
            feature_id=feature_id,
            date=date_str,
            status="failed",
            duration_ms=duration_ms,
            error_message=str(e),
        )
        print(f"[ECOSTRESS][{feature_id}] ✗ Failed: {e}")
        print(f"[ECOSTRESS][{feature_id}] Traceback: {traceback.format_exc()}")
        raise

    finally:
        import shutil
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
