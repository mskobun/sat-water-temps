import json
import os
import re
import requests
import boto3
import rasterio
import numpy as np
import pandas as pd
import geopandas as gpd
import io
import matplotlib.pyplot as plt
from PIL import Image
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import List, Dict
from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

# Patch all supported libraries for automatic X-Ray tracing
patch_all()

# Constants
INVALID_QC_VALUES = {15, 2501, 3525, 65535}
HTTP_CONNECT_TIMEOUT = 10
HTTP_READ_TIMEOUT = 120
DOWNLOAD_CHUNK_SIZE = 64 * 1024
GLOBAL_MIN = 273.15  # Kelvin
GLOBAL_MAX = 308.15  # Kelvin


def create_http_session():
    retries = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=retries)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_token(user, password):
    response = requests.post(
        "https://appeears.earthdatacloud.nasa.gov/api/login", auth=(user, password)
    )
    response.raise_for_status()
    return response.json()["token"]


def query_d1(sql: str, params: List = None) -> Dict:
    """Execute SQL query against D1 database via Cloudflare API"""
    d1_db_id = os.environ.get("D1_DATABASE_ID")
    cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

    if not all([d1_db_id, cf_account_id, cf_api_token]):
        print("Warning: D1 credentials not configured, skipping database insert")
        return {"success": False}

    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/d1/database/{d1_db_id}/query"
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "application/json",
    }
    payload = {"sql": sql}
    if params:
        payload["params"] = params

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        # D1 API returns result in a specific format
        # {"success": true, "result": [{"success": true, "meta": {...}, "results": [...]}]}
        return result
    except requests.exceptions.HTTPError as e:
        # Log the full error response for debugging
        try:
            error_details = e.response.json()
            print(f"D1 query error: {e}, Details: {error_details}")
        except:
            print(f"D1 query error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"D1 query error: {e}")
        return {"success": False, "error": str(e)}


def log_job_to_d1(
    job_type: str,
    feature_id: str = None,
    date: str = None,
    task_id: str = None,
    status: str = "started",
    duration_ms: int = None,
    error_message: str = None,
    metadata_json: str = None,
):
    """Log processing job to D1 database"""
    try:
        import time

        if status == "started":
            sql = """
            INSERT INTO processing_jobs 
            (job_type, task_id, feature_id, date, status, started_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                job_type,
                task_id,
                feature_id,
                date,
                status,
                int(time.time() * 1000),
                metadata_json,
            ]
            result = query_d1(sql, params)

            # D1 API returns the last_row_id in the meta object
            # Response format: {"success": true, "result": [{"meta": {"last_row_id": N}}]}
            if result.get("success") and result.get("result"):
                first_result = (
                    result["result"][0]
                    if isinstance(result["result"], list)
                    else result["result"]
                )
                if first_result and "meta" in first_result:
                    return first_result["meta"].get("last_row_id")
        else:
            # Update existing job
            sql = """
            UPDATE processing_jobs 
            SET status = ?, completed_at = ?, duration_ms = ?, error_message = ?
            WHERE feature_id = ? AND date = ? AND status = 'started'
            ORDER BY started_at DESC
            LIMIT 1
            """
            import time

            params = [
                status,
                int(time.time() * 1000),
                duration_ms,
                error_message,
                feature_id,
                date,
            ]
            result = query_d1(sql, params)
            if not result.get("success"):
                print(f"Warning: Failed to update job status: {result.get('error')}")
    except Exception as e:
        print(f"Warning: Failed to log job to D1: {e}")
        return None


def insert_metadata_to_d1(
    feature_id: str,
    date: str,
    metadata: Dict,
    csv_r2_key: str,
    tif_r2_key: str,
    png_r2_keys: Dict[str, str],
):
    """Insert only metadata into D1 (temperature data stays in R2)"""
    try:
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

        with xray_recorder.capture('d1_insert_feature') as subsegment:
            subsegment.put_metadata('feature_id', feature_id)
            feature_result = query_d1(feature_sql, feature_params)
            if not feature_result.get("success"):
                subsegment.put_annotation('error', True)
                raise Exception(f"Failed to insert feature record: {feature_result.get('error')}")

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
        with xray_recorder.capture('d1_insert_temperature_metadata') as subsegment:
            subsegment.put_metadata('feature_id', feature_id)
            subsegment.put_metadata('date', date)
            subsegment.put_metadata('has_filter_stats', bool(filter_stats_json and filter_stats_json != '{}'))
            meta_result = query_d1(meta_sql, meta_params)
            if not meta_result.get("success"):
                subsegment.put_annotation('error', True)
                raise Exception(f"Failed to insert temperature metadata: {meta_result.get('error')}")

        print(f"✓ Inserted metadata to D1 with R2 paths")

    except Exception as e:
        print(f"Error inserting to D1: {e}")
        raise  # Re-raise to fail the job properly


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


def extract_metadata(filename):
    aid_match = re.search(r"aid(\d{4})", filename)
    date_match = re.search(r"doy(\d{13})", filename)
    aid_number = int(aid_match.group(1)) if aid_match else None
    date = date_match.group(1) if date_match else None
    return aid_number, date


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


def compute_filter_stats(filter_flags, total_pixels):
    """Compute filter statistics as bit flag histogram"""
    # Create histogram of bit flag values (0-7)
    histogram = {}
    for flag_value in range(8):
        count = int(np.sum(filter_flags == flag_value))
        if count > 0:  # Only store non-zero counts
            histogram[str(flag_value)] = count

    return {
        "total_pixels": int(total_pixels),
        "histogram": histogram
    }


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

    print(f"  [{feature_id}] Filtering {len(selected_files)} file(s) for aid={aid_number} date={date}")
    relevant_files = []
    for f in selected_files:
        aid, f_date = extract_metadata(f)
        if aid == aid_number and date == f_date:
            relevant_files.append(f)

    if not relevant_files:
        error_msg = f"No relevant files found after filtering for aid={aid_number} date={date}"
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
        print(f"  [{feature_id}] Available files: {[os.path.basename(f) for f in relevant_files]}")
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

    # Create filter tracking array (1 byte per pixel, 3 bits used)
    filter_flags = np.zeros(len(df), dtype=np.uint8)

    # Filter by QC and cloud first
    water_mask_flag = df["wt"].isin([1]).any()

    # QC filtering (bit 0)
    qc_mask = df["QC"].isin(INVALID_QC_VALUES)
    filter_flags = np.where(qc_mask, filter_flags | 1, filter_flags)

    for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        df[f"{col}_filter"] = np.where(qc_mask, np.nan, df[col])

    # Cloud filtering (bit 1)
    cloud_mask = df["cloud"] == 1
    filter_flags = np.where(cloud_mask, filter_flags | 2, filter_flags)

    for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        df[f"{col}_filter"] = np.where(cloud_mask, np.nan, df[f"{col}_filter"])

    suffix = ""
    if water_mask_flag:
        # Water detected - filter to keep only water pixels (bit 2)
        water_mask = df["wt"] == 0
        filter_flags = np.where(water_mask, filter_flags | 4, filter_flags)

        for col in [
            "LST_filter",
            "LST_err_filter",
            "QC_filter",
            "EmisWB_filter",
            "height_filter",
        ]:
            df[f"{col}"] = np.where(water_mask, np.nan, df[col])
    else:
        # No water detected - keep all data but flag as unreliable
        suffix = "_wtoff"

    # Compute filter statistics
    filter_stats = compute_filter_stats(filter_flags, len(df))

    # Log to CloudWatch (compute stats from histogram for display)
    hist = filter_stats["histogram"]
    total = filter_stats["total_pixels"]
    valid = hist.get("0", 0)
    filtered_qc = sum(hist.get(str(i), 0) for i in [1, 3, 5, 7])  # Bit 0 set
    filtered_cloud = sum(hist.get(str(i), 0) for i in [2, 3, 6, 7])  # Bit 1 set
    filtered_water = sum(hist.get(str(i), 0) for i in [4, 5, 6, 7])  # Bit 2 set

    print(f"Filter Statistics for {name}/{location} {date}:")
    print(f"  Total pixels: {total:,}")
    print(f"  Valid pixels: {valid:,} ({valid/total*100:.1f}%)")
    print(f"  Filtered: {total - valid:,} ({(total-valid)/total*100:.1f}%)")
    print(f"    - QC filtered: {filtered_qc:,} ({filtered_qc/total*100:.1f}%)")
    print(f"    - Cloud filtered: {filtered_cloud:,} ({filtered_cloud/total*100:.1f}%)")
    if water_mask_flag:
        print(f"    - Water mask filtered: {filtered_water:,} ({filtered_water/total*100:.1f}%)")

    # Create filtered raster
    filtered_rasters = {
        "LST": df["LST_filter"].values.reshape(rows, cols).astype(np.float32),
        "LST_err": df["LST_err_filter"].values.reshape(rows, cols).astype(np.float32),
        "QC": df["QC_filter"].values.reshape(rows, cols).astype(np.float32),
        "EmisWB": df["EmisWB_filter"].values.reshape(rows, cols).astype(np.float32),
        "height": df["height_filter"].values.reshape(rows, cols).astype(np.float32),
    }

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
    land_pixels = sum(hist.get(str(i), 0) for i in [4, 5, 6, 7]) if water_mask_flag else 0

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


def handler(event, context):
    # SQS event structure
    print(f"Received {len(event['Records'])} SQS message(s)")

    for record in event["Records"]:
        body = json.loads(record["body"])
        task_id = body.get("task_id")

        if not task_id:
            print(f"[UNKNOWN] Skipping message: no task_id in body")
            continue

        print(f"[{task_id}] Processing SQS message")

        user = os.environ.get("APPEEARS_USER")
        password = os.environ.get("APPEEARS_PASS")
        r2_endpoint = os.environ.get("R2_ENDPOINT")
        bucket_name = os.environ.get("R2_BUCKET_NAME", "multitifs")
        r2_key = os.environ.get("R2_ACCESS_KEY_ID")
        r2_secret = os.environ.get("R2_SECRET_ACCESS_KEY")

        token = get_token(user, password)
        headers = {"Authorization": f"Bearer {token}"}

        # Download
        url = f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}"
        session = create_http_session()

        work_dir = f"/tmp/{task_id}"
        os.makedirs(work_dir, exist_ok=True)
        # Use provided files list
        files_to_process = body.get("files", [])
        if not files_to_process:
            print(f"[{task_id}] ERROR: No files provided in SQS message body")
            continue

        print(f"[{task_id}] Downloading {len(files_to_process)} file(s)")

        downloaded_files = []

        with xray_recorder.capture('download_files') as subsegment:
            subsegment.put_metadata('task_id', task_id)
            subsegment.put_metadata('file_count', len(files_to_process))

            for file_info in files_to_process:
                file_id = file_info["file_id"]
                filename = file_info["file_name"]
                local_path = os.path.join(work_dir, filename)

                # Download file
                d_url = f"{url}/{file_id}"
                print(f"[{task_id}] Downloading: {filename}")
                r = session.get(d_url, headers=headers, stream=True)
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        f.write(chunk)
                downloaded_files.append(local_path)

            print(f"[{task_id}] Downloaded {len(downloaded_files)} file(s) successfully")

        # Process
        # Need ROI mapping
        roi_path = "static/polygons_new.geojson"
        roi = gpd.read_file(roi_path)
        aid_folder_mapping = {}
        for idx, row in roi.iterrows():
            aid_folder_mapping[int(idx + 1)] = (row["name"], row["location"])

        # Group by AID and Date (should be just one group now, but keeping logic safe)
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

        # R2 client
        s3_client = boto3.client(
            "s3",
            endpoint_url=r2_endpoint,
            aws_access_key_id=r2_key,
            aws_secret_access_key=r2_secret,
            region_name="auto",
        )

        for (aid, date), files in files_by_aid_date.items():
            import time

            start_time = time.time()

            # Get feature_id for logging
            name, location = aid_folder_mapping.get(aid, (f"aid{aid}", "lake"))
            feature_id = f"{name}/{location}" if location != "lake" else name

            print(f"[{task_id}][{feature_id}] Starting processing for date {date} with {len(files)} file(s)")

            # Log job start
            log_job_to_d1("process", feature_id, date, task_id, "started")

            with xray_recorder.capture('process_feature') as subsegment:
                subsegment.put_metadata('task_id', task_id)
                subsegment.put_metadata('feature_id', feature_id)
                subsegment.put_metadata('date', date)
                subsegment.put_metadata('file_count', len(files))

                try:
                    process_rasters(
                        aid,
                        date,
                        files,
                        aid_folder_mapping,
                        work_dir,
                        s3_client,
                        bucket_name,
                    )

                    # Log success
                    duration_ms = int((time.time() - start_time) * 1000)
                    log_job_to_d1(
                        "process", feature_id, date, task_id, "success", duration_ms
                    )
                    print(f"[{task_id}][{feature_id}] ✓ Processed successfully in {duration_ms}ms")

                except Exception as e:
                    # Log failure
                    duration_ms = int((time.time() - start_time) * 1000)
                    error_msg = str(e)
                    log_job_to_d1(
                        "process", feature_id, date, task_id, "failed", duration_ms, error_msg
                    )
                    print(f"[{task_id}][{feature_id}] ✗ Processing failed: {error_msg}")
                    import traceback
                    print(f"[{task_id}][{feature_id}] Traceback: {traceback.format_exc()}")

                    # Add error to X-Ray trace
                    subsegment.put_annotation('error', True)
                    subsegment.put_metadata('error_message', error_msg)
                    raise

        # Cleanup
        import shutil

        shutil.rmtree(work_dir)
        print(f"[{task_id}] Cleaned up work directory")

    print(f"Handler completed successfully")
    return {"statusCode": 200}
