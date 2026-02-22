import json
import os
import requests
from datetime import datetime, timedelta
import geopandas as gpd
import time
from d1 import query_d1


def log_job_to_d1(
    job_type: str,
    task_id: str = None,
    status: str = "started",
    duration_ms: int = None,
    error_message: str = None,
    metadata_json: str = None,
):
    """Log processing job to D1 database"""
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

    query_d1(sql, params)


def log_ecostress_request(task_id, trigger_type, triggered_by, description, sd, ed, request_id=None):
    """Log an ECOSTRESS request to the ecostress_requests table.
    If request_id is provided (manual triggers), UPDATE the existing pending row.
    Otherwise (timer triggers), INSERT a new row.
    """
    if request_id:
        sql = """
        UPDATE ecostress_requests
        SET task_id = ?, updated_at = ?
        WHERE id = ?
        """
        params = [task_id, int(time.time() * 1000), request_id]
    else:
        sql = """
        INSERT INTO ecostress_requests
        (task_id, trigger_type, triggered_by, description, start_date, end_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = [task_id, trigger_type, triggered_by, description, sd, ed, int(time.time() * 1000)]
    query_d1(sql, params)


def update_ecostress_request(task_id, error_message=None):
    """Update an ECOSTRESS request error by task_id"""
    sql = """
    UPDATE ecostress_requests
    SET updated_at = ?, error_message = ?
    WHERE task_id = ?
    """
    params = [int(time.time() * 1000), error_message, task_id]
    query_d1(sql, params)


def update_ecostress_request_by_id(request_id, error_message=None):
    """Update an ECOSTRESS request error by row id"""
    sql = """
    UPDATE ecostress_requests
    SET updated_at = ?, error_message = ?
    WHERE id = ?
    """
    params = [int(time.time() * 1000), error_message, request_id]
    query_d1(sql, params)


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

    # Path to ROI file - assumed to be in the task root in Docker
    roi_path = "static/polygons_new.geojson"

    if not user or not password:
        raise ValueError("Missing AppEEARS credentials")

    # Function URL invocations wrap the payload in event["body"]
    if "body" in event:
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        event = body

    # Trigger metadata: defaults to timer/cloudwatch, overridden by manual triggers
    trigger_type = event.get("trigger_type", "timer")
    triggered_by = event.get("triggered_by", "cloudwatch")
    description = event.get("description")
    request_id = event.get("request_id")  # Set by admin UI for manual triggers

    token = get_token(user, password)
    headers = {"Authorization": f"Bearer {token}"}

    # Load ROI
    roi = gpd.read_file(roi_path)
    roi_json = roi.__geo_interface__

    # Dates
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=1)  # Just do 1 day for now or configurable

    # Use dates from event if provided (manual triggers pass these)
    if "start_date" in event:
        sd = event["start_date"]
        ed = event.get("end_date", sd)
    else:
        sd = start_date.strftime("%m-%d-%Y")
        ed = end_date.strftime("%m-%d-%Y")

    if not description:
        description = f"{'Manual' if trigger_type == 'manual' else 'Daily'} processing for {sd}" + (
            f" to {ed}" if sd != ed else ""
        )

    product = "ECO_L2T_LSTE.002"
    layers = ["LST", "LST_err", "QC", "water", "cloud", "EmisWB", "height"]

    task_request = build_task_request(product, layers, roi_json, sd, ed)

    task_id = None
    start_time = time.time()

    try:
        task_id = submit_task(headers, task_request)
        print(f"Submitted task: {task_id}")

        # Log ECOSTRESS request
        log_ecostress_request(task_id, trigger_type, triggered_by, description, sd, ed, request_id=request_id)

        # Log job start
        metadata = json.dumps({"start_date": sd, "end_date": ed})
        log_job_to_d1("scrape", task_id, "started", metadata_json=metadata)

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
        duration_ms = int((time.time() - start_time) * 1000)
        if task_id:
            log_job_to_d1("scrape", task_id, "failed", duration_ms, str(e))
            update_ecostress_request(task_id, str(e))
        elif request_id:
            # Manual trigger failed before getting task_id - update existing row
            update_ecostress_request_by_id(request_id, str(e))
        else:
            # Timer trigger failed before getting task_id - create failed row
            log_ecostress_request(None, trigger_type, triggered_by, description, sd, ed)
        print(f"✗ Error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
