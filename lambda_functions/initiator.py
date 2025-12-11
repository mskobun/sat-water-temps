import json
import os
import boto3
import requests
from datetime import datetime, timedelta
import geopandas as gpd
import time

# Initialize clients
sfn_client = boto3.client("stepfunctions")


def log_job_to_d1(
    job_type: str,
    task_id: str = None,
    status: str = "started",
    duration_ms: int = None,
    error_message: str = None,
    metadata_json: str = None,
):
    """Log processing job to D1 database"""
    try:
        d1_db_id = os.environ.get("D1_DATABASE_ID")
        cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

        if not all([d1_db_id, cf_account_id, cf_api_token]):
            return None

        url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/d1/database/{d1_db_id}/query"
        headers = {
            "Authorization": f"Bearer {cf_api_token}",
            "Content-Type": "application/json",
        }

        if status == "started":
            sql = """
            INSERT INTO processing_jobs 
            (job_type, task_id, status, started_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            """
            params = [job_type, task_id, status, int(time.time() * 1000), metadata_json]
        else:
            sql = """
            UPDATE processing_jobs 
            SET status = ?, completed_at = ?, duration_ms = ?, error_message = ?
            WHERE task_id = ? AND status = 'started'
            """
            params = [
                status,
                int(time.time() * 1000),
                duration_ms,
                error_message,
                task_id,
            ]

        payload = {"sql": sql, "params": params}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

    except Exception as e:
        print(f"Warning: Failed to log job to D1: {e}")


def get_token(user, password):
    try:
        response = requests.post(
            "https://appeears.earthdatacloud.nasa.gov/api/login", auth=(user, password)
        )
        response.raise_for_status()
        return response.json()["token"]
    except Exception as e:
        print(f"Authentication failed: {e}")
        raise


def build_task_request(product, layers, roi_json, sd, ed):
    task = {
        "task_type": "area",
        "task_name": "ECOStress_Request",
        "params": {
            "dates": [{"startDate": sd, "endDate": ed}],
            "layers": [{"product": product, "layer": layer} for layer in layers],
            "geo": roi_json,
            "output": {"format": {"type": "geotiff"}, "projection": "geographic"},
        },
    }
    return task


def submit_task(headers, task_request):
    url = "https://appeears.earthdatacloud.nasa.gov/api/task"
    response = requests.post(url, json=task_request, headers=headers)
    if response.status_code == 202:
        return response.json()["task_id"]
    else:
        raise Exception(
            f"Task submission failed: {response.status_code} {response.text}"
        )


def handler(event, context):
    user = os.environ.get("APPEEARS_USER")
    password = os.environ.get("APPEEARS_PASS")
    state_machine_arn = os.environ.get("STATE_MACHINE_ARN")

    # Path to ROI file - assumed to be in the task root in Docker
    roi_path = "static/polygons_new.geojson"

    if not user or not password:
        raise ValueError("Missing AppEEARS credentials")

    token = get_token(user, password)
    headers = {"Authorization": f"Bearer {token}"}

    # Load ROI
    roi = gpd.read_file(roi_path)
    roi_json = roi.__geo_interface__

    # Dates
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=1)  # Just do 1 day for now or configurable
    # Or use the logic from original script:
    # start_date = end_date - timedelta(days=29)

    # For this implementation, let's stick to processing "yesterday" or a specific range from event
    if "start_date" in event:
        sd = event["start_date"]
        ed = event.get("end_date", sd)
    else:
        sd = start_date.strftime("%m-%d-%Y")
        ed = end_date.strftime("%m-%d-%Y")

    product = "ECO_L2T_LSTE.002"
    layers = ["LST", "LST_err", "QC", "water", "cloud", "EmisWB", "height"]

    task_request = build_task_request(product, layers, roi_json, sd, ed)

    task_id = None
    start_time = time.time()

    try:
        task_id = submit_task(headers, task_request)
        print(f"Submitted task: {task_id}")

        # Log job start
        metadata = json.dumps({"start_date": sd, "end_date": ed})
        log_job_to_d1("scrape", task_id, "started", metadata_json=metadata)

        # Start Step Function
        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps({"task_id": task_id, "wait_seconds": 30}),
        )

        # Log success
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1("scrape", task_id, "success", duration_ms)
        print(f"✓ Initiated scrape job {task_id} in {duration_ms}ms")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Task submitted", "task_id": task_id}),
        }
    except Exception as e:
        # Log failure
        if task_id:
            duration_ms = int((time.time() - start_time) * 1000)
            log_job_to_d1("scrape", task_id, "failed", duration_ms, str(e))
        print(f"✗ Error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
