import json
import os
import numpy as np
import pandas as pd
import geopandas as gpd
import io
import matplotlib.pyplot as plt
from PIL import Image
from typing import Dict
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all
from d1 import query_d1, log_job_to_d1
from shared import get_token, create_http_session, extract_metadata

import boto3
import rasterio

# Patch all supported libraries for automatic X-Ray tracing
patch_all()

# Constants
INVALID_QC_VALUES = {15, 2501, 3525, 65535}
HTTP_CONNECT_TIMEOUT = 10
HTTP_READ_TIMEOUT = 120
DOWNLOAD_CHUNK_SIZE = 64 * 1024
GLOBAL_MIN = 273.15  # Kelvin
GLOBAL_MAX = 308.15  # Kelvin

# Module-level caches (persist across warm invocations)
_aid_folder_mapping = None
_s3_client = None


def _get_aid_folder_mapping():
    """Load and cache ROI polygon mapping. Persists across warm Lambda invocations."""
    global _aid_folder_mapping
    if _aid_folder_mapping is None:
        roi = gpd.read_file("static/polygons_new.geojson")
        _aid_folder_mapping = {}
        for idx, row in roi.iterrows():
            _aid_folder_mapping[int(idx + 1)] = (row["name"], row["location"])
    return _aid_folder_mapping


def _get_s3_client():
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


