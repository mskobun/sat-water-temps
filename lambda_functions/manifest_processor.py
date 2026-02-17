import json
import os
import re
import requests
import boto3
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


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


def extract_metadata(filename):
    aid_match = re.search(r"aid(\d{4})", filename)
    date_match = re.search(r"doy(\d{13})", filename)
    aid_number = int(aid_match.group(1)) if aid_match else None
    date = date_match.group(1) if date_match else None
    return aid_number, date


def update_ecostress_request(task_id, scenes_count):
    """Update ecostress_requests with scene count"""
    try:
        d1_db_id = os.environ.get("D1_DATABASE_ID")
        cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

        if not all([d1_db_id, cf_account_id, cf_api_token]):
            return

        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/d1/database/{d1_db_id}/query"
        headers = {
            "Authorization": f"Bearer {cf_api_token}",
            "Content-Type": "application/json",
        }

        sql = """
        UPDATE ecostress_requests
        SET scenes_count = ?, updated_at = ?
        WHERE task_id = ?
        """
        params = [scenes_count, int(time.time() * 1000), task_id]

        payload = {"sql": sql, "params": params}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"Warning: Failed to update ecostress_request in D1: {e}")


def handler(event, context):
    start_time = time.time()

    # Input: {"task_id": "..."}
    task_id = event.get("task_id")
    if not task_id:
        raise ValueError("task_id is required")

    user = os.environ.get("APPEEARS_USER")
    password = os.environ.get("APPEEARS_PASS")
    queue_url = os.environ.get("SQS_QUEUE_URL")

    sqs = boto3.client("sqs")

    try:
        # Authenticate
        token = get_token(user, password)
        headers = {"Authorization": f"Bearer {token}"}

        # Get Manifest
        url = f"https://appeears.earthdatacloud.nasa.gov/api/bundle/{task_id}"
        session = create_http_session()
        response = session.get(url, headers=headers)
        response.raise_for_status()
        manifest = response.json()

        files = manifest.get("files", [])
        print(f"Found {len(files)} files for task {task_id}")

        # Group by Scene (AID + Date)
        scenes = {}
        for file in files:
            filename = file["file_name"].split("/")[-1]
            aid, date = extract_metadata(filename)

            if aid and date:
                key = f"{aid}_{date}"
                if key not in scenes:
                    scenes[key] = []

                # Store minimal info needed for download
                scenes[key].append({"file_id": file["file_id"], "file_name": filename})

        print(f"Grouped into {len(scenes)} scenes")

        # Update ecostress_request with scene count
        update_ecostress_request(task_id, len(scenes))

        # Send to SQS
        for key, file_list in scenes.items():
            message_body = {"task_id": task_id, "scene_id": key, "files": file_list}

            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message_body))

        duration_ms = int((time.time() - start_time) * 1000)
        print(
            f"✓ Processed manifest for {task_id}: {len(scenes)} scenes, {len(files)} files in {duration_ms}ms"
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Manifest processed", "scenes_count": len(scenes)}
            ),
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        print(f"✗ Error processing manifest for {task_id}: {e} (took {duration_ms}ms)")
        raise
