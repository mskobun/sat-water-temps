import json
import os
import boto3
from d1 import get_pending_task_ids, mark_dispatched, mark_error
from shared import get_token


def get_all_task_statuses(token):
    """Fetch status of all tasks for this account. Returns dict of task_id -> status."""
    import requests

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
