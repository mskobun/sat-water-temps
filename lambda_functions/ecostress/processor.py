"""ECOSTRESS processor — handles ECOSTRESS SQS messages from the CMR-STAC initiator.

For each (AID, date) message:
1. Open COGs from NASA Earthdata Cloud via earthaccess
2. Clip to polygon using rasterio.mask
3. Apply ECOSTRESS-specific QC/cloud/water filtering
4. Output TIF/CSV/PNGs + Parquet
5. Upload to R2 and insert metadata into D1
"""

import json
import math
import os
import time

import earthaccess
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import transform_geom
from shapely.geometry import shape, mapping, box

from common.storage import get_s3_client, upload_to_r2, upload_csv_to_r2
from common.metadata import affine_transform_to_dict, insert_metadata_to_d1
from common.visualization import tif_to_png
from common.parquet import upload_parquet_to_r2
from common.statistics import compute_filter_stats, summarize_temperature_series
from common.exceptions import NoDataError
from ecostress.filters import apply_ecostress_filters
from d1 import log_job_to_d1


R2_PREFIX = "ECO"


def _clip_band(src, clip_shapes, **kwargs):
    """Clip a raster band, reprojecting the polygon to the raster's CRS."""
    raster_crs = src.crs
    if raster_crs and not raster_crs.to_epsg() == 4326:
        projected = [transform_geom("EPSG:4326", raster_crs, s) for s in clip_shapes]
    else:
        projected = clip_shapes
    return mask(src, projected, crop=True, **kwargs)


