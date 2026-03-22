import json
import os
import time
import boto3
from d1 import log_job_to_d1, update_data_request_scenes
from shared import get_token, create_http_session, extract_metadata


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

    # Log manifest job start — fatal=False so we still attempt the actual work
    log_job_to_d1(job_type="manifest", task_id=task_id, status="started", fatal=False)

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
        update_data_request_scenes(task_id=task_id, scenes_count=len(scenes))

        # Send to SQS
        for key, file_list in scenes.items():
            message_body = {"task_id": task_id, "scene_id": key, "files": file_list}

            sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(message_body))

        duration_ms = int((time.time() - start_time) * 1000)
        metadata = json.dumps({"scenes_count": len(scenes), "files_count": len(files)})
        log_job_to_d1(
            job_type="manifest",
            task_id=task_id,
            status="success",
            duration_ms=duration_ms,
            metadata_json=metadata,
        )
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
        log_job_to_d1(
            job_type="manifest",
            task_id=task_id,
            status="failed",
            duration_ms=duration_ms,
            error_message=str(e),
        )
        print(f"✗ Error processing manifest for {task_id}: {e} (took {duration_ms}ms)")
        raise
