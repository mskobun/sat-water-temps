import json
import os
import requests


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


def handler(event, context):
    user = os.environ.get("APPEEARS_USER")
    password = os.environ.get("APPEEARS_PASS")
    task_id = event.get("task_id")

    if not task_id:
        raise ValueError("Missing task_id")

    try:
        token = get_token(user, password)
        headers = {"Authorization": f"Bearer {token}"}

        url = f"https://appeears.earthdatacloud.nasa.gov/api/task/{task_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()

        status = response.json()["status"]

        print(f"Task {task_id} status: {status}")

        return {"task_id": task_id, "status": status}
    except Exception as e:
        print(f"✗ Error checking status for {task_id}: {e}")
        raise