def insert_metadata_to_d1(
    feature_id: str,
    date: str,
    metadata: Dict,
    csv_r2_key: str,
    tif_r2_key: str,
    png_r2_keys: Dict[str, str],
):
    """Insert only metadata into D1 (temperature data stays in R2).

    query_d1 raises on failure by default, so no manual success checks needed.
    """
    # Use actual R2 paths from upload
    csv_path = csv_r2_key
    tif_path = tif_r2_key
    # Use relative scale PNG (main PNG)
    png_path = png_r2_keys.get("relative", png_r2_keys.get("fixed", ""))

    # Insert/update feature record FIRST (to satisfy foreign key constraint)
    name, location = (
        feature_id.split("/") if "/" in feature_id else (feature_id, "lake")
    )
    feature_sql = """
    INSERT INTO features (id, name, location, latest_date, last_updated)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        latest_date = CASE
            WHEN excluded.latest_date > latest_date THEN excluded.latest_date
            ELSE latest_date
        END,
        last_updated = excluded.last_updated
    """
    import time

    feature_params = [feature_id, name, location, date, int(time.time())]

    with xray_recorder.capture("d1_insert_feature") as subsegment:
        subsegment.put_metadata("feature_id", feature_id)
        query_d1(feature_sql, feature_params)

    # Now insert metadata with file paths (after feature exists)
    meta_sql = """
    INSERT OR REPLACE INTO temperature_metadata
    (feature_id, date, min_temp, max_temp, mean_temp, median_temp, std_dev,
     data_points, water_pixel_count, land_pixel_count, wtoff,
     csv_path, tif_path, png_path, filter_stats)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    # Serialize filter_stats to JSON
    filter_stats_json = json.dumps(metadata.get("filter_stats", {}))

    meta_params = [
        feature_id,
        date,
        metadata.get("min_temp"),
        metadata.get("max_temp"),
        metadata.get("mean_temp"),
        metadata.get("median_temp"),
        metadata.get("std_dev"),
        metadata.get("data_points", 0),
        metadata.get("water_pixel_count", 0),
        metadata.get("land_pixel_count", 0),
        1 if metadata.get("wtoff", False) else 0,
        csv_path,
        tif_path,
        png_path,
        filter_stats_json,
    ]
    with xray_recorder.capture("d1_insert_temperature_metadata") as subsegment:
        subsegment.put_metadata("feature_id", feature_id)
        subsegment.put_metadata("date", date)
        subsegment.put_metadata(
            "has_filter_stats", bool(filter_stats_json and filter_stats_json != "{}")
        )
        query_d1(meta_sql, meta_params)

    print(f"✓ Inserted metadata to D1 with R2 paths")


def normalize(data):
    data = np.where(np.isfinite(data), data, np.nan)
    min_val, max_val = np.nanmin(data), np.nanmax(data)
    if np.isnan(min_val) or np.isnan(max_val) or max_val == min_val:
        return np.zeros_like(data, dtype=np.uint8), np.zeros_like(data, dtype=np.uint8)
    norm_data = np.nan_to_num(
        (data - min_val) / (max_val - min_val) * 255, nan=0
    ).astype(np.uint8)
    alpha_mask = np.where(np.isnan(data) | (data < -1000), 0, 255).astype(np.uint8)
    return norm_data, alpha_mask


def tif_to_png(tif_path, color_scale="relative"):
    with rasterio.open(tif_path) as dataset:
        num_bands = dataset.count
        if num_bands < 5:
            img = Image.new("RGBA", (256, 256), (255, 0, 0, 0))
            img_bytes = io.BytesIO()
            img.save(img_bytes, format="PNG")
            img_bytes.seek(0)
            return img_bytes

        if color_scale == "fixed":
            band = dataset.read(1).astype(np.float32)
            band[np.isnan(band)] = 0
            band = np.clip(band, GLOBAL_MIN, GLOBAL_MAX)
            norm_band = ((band - GLOBAL_MIN) / (GLOBAL_MAX - GLOBAL_MIN) * 255).astype(
                np.uint8
            )
            alpha_mask = np.where(band <= GLOBAL_MIN, 0, 255).astype(np.uint8)
            cmap = plt.get_cmap("jet")
            rgba_img = cmap(norm_band / 255.0)
            rgba_img = (rgba_img * 255).astype(np.uint8)
            rgba_img[..., 3] = alpha_mask
        elif color_scale == "relative":
            bands = [dataset.read(band) for band in range(1, num_bands + 1)]
            norm_bands, alpha_mask = zip(*[normalize(band) for band in bands])
            norm_band = norm_bands[0]
            cmap = plt.get_cmap("jet")
            rgba_img = cmap(norm_band / 255.0)
            rgba_img = (rgba_img * 255).astype(np.uint8)
            rgba_img[..., 3] = alpha_mask[0]
        elif color_scale == "gray":
            bands = [dataset.read(band) for band in range(1, num_bands + 1)]
            norm_bands, alpha_mask = zip(*[normalize(band) for band in bands])
            img_array = np.stack([norm_bands[0], norm_bands[0], norm_bands[0]], axis=-1)
            img_array = np.dstack((img_array, alpha_mask[0]))
            rgba_img = img_array
        else:
            raise ValueError(f"Invalid color_scale: {color_scale}")

        img = Image.fromarray(rgba_img, mode="RGBA")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
    return img_bytes


def read_raster(layer_name, relevant_files):
    matches = [f for f in relevant_files if layer_name in f]
    return rasterio.open(matches[0]) if matches else None


def read_array(raster):
    return raster.read(1) if raster else None


def upload_to_r2(s3_client, bucket_name, key, file_path, content_type=None):
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    with open(file_path, "rb") as f:
        s3_client.upload_fileobj(f, bucket_name, key, ExtraArgs=extra_args)
    print(f"Uploaded {file_path} to {key}")


def compute_filter_stats(filter_flags, total_pixels, padding_count=0):
    """Compute filter statistics as bit flag histogram.

    total_pixels counts only pixels inside the polygon (excludes grid padding).
    padding_count is tracked separately for reference.
    """
    # Create histogram of bit flag values (0-15, 4 bits)
    histogram = {}
    for flag_value in range(16):
        count = int(np.sum(filter_flags == flag_value))
        if count > 0:  # Only store non-zero counts
            histogram[str(flag_value)] = count

    stats = {"total_pixels": int(total_pixels), "histogram": histogram}
    if padding_count > 0:
        stats["padding_count"] = padding_count
    return stats


def apply_filters(df, water_mask_flag):
    """Apply all pixel filters and return (filter_flags, suffix, padding_count).

    Drops padding pixels (outside polygon) from df before filtering.
    Padding is identified by QC fill values (NaN or -99999).

    Pixels inside the polygon with no LST data (swath gaps) are kept
    and tracked as bit 3 (NoData).

    Mutates df in place (adds *_filter columns, drops padding rows).
    Bit 0 = QC, Bit 1 = Cloud, Bit 2 = Water, Bit 3 = NoData (swath gap).
    """
    # Drop padding pixels outside polygon (QC fill value = -99999 or NaN)
    padding_mask = df["QC"].isna() | (df["QC"] == -99999)
    padding_count = int(padding_mask.sum())
    df.drop(df.index[padding_mask], inplace=True)
    df.reset_index(drop=True, inplace=True)

    filter_flags = np.zeros(len(df), dtype=np.uint8)

    # Bit 3: NoData / swath gap (inside polygon but no LST)
    nodata_mask = df["LST"].isna() | (df["LST"] <= 0)
    filter_flags = np.where(nodata_mask, filter_flags | 8, filter_flags)

    for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        df[f"{col}_filter"] = np.where(nodata_mask, np.nan, df[col])

    # Bit 0: QC filtering
    qc_mask = df["QC"].isin(INVALID_QC_VALUES)
    filter_flags = np.where(qc_mask, filter_flags | 1, filter_flags)

    for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        df[f"{col}_filter"] = np.where(qc_mask, np.nan, df[f"{col}_filter"])

    # Bit 1: Cloud filtering
    cloud_mask = df["cloud"] == 1
    filter_flags = np.where(cloud_mask, filter_flags | 2, filter_flags)

    for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        df[f"{col}_filter"] = np.where(cloud_mask, np.nan, df[f"{col}_filter"])

    suffix = ""
    if water_mask_flag:
        # Bit 2: Water mask — keep only water pixels
        water_mask = df["wt"] == 0
        filter_flags = np.where(water_mask, filter_flags | 4, filter_flags)

        for col in [
            "LST_filter", "LST_err_filter", "QC_filter",
            "EmisWB_filter", "height_filter",
        ]:
            df[col] = np.where(water_mask, np.nan, df[col])
    else:
        suffix = "_wtoff"

    return filter_flags, suffix, padding_count


def process_rasters(
    aid_number,
    date,
    selected_files,
    aid_folder_mapping,
    work_dir,
    s3_client,
    bucket_name,
):
    name, location = aid_folder_mapping.get(aid_number, (f"aid{aid_number}", "lake"))
    feature_id = f"{name}/{location}" if location != "lake" else name

    print(
        f"  [{feature_id}] Filtering {len(selected_files)} file(s) for aid={aid_number} date={date}"
    )
    relevant_files = []
    for f in selected_files:
        aid, f_date = extract_metadata(f)
        if aid == aid_number and date == f_date:
            relevant_files.append(f)

    if not relevant_files:
        error_msg = (
            f"No relevant files found after filtering for aid={aid_number} date={date}"
        )
        print(f"  [{feature_id}] ERROR: {error_msg}")
        raise ValueError(error_msg)

    print(f"  [{feature_id}] Found {len(relevant_files)} relevant file(s)")

    # Read raster layers
    print(f"  [{feature_id}] Reading raster layers...")
    LST = read_raster("LST_doy", relevant_files)
    LST_err = read_raster("LST_err", relevant_files)
    QC = read_raster("QC", relevant_files)
    wt = read_raster("water", relevant_files)
    cl = read_raster("cloud", relevant_files)
    EmisWB = read_raster("EmisWB", relevant_files)
    heig = read_raster("height", relevant_files)

    missing_layers = []
    layer_names = ["LST", "LST_err", "QC", "water", "cloud", "EmisWB", "height"]
    for layer_name, layer in zip(layer_names, [LST, LST_err, QC, wt, cl, EmisWB, heig]):
        if layer is None:
            missing_layers.append(layer_name)

    if missing_layers:
        error_msg = f"Missing required layers: {', '.join(missing_layers)}"
        print(f"  [{feature_id}] ERROR: {error_msg}")
        print(
            f"  [{feature_id}] Available files: {[os.path.basename(f) for f in relevant_files]}"
        )
        raise ValueError(error_msg)

    arrays = {
        "LST": read_array(LST),
        "LST_err": read_array(LST_err),
        "QC": read_array(QC),
        "wt": read_array(wt),
        "cloud": read_array(cl),
        "EmisWB": read_array(EmisWB),
        "height": read_array(heig),
    }

    print(f"  [{feature_id}] Processing raster data...")

    # Processing logic (simplified adaptation from original)
    rows, cols = arrays["LST"].shape

    # Create pixel coordinate grids
    col_idx, row_idx = np.meshgrid(np.arange(cols), np.arange(rows))

    # Convert pixel coordinates to geographic coordinates using raster transform
    transform = LST.transform
    # rasterio.transform.xy returns (x, y) = (longitude, latitude) for each pixel
    lons, lats = rasterio.transform.xy(transform, row_idx.flatten(), col_idx.flatten())

    df = pd.DataFrame(
        {
            "longitude": lons,
            "latitude": lats,
            **{key: arr.flatten() for key, arr in arrays.items()},
        }
    )

    # Track original grid indices before dropping nodata rows
    df["_grid_idx"] = np.arange(len(df))
    total_grid_pixels = len(df)
    water_mask_flag = df["wt"].isin([1]).any()
    filter_flags, suffix, padding_count = apply_filters(df, water_mask_flag)

    # Compute filter statistics (total_pixels = pixels inside polygon only)
    filter_stats = compute_filter_stats(filter_flags, len(df), padding_count)

    # Log to CloudWatch (compute stats from histogram for display)
    hist = filter_stats["histogram"]
    total = filter_stats["total_pixels"]
    valid = hist.get("0", 0)
    filtered_qc = sum(hist.get(str(i), 0) for i in range(16) if i & 1)  # Bit 0 set
    filtered_cloud = sum(hist.get(str(i), 0) for i in range(16) if i & 2)  # Bit 1 set
    filtered_water = sum(hist.get(str(i), 0) for i in range(16) if i & 4)  # Bit 2 set
    filtered_nodata = sum(hist.get(str(i), 0) for i in range(16) if i & 8)  # Bit 3 set

    print(f"Filter Statistics for {name}/{location} {date}:")
    print(f"  Grid pixels: {total_grid_pixels:,} (padding: {padding_count:,})")
    print(f"  Polygon pixels: {total:,}")
    print(f"  Valid pixels: {valid:,} ({valid / total * 100:.1f}%)")
    print(f"  Filtered: {total - valid:,} ({(total - valid) / total * 100:.1f}%)")
    print(f"    - NoData (swath gap): {filtered_nodata:,} ({filtered_nodata / total * 100:.1f}%)")
    print(f"    - QC filtered: {filtered_qc:,} ({filtered_qc / total * 100:.1f}%)")
    print(
        f"    - Cloud filtered: {filtered_cloud:,} ({filtered_cloud / total * 100:.1f}%)"
    )
    if water_mask_flag:
        print(
            f"    - Water mask filtered: {filtered_water:,} ({filtered_water / total * 100:.1f}%)"
        )

    # Reconstruct filtered rasters on the original grid (nodata rows become NaN)
    grid_size = rows * cols
    filtered_rasters = {}
    for col_name in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        full = np.full(grid_size, np.nan, dtype=np.float32)
        full[df["_grid_idx"].values] = df[f"{col_name}_filter"].values.astype(np.float32)
        filtered_rasters[col_name] = full.reshape(rows, cols)

    base_name = f"{name}_{location}_{date}_filter{suffix}"
    filter_tif_path = os.path.join(work_dir, f"{base_name}.tif")
    filter_csv_path = os.path.join(work_dir, f"{base_name}.csv")

    meta = LST.meta.copy()
    meta.update(dtype=rasterio.float32, count=len(filtered_rasters))

    with rasterio.open(filter_tif_path, "w", **meta) as dst:
        for idx, (key, data) in enumerate(filtered_rasters.items(), start=1):
            dst.write(data, idx)

    # Upload TIF
    tif_key = f"ECO/{name}/{location}/{base_name}.tif"
    upload_to_r2(s3_client, bucket_name, tif_key, filter_tif_path, "image/tiff")

    # CSV (keep for archive downloads)
    df.dropna(subset=["LST_filter"], inplace=True)
    df.to_csv(filter_csv_path, index=False)
    csv_key = f"ECO/{name}/{location}/{base_name}.csv"
    upload_to_r2(s3_client, bucket_name, csv_key, filter_csv_path, "text/csv")

    # PNGs for all scales
    png_r2_keys = {}
    for scale in ["relative", "fixed", "gray"]:
        try:
            png_bytes = tif_to_png(filter_tif_path, color_scale=scale)
            png_path = os.path.join(work_dir, f"{base_name}_{scale}.png")
            with open(png_path, "wb") as f:
                f.write(png_bytes.getvalue())
            png_key = f"ECO/{name}/{location}/{base_name}_{scale}.png"
            upload_to_r2(s3_client, bucket_name, png_key, png_path, "image/png")
            png_r2_keys[scale] = png_key
        except Exception as e:
            print(f"PNG generation failed for {scale}: {e}")

    # Ensure at least one PNG was generated successfully
    if not png_r2_keys:
        raise Exception("Failed to generate any PNG visualizations - all scales failed")

    # Metadata JSON
    hist = filter_stats["histogram"]
    valid_pixels = hist.get("0", 0)
    land_pixels = (
        sum(hist.get(str(i), 0) for i in range(16) if i & 4) if water_mask_flag else 0
    )

    metadata = {
        "date": date,
        "min_temp": float(df["LST_filter"].min())
        if not df["LST_filter"].empty
        else None,
        "max_temp": float(df["LST_filter"].max())
        if not df["LST_filter"].empty
        else None,
        "data_points": int(len(df)),
        "water_pixel_count": valid_pixels,
        "land_pixel_count": land_pixels,
        "wtoff": bool(suffix),
        "filter_stats": filter_stats,
    }
    metadata_path = os.path.join(work_dir, f"{base_name}_metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)
    meta_key = f"ECO/{name}/{location}/metadata/{base_name}_metadata.json"
    upload_to_r2(s3_client, bucket_name, meta_key, metadata_path, "application/json")

    # Insert metadata into D1 with actual R2 paths
    feature_id = f"{name}/{location}" if location != "lake" else name
    insert_metadata_to_d1(feature_id, date, metadata, csv_key, tif_key, png_r2_keys)

    # Update index (keep for backward compatibility during transition)
    index_key = f"ECO/{name}/{location}/index.json"
    try:
        existing = s3_client.get_object(Bucket=bucket_name, Key=index_key)
        index_json = json.loads(existing["Body"].read().decode("utf-8"))
    except Exception:
        index_json = {"dates": [], "latest_date": None}
    if date not in index_json.get("dates", []):
        index_json["dates"].append(date)
    index_json["dates"] = sorted(index_json["dates"], reverse=True)
    index_json["latest_date"] = (
        max(index_json["dates"]) if index_json["dates"] else date
    )
    s3_client.put_object(
        Bucket=bucket_name,
        Key=index_key,
        Body=json.dumps(index_json),
        ContentType="application/json",
    )


def _process_record(record, token, session, aid_folder_mapping, s3_client, bucket_name):
    """Process a single SQS record. Returns (message_id, success) tuple."""
    import time
    import shutil
    import traceback

    message_id = record["messageId"]
    body = json.loads(record["body"])
    task_id = body.get("task_id")

    if not task_id:
        print(f"[UNKNOWN] Skipping message {message_id}: no task_id in body")
        return message_id, True  # Don't retry malformed messages

    print(f"[{task_id}] Processing SQS message {message_id}")

    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}"

    work_dir = f"/tmp/{task_id}_{message_id}"
    os.makedirs(work_dir, exist_ok=True)

    files_to_process = body.get("files", [])
    if not files_to_process:
        print(f"[{task_id}] ERROR: No files provided in SQS message body")
        return message_id, True  # Don't retry empty messages

    print(f"[{task_id}] Downloading {len(files_to_process)} file(s)")

    try:
        downloaded_files = []

        with xray_recorder.capture("download_files") as subsegment:
            subsegment.put_metadata("task_id", task_id)
            subsegment.put_metadata("file_count", len(files_to_process))

            for file_info in files_to_process:
                file_id = file_info["file_id"]
                filename = file_info["file_name"]
                local_path = os.path.join(work_dir, filename)

                d_url = f"{url}/{file_id}"
                print(f"[{task_id}] Downloading: {filename}")
                r = session.get(d_url, headers=headers, stream=True)
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                downloaded_files.append(local_path)

            print(f"[{task_id}] Downloaded {len(downloaded_files)} file(s) successfully")

        # Group by AID and Date (should be just one group, but keeping logic safe)
        files_by_aid_date = {}
        for f in downloaded_files:
            aid, date = extract_metadata(f)
            if aid and date:
                key = (aid, date)
                if key not in files_by_aid_date:
                    files_by_aid_date[key] = []
                files_by_aid_date[key].append(f)
            else:
                print(f"[{task_id}] WARNING: Could not extract AID/date from {os.path.basename(f)}")

        print(f"[{task_id}] Grouped files into {len(files_by_aid_date)} AID/date combination(s)")

        for (aid, date), files in files_by_aid_date.items():
            start_time = time.time()

            name, location = aid_folder_mapping.get(aid, (f"aid{aid}", "lake"))
            feature_id = f"{name}/{location}" if location != "lake" else name

            print(f"[{task_id}][{feature_id}] Starting processing for date {date} with {len(files)} file(s)")

            log_job_to_d1(
                job_type="process",
                task_id=task_id,
                feature_id=feature_id,
                date=date,
                status="started",
                fatal=False,
            )

            with xray_recorder.capture("process_feature") as subsegment:
                subsegment.put_metadata("task_id", task_id)
                subsegment.put_metadata("feature_id", feature_id)
                subsegment.put_metadata("date", date)
                subsegment.put_metadata("file_count", len(files))

                try:
                    process_rasters(
                        aid, date, files, aid_folder_mapping,
                        work_dir, s3_client, bucket_name,
                    )

                    duration_ms = int((time.time() - start_time) * 1000)
                    log_job_to_d1(
                        job_type="process",
                        task_id=task_id,
                        feature_id=feature_id,
                        date=date,
                        status="success",
                        duration_ms=duration_ms,
                    )
                    print(f"[{task_id}][{feature_id}] ✓ Processed successfully in {duration_ms}ms")

                except ValueError as e:
                    # Permanent failure (missing layers, no files) - don't retry
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_msg = str(e)
                    log_job_to_d1(
                        job_type="process",
                        task_id=task_id,
                        feature_id=feature_id,
                        date=date,
                        status="failed",
                        duration_ms=duration_ms,
                        error_message=error_msg,
                    )
                    print(f"[{task_id}][{feature_id}] ✗ Permanent failure (skipping): {error_msg}")
                    subsegment.put_annotation("error", True)
                    subsegment.put_annotation("permanent_failure", True)
                    subsegment.put_metadata("error_message", error_msg)

                except Exception as e:
                    # Transient failure - report as failed for SQS retry
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_msg = str(e)
                    log_job_to_d1(
                        job_type="process",
                        task_id=task_id,
                        feature_id=feature_id,
                        date=date,
                        status="failed",
                        duration_ms=duration_ms,
                        error_message=error_msg,
                    )
                    print(f"[{task_id}][{feature_id}] ✗ Transient failure (will retry): {error_msg}")
                    print(f"[{task_id}][{feature_id}] Traceback: {traceback.format_exc()}")
                    subsegment.put_annotation("error", True)
                    subsegment.put_metadata("error_message", error_msg)
                    return message_id, False  # Signal failure for batch item reporting

        return message_id, True

    except Exception as e:
        print(f"[{task_id}] ✗ Record-level failure: {e}")
        print(f"[{task_id}] Traceback: {traceback.format_exc()}")
        return message_id, False

    finally:
        # Cleanup work directory
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
            print(f"[{task_id}] Cleaned up work directory")


def handler(event, context):
    import time

    records = event["Records"]
    print(f"Received {len(records)} SQS message(s)")

    # Shared resources across all records in this batch
    user = os.environ.get("APPEEARS_USER")
    password = os.environ.get("APPEEARS_PASS")
    bucket_name = os.environ.get("R2_BUCKET_NAME", "multitifs")

    token = get_token(user, password)
    session = create_http_session()
    aid_folder_mapping = _get_aid_folder_mapping()
    s3_client = _get_s3_client()

    # Process each record, tracking failures for partial batch reporting
    failed_message_ids = []

    for record in records:
        message_id, success = _process_record(
            record, token, session, aid_folder_mapping, s3_client, bucket_name,
        )
        if not success:
            failed_message_ids.append(message_id)

    if failed_message_ids:
        print(f"Batch complete: {len(failed_message_ids)}/{len(records)} failed, will be retried")
    else:
        print(f"Batch complete: all {len(records)} message(s) processed successfully")

    # Return partial batch failure response (requires ReportBatchItemFailures on the event source)
    return {
        "batchItemFailures": [
            {"itemIdentifier": mid} for mid in failed_message_ids
        ]
    }
