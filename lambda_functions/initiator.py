import json
import os
import requests
from datetime import datetime, timedelta
import time
from d1 import (
    get_setting,
    log_job_to_d1,
    log_data_request,
    update_data_request_error,
)
from shared import get_token


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
    with open(roi_path) as f:
        roi_json = json.load(f)

    # Dates — delay is configurable via admin settings (default 2 days for ECOSTRESS latency)
    delay_days = int(get_setting("data_delay_days", default=2))
    end_date = datetime.now() - timedelta(days=delay_days)
    start_date = end_date - timedelta(days=1)

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
        log_data_request('ecostress', task_id, trigger_type, triggered_by, description, sd, ed, request_id=request_id)

        # Log job start — fatal=False so we still attempt the actual work
        metadata = json.dumps({"start_date": sd, "end_date": ed})
        log_job_to_d1(job_type="submit", task_id=task_id, status="started", metadata_json=metadata, fatal=False)

        # Log success
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(job_type="submit", task_id=task_id, status="success", duration_ms=duration_ms)
        print(f"✓ Initiated submit job {task_id} in {duration_ms}ms")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Task submitted", "task_id": task_id}),
        }
    except Exception as e:
        # Log failure
        duration_ms = int((time.time() - start_time) * 1000)
        if task_id:
            log_job_to_d1(
                job_type="submit",
                task_id=task_id,
                status="failed",
                duration_ms=duration_ms,
                error_message=str(e),
            )
            update_data_request_error(task_id=task_id, error_message=str(e))
        elif request_id:
            # Manual trigger failed before getting task_id - update existing row
            update_data_request_error(request_id=request_id, error_message=str(e))
        else:
            # Timer trigger failed before getting task_id - create failed row
            log_data_request('ecostress', None, trigger_type, triggered_by, description, sd, ed)
        print(f"✗ Error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
