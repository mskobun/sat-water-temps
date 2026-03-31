"""ECOSTRESS initiator Lambda — queries CMR-STAC via earthaccess for
ECO_L2T_LSTE granules and sends processing messages to SQS.

Replaces the old AppEEARS submit/poll/manifest workflow with direct
CMR search + COG access.
"""

import json
import os
import time
from datetime import datetime, timedelta

import boto3
import earthaccess

from common.polygons import load_polygons
from d1 import log_job_to_d1, get_setting, log_data_request


SHORT_NAME = "ECO_L2T_LSTE"
VERSION = "002"

# Mapping from logical band name (used in SQS messages / processor) to the
# layer suffix in ECOSTRESS L2T LSTE v002 COG filenames.
# Filenames look like: ECOv002_L2T_LSTE_{orbit}_{scene}_{tile}_{datetime}_{build}_{iter}_{layer}.tif
BAND_FILE_SUFFIX = {
    "LST": "LST",
    "QC": "QC",
    "water": "water",
    "cloud": "cloud",
    "EmisWB": "EmisWB",
}
REQUIRED_BANDS = ["LST", "QC", "water", "cloud", "EmisWB"]
OPTIONAL_BANDS_SUFFIX = {
    "LST_err": "LST_err",
    "height": "height",
}


def _granule_datetime(granule) -> str:
    """Extract datetime string from an earthaccess DataGranule."""
    # earthaccess DataGranule has .date_range_dt returning (start, end) datetimes
    try:
        start_dt = granule["umm"]["TemporalExtent"]["RangeDateTime"]["BeginningDateTime"]
        return datetime.fromisoformat(start_dt.replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%S")
    except (KeyError, TypeError):
        # Fallback: use granule metadata
        try:
            tr = granule["umm"]["TemporalExtent"]["RangeDateTime"]
            return tr["BeginningDateTime"][:19]
        except Exception:
            return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")


def _granule_hrefs(granule) -> dict:
    """Extract S3 URIs for each band from a DataGranule.

    Matches the layer suffix at the end of the filename (before .tif).
    Returns dict keyed by logical band name (LST, QC, water, cloud, EmisWB, etc.).
    """
    hrefs = {}
    # Use direct S3 access — Lambda runs in us-west-2, same region as LPDAAC archive.
    # data_links(access="direct") should return s3:// URIs; if it falls back to https://
    # the processor will get a 403. Filter to s3:// only and warn if none come back.
    links = [l for l in granule.data_links(access="direct") if l.startswith("s3://")]
    if not links:
        # Fallback: no direct S3 links available for this granule
        print(f"  Warning: no s3:// links found for granule, skipping")
        return {}
    all_suffixes = {**BAND_FILE_SUFFIX, **OPTIONAL_BANDS_SUFFIX}
    for link in links:
        for band, suffix in all_suffixes.items():
            if link.endswith(f"_{suffix}.tif"):
                hrefs[band] = link
                break
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
    request_id = event.get("request_id")

    # Date range — default: look back 2 days for ECOSTRESS latency
    delay_days = int(get_setting("data_delay_days", default=2))
    end_date = datetime.utcnow() - timedelta(days=delay_days)
    start_date = end_date - timedelta(days=1)

    if "start_date" in event:
        sd = event["start_date"]
        ed = event.get("end_date", sd)
    else:
        sd = start_date.strftime("%Y-%m-%d")
        ed = end_date.strftime("%Y-%m-%d")

    if not description:
        description = f"{'Manual' if trigger_type == 'manual' else 'Daily'} ECOSTRESS scan for {sd}" + (
            f" to {ed}" if sd != ed else ""
        )

    print(f"ECOSTRESS initiator: searching {sd} to {ed}")

    # Authenticate with Earthdata and pre-fetch S3 credentials so that
    # data_links(access="direct") returns s3:// URIs rather than https:// fallbacks.
    auth = earthaccess.login()
    auth.get_s3_credentials(daac="LPDAAC")

    polygons = load_polygons()
    sqs = boto3.client("sqs")
    start_time = time.time()

    # Log job start
    log_job_to_d1(
        job_type="ecostress_submit",
        status="started",
        metadata_json=json.dumps({"start_date": sd, "end_date": ed}),
        fatal=False,
    )

    total_messages = 0

    try:
        for poly in polygons:
            # earthaccess expects bounding_box as (west, south, east, north)
            bbox = tuple(poly["bbox"])  # already (minx, miny, maxx, maxy)

            results = earthaccess.search_data(
                short_name=SHORT_NAME,
                version=VERSION,
                bounding_box=bbox,
                temporal=(f"{sd}T00:00:00", f"{ed}T23:59:59"),
            )

            if not results:
                continue

            # Group granules by date for this polygon
            granules_by_date = {}
            for granule in results:
                dt_str = _granule_datetime(granule)
                date_key = dt_str[:10]  # YYYY-MM-DD for grouping

                hrefs = _granule_hrefs(granule)
                # Check required bands are present
                missing = [b for b in REQUIRED_BANDS if b not in hrefs]
                if missing:
                    granule_id = getattr(granule, "concept_id", lambda: "unknown")
                    print(f"  Skipping granule: missing bands {missing}")
                    continue

                if date_key not in granules_by_date:
                    granules_by_date[date_key] = []
                granules_by_date[date_key].append({
                    "granule_id": granule.get("meta", {}).get("concept-id", ""),
                    "hrefs": hrefs,
                    "datetime": dt_str,
                })

            # Send one SQS message per (AID, date)
            for date_key, granules in granules_by_date.items():
                # Use earliest granule datetime
                granule_datetime = min(g["datetime"] for g in granules)
                message_body = {
                    "source": "ecostress",
                    "aid": poly["aid"],
                    "date": granule_datetime,
                    "name": poly["name"],
                    "location": poly["location"],
                    "granules": granules,
                }
                sqs.send_message(
                    QueueUrl=sqs_queue_url,
                    MessageBody=json.dumps(message_body),
                )
                total_messages += 1
                print(f"  Queued: AID={poly['aid']} ({poly['name']}) date={date_key} ({len(granules)} granule(s))")

        duration_ms = int((time.time() - start_time) * 1000)

        log_job_to_d1(
            job_type="ecostress_submit",
            status="success",
            duration_ms=duration_ms,
        )
        log_data_request('ecostress', None, trigger_type, triggered_by, description, sd, ed,
                         request_id=request_id, scenes_count=total_messages)

        print(f"✓ ECOSTRESS initiator complete: {total_messages} messages sent in {duration_ms}ms")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "ECOSTRESS scan complete",
                "messages_sent": total_messages,
            }),
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        log_job_to_d1(
            job_type="ecostress_submit",
            status="failed",
            duration_ms=duration_ms,
            error_message=str(e),
        )
        log_data_request('ecostress', None, trigger_type, triggered_by, description, sd, ed,
                         request_id=request_id, error_message=str(e))
        print(f"✗ ECOSTRESS initiator error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
