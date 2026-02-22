import json
import os
import time
import boto3
import requests


def _d1_query(sql, params):
    """Execute a D1 query via Cloudflare API. Returns None on failure."""
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

        payload = {"sql": sql, "params": params}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Warning: D1 query failed: {e}")
        return None


def get_pending_task_ids():
    """Return list of task_ids that need polling."""
    result = _d1_query(
        """
        SELECT task_id FROM ecostress_requests
        WHERE task_id IS NOT NULL
          AND scenes_count IS NULL
          AND dispatched_at IS NULL
          AND error_message IS NULL
        """,
        [],
    )
    if not result:
        return []
    try:
        rows = result["result"][0]["results"]
        return [row["task_id"] for row in rows]
    except (KeyError, IndexError):
        return []


def mark_dispatched(task_id):
    _d1_query(
        "UPDATE ecostress_requests SET dispatched_at = ? WHERE task_id = ?",
        [int(time.time() * 1000), task_id],
    )


def mark_error(task_id, error_message):
    _d1_query(
        "UPDATE ecostress_requests SET error_message = ?, updated_at = ? WHERE task_id = ?",
        [error_message, int(time.time() * 1000), task_id],
    )
    _d1_query(
        "UPDATE processing_jobs SET status = 'failed', completed_at = ?, error_message = ? WHERE task_id = ? AND status = 'started'",
        [int(time.time() * 1000), error_message, task_id],
    )


def get_token(user, password):
    response = requests.post(
        "https://appeears.earthdatacloud.nasa.gov/api/login", auth=(user, password)
    )
    response.raise_for_status()
    return response.json()["token"]


def get_all_task_statuses(token):
    """Fetch status of all tasks for this account. Returns dict of task_id -> status."""
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        "https://appeears.earthdatacloud.nasa.gov/api/task",
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    tasks = response.json()
    return {t["task_id"]: t["status"] for t in tasks}


def handler(event, context):
    user = os.environ.get("APPEEARS_USER")
    password = os.environ.get("APPEEARS_PASS")
    manifest_processor_arn = os.environ.get("MANIFEST_PROCESSOR_ARN")

    if not user or not password:
        raise ValueError("Missing AppEEARS credentials")

    pending_task_ids = get_pending_task_ids()
    if not pending_task_ids:
        print("No pending tasks — exiting early.")
        return {"statusCode": 200, "body": json.dumps({"message": "No pending tasks"})}

    print(f"Found {len(pending_task_ids)} pending task(s): {pending_task_ids}")

    token = get_token(user, password)
    all_statuses = get_all_task_statuses(token)

    lambda_client = boto3.client("lambda")

    for task_id in pending_task_ids:
        status = all_statuses.get(task_id)
        if status is None:
            print(f"Task {task_id} not found in AppEEARS — skipping.")
            continue

        print(f"Task {task_id} status: {status}")

        if status == "done":
            mark_dispatched(task_id)
            lambda_client.invoke(
                FunctionName=manifest_processor_arn,
                InvocationType="Event",
                Payload=json.dumps({"task_id": task_id}).encode(),
            )
            print(f"✓ Dispatched manifest_processor for task {task_id}")

        elif status == "error":
            error_msg = f"AppEEARS task {task_id} reported error status"
            mark_error(task_id, error_msg)
            print(f"✗ Task {task_id} failed in AppEEARS")

    return {"statusCode": 200, "body": json.dumps({"message": "Poll complete"})}
