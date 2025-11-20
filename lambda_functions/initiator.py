import json
import os
import boto3
import requests
from datetime import datetime, timedelta
import geopandas as gpd

# Initialize clients
sfn_client = boto3.client('stepfunctions')

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
        raise Exception(f"Task submission failed: {response.status_code} {response.text}")

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
    start_date = end_date - timedelta(days=1) # Just do 1 day for now or configurable
    # Or use the logic from original script:
    # start_date = end_date - timedelta(days=29)
    
    # For this implementation, let's stick to processing "yesterday" or a specific range from event
    if 'start_date' in event:
        sd = event['start_date']
        ed = event.get('end_date', sd)
    else:
        sd = start_date.strftime("%m-%d-%Y")
        ed = end_date.strftime("%m-%d-%Y")

    product = "ECO_L2T_LSTE.002"
    layers = ["LST", "LST_err", "QC", "water", "cloud", "EmisWB", "height"]

    task_request = build_task_request(product, layers, roi_json, sd, ed)
    
    try:
        task_id = submit_task(headers, task_request)
        print(f"Submitted task: {task_id}")
        
        # Start Step Function
        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            input=json.dumps({"task_id": task_id, "wait_seconds": 30})
        )
        
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Task submitted", "task_id": task_id})
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
