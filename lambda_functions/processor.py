"""SQS message router — dispatches to the appropriate processor based on message source.

This is the single Lambda handler that receives all SQS messages from the
processing queue and routes them to:
  - backfill.*       for backfill messages
  - landsat.processor for Landsat COG messages
  - ecostress.processor for ECOSTRESS COG messages
"""

import json
import os

from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core import patch_all

from common.exceptions import NoDataError

# Patch supported libraries for X-Ray tracing.
# Exclude aiobotocore — s3fs uses it for async S3 ops via earthaccess.open(),
# and patch_all() causes AlreadyEndedException when X-Ray tries to record
# subsegments after the parent segment has closed.
patch_all(ignore_module_patterns=["aiobotocore"])


def handler(event, context):
    import time

    records = event["Records"]
    print(f"Received {len(records)} SQS message(s)")

    # Process each record, tracking failures for partial batch reporting
    failed_message_ids = []

    for record in records:
        message_id = record["messageId"]
        body = json.loads(record["body"])

        # Route backfill messages to the backfill package
        if body.get("type", "").startswith("backfill:"):
            try:
                from backfill import dispatch
                dispatch(body)
                continue
            except Exception as e:
                import traceback
                print(f"[Backfill] ✗ Failed: {e}")
                print(f"[Backfill] Traceback: {traceback.format_exc()}")
                failed_message_ids.append(message_id)
                continue

        # Route Landsat messages to the Landsat processor
        if body.get("source") == "landsat":
            try:
                from landsat.processor import process_one_record as process_landsat
                process_landsat(body)
                continue
            except NoDataError:
                # Zero valid pixels — already logged as nodata by Landsat processor
                continue
            except Exception as e:
                import traceback
                print(f"[Landsat] ✗ Record-level failure: {e}")
                print(f"[Landsat] Traceback: {traceback.format_exc()}")
                failed_message_ids.append(message_id)
                continue

        # Route ECOSTRESS messages to the ECOSTRESS processor
        if body.get("source") == "ecostress":
            try:
                from ecostress.processor import process_one_record as process_ecostress
                process_ecostress(body)
                continue
            except NoDataError:
                # Zero valid pixels — already logged as nodata by ECOSTRESS processor
                continue
            except Exception as e:
                import traceback
                print(f"[ECOSTRESS] ✗ Record-level failure: {e}")
                print(f"[ECOSTRESS] Traceback: {traceback.format_exc()}")
                failed_message_ids.append(message_id)
                continue

        # Unknown message type
        print(f"[Router] Unknown message source, skipping: {body.get('source', body.get('type', 'unknown'))}")

    if failed_message_ids:
        print(f"Batch complete: {len(failed_message_ids)}/{len(records)} failed, will be retried")
    else:
        print(f"Batch complete: all {len(records)} message(s) processed successfully")

    # Return partial batch failure response (requires ReportBatchItemFailures on the event source)
    return {
        "batchItemFailures": [
            {"itemIdentifier": mid} for mid in failed_message_ids
        ]
    }
