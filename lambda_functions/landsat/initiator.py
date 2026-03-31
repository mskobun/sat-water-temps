"""Landsat initiator Lambda — queries USGS STAC for Landsat C2 L2 ST scenes
and sends processing messages to SQS for each (AID, date) match.

Triggered daily by CloudWatch. Simpler than ECOSTRESS: no AppEEARS task/poll cycle.
"""

import json
import os
import time
from datetime import datetime, timedelta

import boto3
from pystac_client import Client as STACClient
from shapely.geometry import shape, mapping

from common.polygons import load_polygons
from d1 import log_job_to_d1, get_setting, log_data_request


STAC_URL = "https://landsatlook.usgs.gov/stac-server"
COLLECTION = "landsat-c2l2-st"

# STAC asset key mapping:
#   lwir11   -> *_ST_B10.TIF (surface temperature)
#   qa       -> *_ST_QA.TIF  (temperature uncertainty)
#   qa_pixel -> *_QA_PIXEL.TIF (CFMask bit flags)
REQUIRED_ASSETS = ["lwir11", "qa", "qa_pixel"]


def _search_stac(start_date: str, end_date: str, bbox: list) -> list:
    """Search USGS STAC for Landsat C2 L2 ST scenes intersecting bbox."""
    catalog = STACClient.open(STAC_URL)
    search = catalog.search(
        collections=[COLLECTION],
        bbox=bbox,
        datetime=f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        max_items=100,
    )
    return list(search.items())


def _get_s3_hrefs(item) -> dict:
    """Extract S3 hrefs from STAC item assets (alternate.s3.href)."""
    hrefs = {}
    for key in REQUIRED_ASSETS:
        asset = item.assets.get(key)
        if not asset:
            continue
        # Try alternate S3 path first, fall back to direct href
        s3_href = None
        if hasattr(asset, "extra_fields"):
            alternate = asset.extra_fields.get("alternate", {})
            s3_href = alternate.get("s3", {}).get("href")
        if not s3_href:
            s3_href = asset.href
        hrefs[key] = s3_href
    return hrefs


def handler(event, context):
    sqs_queue_url = os.environ.get("SQS_QUEUE_URL")
    if not sqs_queue_url:
        raise ValueError("SQS_QUEUE_URL not configured")

    # Parse event (support Function URL wrapping)
    if "body" in event:
        body = event["body"]
        if isinstance(body, str):
            body = json.loads(body)
        event = body

    trigger_type = event.get("trigger_type", "timer")
    triggered_by = event.get("triggered_by", "cloudwatch")
    description = event.get("description")
    run_id = event.get("run_id")  # set by admin trigger API

    # Date range — default: look back 2 days for Landsat latency
    delay_days = int(get_setting("data_delay_days", default=2))
    end_date = datetime.utcnow() - timedelta(days=delay_days)
    start_date = end_date - timedelta(days=1)

    if "start_date" in event:
        sd = event["start_date"]  # YYYY-MM-DD format
        ed = event.get("end_date", sd)
    else:
        sd = start_date.strftime("%Y-%m-%d")
        ed = end_date.strftime("%Y-%m-%d")

    if not description:
        description = f"{'Manual' if trigger_type == 'manual' else 'Daily'} Landsat scan for {sd}" + (
            f" to {ed}" if sd != ed else ""
        )

    print(f"Landsat initiator: searching {sd} to {ed}")

    polygons = load_polygons()
    sqs = boto3.client("sqs")
    start_time = time.time()

    # Log job start
    log_job_to_d1(
        job_type="landsat_submit",
        status="started",
        metadata_json=json.dumps({"start_date": sd, "end_date": ed}),
        fatal=False,
    )

    total_messages = 0

    try:
        # For each polygon, query STAC and find matching scenes
        for poly in polygons:
            items = _search_stac(sd, ed, poly["bbox"])
            if not items:
                continue

            # Group scenes by date for this polygon
            scenes_by_date = {}
            for item in items:
                # Check spatial intersection
                item_geom = shape(item.geometry)
                if not item_geom.intersects(poly["geometry"]):
                    continue

                # Extract date (YYYY-MM-DD)
                scene_date = item.datetime.strftime("%Y-%m-%d")
                hrefs = _get_s3_hrefs(item)

                if len(hrefs) < len(REQUIRED_ASSETS):
                    print(f"  Skipping {item.id}: missing assets {set(REQUIRED_ASSETS) - set(hrefs.keys())}")
                    continue

                if scene_date not in scenes_by_date:
                    scenes_by_date[scene_date] = []
                scenes_by_date[scene_date].append({
                    "scene_id": item.id,
                    "hrefs": hrefs,
                    "cloud_cover": item.properties.get("eo:cloud_cover"),
                    "datetime": item.datetime.strftime("%Y-%m-%dT%H:%M:%S"),
                })

            # Send one SQS message per (AID, date)
            for scene_date, scenes in scenes_by_date.items():
                # Use earliest scene datetime for the record timestamp
                scene_datetime = min(s["datetime"] for s in scenes)
                message_body = {
                    "source": "landsat",
                    "aid": poly["aid"],
                    "date": scene_datetime,
                    "name": poly["name"],
                    "location": poly["location"],
                    "scenes": scenes,
                }
                sqs.send_message(
                    QueueUrl=sqs_queue_url,
                    MessageBody=json.dumps(message_body),
                )
                total_messages += 1
                print(f"  Queued: AID={poly['aid']} ({poly['name']}) date={scene_date} ({len(scenes)} scene(s))")

        duration_ms = int((time.time() - start_time) * 1000)

        # Log success
        log_job_to_d1(
            job_type="landsat_submit",
            status="success",
            duration_ms=duration_ms,
        )
        log_data_request('landsat', None, trigger_type, triggered_by, description, sd, ed,
                         request_id=run_id, scenes_count=total_messages)

        print(f"✓ Landsat initiator complete: {total_messages} messages sent in {duration_ms}ms")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Landsat scan complete",
                "messages_sent": total_messages,
            }),
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="landsat_submit",
            status="failed",
            duration_ms=duration_ms,
            error_message=str(e),
        )
        log_data_request('landsat', None, trigger_type, triggered_by, description, sd, ed,
                         request_id=run_id, error_message=str(e))
        print(f"✗ Landsat initiator error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
