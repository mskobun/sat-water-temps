import json
import os
import re
import requests
import boto3
import rasterio
import numpy as np
import pandas as pd
import geopandas as gpd
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from supabase import create_client, Client

# Constants
INVALID_QC_VALUES = {15, 2501, 3525, 65535}
HTTP_CONNECT_TIMEOUT = 10
HTTP_READ_TIMEOUT = 120
DOWNLOAD_CHUNK_SIZE = 64 * 1024

def create_http_session():
    retries = Retry(
        total=3, read=3, connect=3, backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"]
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

def upload_to_supabase(bucket_name, supabase_url, supabase_key, file_path, name, location):
    supabase: Client = create_client(supabase_url, supabase_key)
    supabase_dir = f"ECO/{name}/{location}"
    supabase_path = f"{supabase_dir}/{os.path.basename(file_path)}"
    
    # Simplified upload logic (skipping directory checks for brevity, Supabase handles it usually)
    with open(file_path, "rb") as file:
        supabase.storage.from_(bucket_name).upload(
            supabase_path, file, file_options={"upsert": "true"}
        )
    print(f"Uploaded {file_path} to Supabase")

def process_rasters(aid_number, date, selected_files, aid_folder_mapping, work_dir, supabase_url, supabase_key, bucket_name):
    print(f"Processing date: {date} for aid: {aid_number}")
    relevant_files = []
    for f in selected_files:
        aid, f_date = extract_metadata(f)
        if aid == aid_number and date == f_date:
            relevant_files.append(f)
            
    if not relevant_files:
        return

    # Read raster layers
    LST = read_raster("LST_doy", relevant_files)
    LST_err = read_raster("LST_err", relevant_files)
    QC = read_raster("QC", relevant_files)
    wt = read_raster("water", relevant_files)
    cl = read_raster("cloud", relevant_files)
    EmisWB = read_raster("EmisWB", relevant_files)
    heig = read_raster("height", relevant_files)

    if None in [LST, LST_err, QC, wt, cl, EmisWB, heig]:
        print(f"Skipping {date} due to missing layers.")
        return

    arrays = {
        "LST": read_array(LST), "LST_err": read_array(LST_err), "QC": read_array(QC),
        "wt": read_array(wt), "cloud": read_array(cl), "EmisWB": read_array(EmisWB),
        "height": read_array(heig)
    }

    name, location = aid_folder_mapping.get(aid_number, (None, None))
    if not name: return

    # Processing logic (simplified adaptation from original)
    rows, cols = arrays["LST"].shape
    x, y = np.meshgrid(np.arange(cols), np.arange(rows))
    
    df = pd.DataFrame({
        "x": x.flatten(), "y": y.flatten(),
        **{key: arr.flatten() for key, arr in arrays.items()}
    })

    # Filter
    water_mask_flag = df["wt"].isin([1]).any()
    
    for col in ["LST", "LST_err", "QC", "EmisWB", "height"]:
        df[f"{col}_filter"] = np.where(df["QC"].isin(INVALID_QC_VALUES), np.nan, df[col])
        df[f"{col}_filter"] = np.where(df["cloud"] == 1, np.nan, df[f"{col}_filter"])
        
    suffix = ""
    if not water_mask_flag:
        for col in ["LST_filter", "LST_err_filter", "QC_filter", "EmisWB_filter", "height_filter"]:
            df[f"{col}"] = np.where(df["wt"] == 0, np.nan, df[col])
        suffix = "_wtoff"

    # Create filtered raster
    filtered_rasters = {
        "LST": df["LST_filter"].values.reshape(rows, cols).astype(np.float32),
        "LST_err": df["LST_err_filter"].values.reshape(rows, cols).astype(np.float32),
        "QC": df["QC_filter"].values.reshape(rows, cols).astype(np.float32),
        "EmisWB": df["EmisWB_filter"].values.reshape(rows, cols).astype(np.float32),
        "height": df["height_filter"].values.reshape(rows, cols).astype(np.float32),
    }
    
    filter_tif_path = os.path.join(work_dir, f"{name}_{location}_{date}_filter{suffix}.tif")
    filter_csv_path = os.path.join(work_dir, f"{name}_{location}_{date}_filter{suffix}.csv")
    
    meta = LST.meta.copy()
    meta.update(dtype=rasterio.float32, count=len(filtered_rasters))
    
    with rasterio.open(filter_tif_path, "w", **meta) as dst:
        for idx, (key, data) in enumerate(filtered_rasters.items(), start=1):
            dst.write(data, idx)
        
    # Upload
    upload_to_supabase(bucket_name, supabase_url, supabase_key, filter_tif_path, name, location)
    
    # CSV
    df.dropna(subset=["LST_filter"], inplace=True)
    df.to_csv(filter_csv_path, index=False)
    upload_to_supabase(bucket_name, supabase_url, supabase_key, filter_csv_path, name, location)


def handler(event, context):
    # SQS event structure
    for record in event['Records']:
        body = json.loads(record['body'])
        task_id = body.get('task_id')
        
        if not task_id: continue
        
        user = os.environ.get("APPEEARS_USER")
        password = os.environ.get("APPEEARS_PASS")
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY")
        bucket_name = os.environ.get("BUCKET_NAME", "multitifs")
        
        token = get_token(user, password)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Download
        # Download
        url = f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}"
        session = create_http_session()
        
        work_dir = f"/tmp/{task_id}"
        os.makedirs(work_dir, exist_ok=True)
        # Use provided files list
        files_to_process = body.get('files', [])
        if not files_to_process:
            print("No files provided in message")
            continue
            
        downloaded_files = []
        
        for file_info in files_to_process:
            file_id = file_info["file_id"]
            filename = file_info["file_name"]
            local_path = os.path.join(work_dir, filename)
            
            # Download file
            d_url = f"{url}/{file_id}"
            r = session.get(d_url, headers=headers, stream=True)
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    f.write(chunk)
            downloaded_files.append(local_path)
            
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
        
        for (aid, date), files in files_by_aid_date.items():
            try:
                process_rasters(aid, date, files, aid_folder_mapping, work_dir, supabase_url, supabase_key, bucket_name)
            except Exception as e:
                print(f"Error processing {aid} {date}: {e}")

        # Cleanup
        import shutil
        shutil.rmtree(work_dir)
        
    return {"statusCode": 200}
