import os
import time
import requests
from typing import Dict, List

from common.dates import to_iso_datetime


class D1Error(Exception):
    """Raised when a D1 query fails and fatal=True."""
    pass


def query_d1(sql: str, params: List = None, fatal: bool = True) -> Dict:
    """Execute SQL query against D1 database via Cloudflare API.

    When fatal=True (default), raises D1Error on failure instead of
    returning {"success": False}. This lets SQS-triggered Lambdas
    fail loudly so the message gets retried.

    When ``PROCESSOR_RUNTIME=local``, runs ``wrangler d1 execute --local`` instead
    (see :mod:`common.local_wrangler`).
    """
    if os.environ.get("PROCESSOR_RUNTIME", "cloud").lower() == "local":
        from common.local_wrangler import query_d1_via_wrangler

        return query_d1_via_wrangler(sql, params, fatal=fatal)

    d1_db_id = os.environ.get("D1_DATABASE_ID")
    cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

    if not all([d1_db_id, cf_account_id, cf_api_token]):
        msg = "D1 credentials not configured"
        if fatal:
            raise D1Error(msg)
        print(f"Warning: {msg}, skipping query")
        return {"success": False}

    url = f"https://api.cloudflare.com/client/v4/accounts/{cf_account_id}/d1/database/{d1_db_id}/query"
    headers = {
        "Authorization": f"Bearer {cf_api_token}",
        "Content-Type": "application/json",
    }
    payload = {"sql": sql}
    if params:
        payload["params"] = params

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        try:
            error_details = e.response.json()
            msg = f"D1 query error: {e}, Details: {error_details}"
        except Exception:
            msg = f"D1 query error: {e}"
        print(msg)
        if fatal:
            raise D1Error(msg) from e
        return {"success": False, "error": str(e)}
    except Exception as e:
        msg = f"D1 query error: {e}"
        print(msg)
        if fatal:
            raise D1Error(msg) from e
        return {"success": False, "error": str(e)}


def get_setting(key: str, default=None):
    """Fetch a single value from the app_settings table."""
    result = query_d1("SELECT value FROM app_settings WHERE key = ?", [key])
    try:
        rows = result.get("result", [{}])[0].get("results", [])
        if rows:
            return rows[0]["value"]
    except (IndexError, KeyError, TypeError):
        pass
    return default


# ---------------------------------------------------------------------------
# Unified job logging
# ---------------------------------------------------------------------------

def log_job_to_d1(
    job_type: str,
    task_id: str = None,
    feature_id: str = None,
    date: str = None,
    status: str = "started",
    duration_ms: int = None,
    error_message: str = None,
    metadata_json: str = None,
    fatal: bool = True,
):
    """Log a processing job to the processing_jobs table.

    INSERT when status="started", UPDATE otherwise.
    Returns last_row_id on INSERT success.
    """
    if date is not None:
        date = to_iso_datetime(date)
    try:
        if status == "started":
            sql = """
            INSERT INTO processing_jobs
            (job_type, task_id, feature_id, date, status, started_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            params = [
                job_type,
                task_id,
                feature_id,
                date,
                status,
                int(time.time() * 1000),
                metadata_json,
            ]
            result = query_d1(sql, params, fatal=fatal)

            if result.get("success") and result.get("result"):
                first_result = (
                    result["result"][0]
                    if isinstance(result["result"], list)
                    else result["result"]
                )
                if first_result and "meta" in first_result:
                    return first_result["meta"].get("last_row_id")
        else:
            # Build WHERE clause depending on what identifiers we have
            where_parts = ["job_type = ?", "status = 'started'"]
            where_params = [job_type]

            if task_id is not None:
                where_parts.append("task_id = ?")
                where_params.append(task_id)
            if feature_id is not None:
                where_parts.append("feature_id = ?")
                where_params.append(feature_id)
            if date is not None:
                where_parts.append("date = ?")
                where_params.append(date)

            where_clause = " AND ".join(where_parts)

            sql = f"""
            UPDATE processing_jobs
            SET status = ?, completed_at = ?, duration_ms = ?,
                error_message = ?, metadata = COALESCE(?, metadata)
            WHERE {where_clause}
            ORDER BY started_at DESC LIMIT 1
            """
            params = [
                status,
                int(time.time() * 1000),
                duration_ms,
                error_message,
                metadata_json,
            ] + where_params

            query_d1(sql, params, fatal=fatal)
    except D1Error:
        raise
    except Exception as e:
        if fatal:
            raise D1Error(f"Failed to log job to D1: {e}") from e
        print(f"Warning: Failed to log job to D1: {e}")
        return None


# ---------------------------------------------------------------------------
# Data request helpers (unified ecostress + landsat)
# ---------------------------------------------------------------------------

def log_data_request(
    source, task_id, trigger_type, triggered_by, description, sd, ed,
    request_id=None, scenes_count=None, error_message=None, fatal=True,
):
    """Log a data request (ECOSTRESS or Landsat).

    If request_id is provided (manual triggers), UPDATE the existing pending row.
    Otherwise (timer triggers), INSERT a new row.
    """
    now = int(time.time() * 1000)
    if request_id:
        sql = """
        UPDATE data_requests
        SET task_id = COALESCE(?, task_id),
            scenes_count = COALESCE(?, scenes_count),
            error_message = COALESCE(?, error_message),
            updated_at = ?
        WHERE id = ?
        """
        params = [task_id, scenes_count, error_message, now, request_id]
    else:
        sql = """
        INSERT INTO data_requests
        (source, task_id, trigger_type, triggered_by, description,
         start_date, end_date, scenes_count, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = [source, task_id, trigger_type, triggered_by, description,
                  sd, ed, scenes_count, error_message, now]
    query_d1(sql, params, fatal=fatal)


def update_data_request_error(task_id=None, request_id=None, error_message=None, fatal=True):
    """Update error on a data request, by task_id or row id."""
    now = int(time.time() * 1000)
    if task_id:
        query_d1(
            "UPDATE data_requests SET updated_at = ?, error_message = ? WHERE task_id = ?",
            [now, error_message, task_id],
            fatal=fatal,
        )
    elif request_id:
        query_d1(
            "UPDATE data_requests SET updated_at = ?, error_message = ? WHERE id = ?",
            [now, error_message, request_id],
            fatal=fatal,
        )


def update_data_request_scenes(task_id=None, request_id=None, scenes_count=None, fatal=True):
    """Update scenes count on a data request."""
    now = int(time.time() * 1000)
    if task_id:
        query_d1(
            "UPDATE data_requests SET scenes_count = ?, updated_at = ? WHERE task_id = ?",
            [scenes_count, now, task_id],
            fatal=fatal,
        )
    elif request_id:
        query_d1(
            "UPDATE data_requests SET scenes_count = ?, updated_at = ? WHERE id = ?",
            [scenes_count, now, request_id],
            fatal=fatal,
        )