def _merge_and_clip(datasets, clip_shapes, work_dir, band_name):
    """Merge multiple raster datasets into a mosaic, then clip to polygon."""
    mosaic, mosaic_transform = merge(datasets)
    meta = datasets[0].meta.copy()
    meta.update(
        height=mosaic.shape[1],
        width=mosaic.shape[2],
        transform=mosaic_transform,
    )
    merge_path = os.path.join(work_dir, f"{band_name}_merged.tif")
    with rasterio.open(merge_path, "w", **meta) as dst:
        dst.write(mosaic)
    with rasterio.open(merge_path) as src:
        clipped, clip_transform = _clip_band(src, clip_shapes)
        clip_meta = src.meta.copy()
        clip_meta.update(
            height=clipped.shape[1],
            width=clipped.shape[2],
            transform=clip_transform,
        )
    return clipped, clip_transform, clip_meta


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
            "hrefs": {"LST": "s3://...", "QC": "s3://...", "water": "s3://...", ...}
        }]
    }
    """
    aid = body["aid"]
    date_str = body["date"]
    date_day = date_str[:10]
    name = body["name"]
    location = body.get("location", "lake")
    task_id = body.get("task_id")
    granules = body["granules"]
    feature_id = f"{name}/{location}" if location != "lake" else name

    print(f"[ECOSTRESS][{feature_id}] Processing {len(granules)} granule(s) for date={date_str}")

    start_time = time.time()

    log_job_to_d1(
        job_type="ecostress_process",
        task_id=task_id,
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

        # earthaccess detects region by querying EC2 IMDS at 169.254.169.254,
        # which doesn't exist in Lambda (Firecracker microVMs). The request
        # times out and in_region defaults to False. Override it.
        earthaccess.login()
        earthaccess.__store__.in_region = True

        # L2T v002 COGs are small UTM tiles — a CMR bbox search can
        # return multiple tiles needed to cover the polygon.  Open all
        # overlapping tiles and merge them (like Landsat scenes).
        lst_datasets = []
        qc_datasets = []
        water_datasets = []
        cloud_datasets = []

        for gi, granule in enumerate(granules):
            hrefs = granule["hrefs"]
            try:
                band_keys = ["LST", "QC", "water", "cloud"]
                band_uris = {k: hrefs[k] for k in band_keys}
                file_objects = earthaccess.open(
                    list(band_uris.values()),
                    credentials_endpoint="https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials",
                )
                file_map = dict(zip(band_keys, file_objects))

                lst_src = rasterio.open(file_map["LST"])
                raster_crs = lst_src.crs
                if raster_crs and raster_crs.to_epsg() != 4326:
                    poly_proj = shape(transform_geom("EPSG:4326", raster_crs, mapping(polygon_geom)))
                else:
                    poly_proj = polygon_geom

                if not box(*lst_src.bounds).intersects(poly_proj):
                    lst_src.close()
                    print(f"[ECOSTRESS][{feature_id}] Granule {gi+1}/{len(granules)} does not overlap, skipping")
                    continue

                lst_datasets.append(lst_src)
                qc_datasets.append(rasterio.open(file_map["QC"]))
                water_datasets.append(rasterio.open(file_map["water"]))
                cloud_datasets.append(rasterio.open(file_map["cloud"]))
                print(f"[ECOSTRESS][{feature_id}] Granule {gi+1}/{len(granules)} overlaps polygon")

            except Exception as e:
                print(f"[ECOSTRESS][{feature_id}] Error opening granule {gi+1}/{len(granules)}: {e}")
                continue

        if not lst_datasets:
            raise NoDataError({"reason": "no_overlap", "granules_tried": len(granules)})

        print(f"[ECOSTRESS][{feature_id}] Using {len(lst_datasets)}/{len(granules)} overlapping granule(s)")

        all_datasets = list(lst_datasets) + list(qc_datasets) + list(water_datasets) + list(cloud_datasets)
        try:
            # Filter to a single CRS before merging (tiles at UTM zone
            # boundaries can straddle two EPSG codes).
            if len(lst_datasets) > 1:
                crs_groups = {}
                for i, ds in enumerate(lst_datasets):
                    epsg = ds.crs.to_epsg()
                    crs_groups.setdefault(epsg, []).append(i)
                if len(crs_groups) > 1:
                    best_epsg = max(crs_groups, key=lambda k: len(crs_groups[k]))
                    keep = crs_groups[best_epsg]
                    print(f"[ECOSTRESS][{feature_id}] Mixed CRS {set(crs_groups)}, keeping {len(keep)} in EPSG:{best_epsg}")
                    lst_datasets = [lst_datasets[i] for i in keep]
                    qc_datasets = [qc_datasets[i] for i in keep]
                    water_datasets = [water_datasets[i] for i in keep]
                    cloud_datasets = [cloud_datasets[i] for i in keep]

            if len(lst_datasets) == 1:
                lst_clipped, lst_transform = _clip_band(lst_datasets[0], clip_shapes)
                lst_meta = lst_datasets[0].meta.copy()
                lst_meta.update(
                    height=lst_clipped.shape[1],
                    width=lst_clipped.shape[2],
                    transform=lst_transform,
                )
                qc_clipped, _ = _clip_band(qc_datasets[0], clip_shapes)
                water_clipped, _ = _clip_band(water_datasets[0], clip_shapes)
                cloud_clipped, _ = _clip_band(cloud_datasets[0], clip_shapes)
            else:
                lst_clipped, lst_transform, lst_meta = _merge_and_clip(
                    lst_datasets, clip_shapes, work_dir, "lst"
                )
                qc_clipped, _, _ = _merge_and_clip(
                    qc_datasets, clip_shapes, work_dir, "qc"
                )
                water_clipped, _, _ = _merge_and_clip(
                    water_datasets, clip_shapes, work_dir, "water"
                )
                cloud_clipped, _, _ = _merge_and_clip(
                    cloud_datasets, clip_shapes, work_dir, "cloud"
                )
        finally:
            for ds in all_datasets:
                try:
                    ds.close()
                except Exception:
                    pass

        lst_data = lst_clipped[0].astype(np.float32)
        qc_data = qc_clipped[0]
        water_data = water_clipped[0]
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

        # Generate CSV with WGS84 coordinates.
        # L2T v002 COGs are UTM-projected; reproject pixel centres to EPSG:4326.
        row_idx, col_idx = np.meshgrid(np.arange(rows), np.arange(cols), indexing="ij")
        xs, ys = rasterio.transform.xy(lst_transform, row_idx.flatten(), col_idx.flatten())

        raster_crs = lst_meta.get("crs")
        if raster_crs and raster_crs.to_epsg() != 4326:
            from rasterio.warp import transform as warp_transform
            lons, lats = warp_transform(raster_crs, "EPSG:4326", xs, ys)
        else:
            lons, lats = xs, ys

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

        # Pixel size in WGS84 degrees.
        # L2T v002 COGs are UTM-projected (meters) — convert to approximate degrees.
        tf = lst_transform
        if raster_crs and raster_crs.to_epsg() != 4326:
            mid_lat = polygon_geom.centroid.y
            pixel_m = abs(tf.a)
            pixel_size_deg_x = pixel_m / (111320 * math.cos(math.radians(mid_lat)))
            pixel_size_deg_y = pixel_m / 110540
        else:
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
            task_id=task_id,
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
            task_id=task_id,
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
            task_id=task_id,
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
