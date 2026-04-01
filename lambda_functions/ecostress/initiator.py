"""ECOSTRESS initiator Lambda — queries CMR-STAC via earthaccess for
ECO_L2T_LSTE granules and sends processing messages to SQS.

Replaces the old AppEEARS submit/poll/manifest workflow with direct
CMR search + COG access.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Iterator, List, Optional

import boto3
import earthaccess

from common.polygons import load_polygons, filter_polygons_for_feature
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


def _granule_hrefs(granule, prefer_http: bool = False) -> dict:
    """Extract hrefs for each band from a DataGranule.

    Matches the layer suffix at the end of the filename (before .tif).
    When ``prefer_http`` is True, also considers ``access="external"`` links so
    HTTPS URLs are preferred over ``s3://`` when both are present.
    """
    hrefs: Dict[str, str] = {}
    seen = set()
    link_list: List[str] = []
    access_modes = ("external", "direct") if prefer_http else ("direct",)
    for access in access_modes:
        try:
            for link in granule.data_links(access=access):
                if link not in seen:
                    seen.add(link)
                    link_list.append(link)
        except Exception:
            continue
    all_suffixes = {**BAND_FILE_SUFFIX, **OPTIONAL_BANDS_SUFFIX}
    for link in link_list:
        for band, suffix in all_suffixes.items():
            if link.endswith(f"_{suffix}.tif"):
                prev = hrefs.get(band)
                # Prefer https over s3 when upgrading
                if prev is None:
                    hrefs[band] = link
                elif prefer_http and prev.startswith("s3://") and link.startswith("http"):
                    hrefs[band] = link
                break
    return hrefs



def iter_ecostress_processor_bodies(
    sd: str,
    ed: str,
    *,
    task_id: str,
    polygons: list,
    prefer_http_hrefs: bool = False,
) -> Iterator[Dict[str, Any]]:
    """Yield processor message bodies (same shape as SQS body) for date range and polygons."""
    earthaccess.login()

    for poly in polygons:
        bbox = tuple(poly["bbox"])
        results = earthaccess.search_data(
            short_name=SHORT_NAME,
            version=VERSION,
            bounding_box=bbox,
            temporal=(f"{sd}T00:00:00", f"{ed}T23:59:59"),
        )
        if not results:
            continue

        granules_by_date: Dict[str, list] = {}
        for granule in results:
            dt_str = _granule_datetime(granule)
            date_key = dt_str[:10]
            hrefs = _granule_hrefs(granule, prefer_http=prefer_http_hrefs)
            missing = [b for b in REQUIRED_BANDS if b not in hrefs]
            if missing:
                print(f"  Skipping granule: missing bands {missing}")
                continue
            granules_by_date.setdefault(date_key, []).append(
                {
                    "granule_id": granule.get("meta", {}).get("concept-id", ""),
                    "hrefs": hrefs,
                    "datetime": dt_str,
                }
            )

        for date_key, granules in granules_by_date.items():
            granule_datetime = min(g["datetime"] for g in granules)
            yield {
                "source": "ecostress",
                "aid": poly["aid"],
                "date": granule_datetime,
                "name": poly["name"],
                "location": poly["location"],
                "task_id": task_id,
                "granules": granules,
            }
            print(
                f"  Yield: AID={poly['aid']} ({poly['name']}) date={date_key} ({len(granules)} granule(s))"
            )


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

    # Use task_id from trigger endpoint if provided, otherwise generate one
    task_id = event.get("task_id") or f"eco-{request_id or int(time.time() * 1000)}"

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

    # Optional feature filter — accepts a name (str) or AID (int)
    feature_filter = event.get("feature")  # e.g. "Magat" or 1

    if not description:
        feature_label = f" [{feature_filter}]" if feature_filter else ""
        description = f"{'Manual' if trigger_type == 'manual' else 'Daily'} ECOSTRESS scan for {sd}" + (
            f" to {ed}" if sd != ed else ""
        ) + feature_label

    print(f"ECOSTRESS initiator: searching {sd} to {ed}" + (f" (feature={feature_filter})" if feature_filter else ""))

    polygons = load_polygons()
    polygons = filter_polygons_for_feature(polygons, feature_filter)
    if polygons is None:
        print(f"  No polygon found matching feature={feature_filter!r}")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": f"feature {feature_filter!r} not found"}),
        }

    prefer_http = bool(
        event.get("prefer_http_hrefs")
        or os.environ.get("ECOSTRESS_PREFER_HTTP_HREFS", "").lower() in ("1", "true", "yes")
    )
    sqs = boto3.client("sqs")
    start_time = time.time()

    # Log job start
    log_job_to_d1(
        job_type="ecostress_submit",
        task_id=task_id,
        status="started",
        metadata_json=json.dumps({"start_date": sd, "end_date": ed}),
        fatal=False,
    )

    total_messages = 0

    try:
        for message_body in iter_ecostress_processor_bodies(
            sd,
            ed,
            task_id=task_id,
            polygons=polygons,
            prefer_http_hrefs=prefer_http,
        ):
            sqs.send_message(
                QueueUrl=sqs_queue_url,
                MessageBody=json.dumps(message_body),
            )
            total_messages += 1
            print(
                f"  Queued: AID={message_body['aid']} ({message_body['name']}) date={message_body['date'][:10]}"
            )

        duration_ms = int((time.time() - start_time) * 1000)

        log_job_to_d1(
            job_type="ecostress_submit",
            task_id=task_id,
            status="success",
            duration_ms=duration_ms,
        )
        log_data_request('ecostress', task_id, trigger_type, triggered_by, description, sd, ed,
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
            task_id=task_id,
            status="failed",
            duration_ms=duration_ms,
            error_message=str(e),
        )
        log_data_request('ecostress', task_id, trigger_type, triggered_by, description, sd, ed,
                         request_id=request_id, error_message=str(e))
        print(f"✗ ECOSTRESS initiator error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
