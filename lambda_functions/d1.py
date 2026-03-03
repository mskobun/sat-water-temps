import os
import time
import requests
from typing import Dict, List


class D1Error(Exception):
    """Raised when a D1 query fails and fatal=True."""
    pass


def query_d1(sql: str, params: List = None, fatal: bool = True) -> Dict:
    """Execute SQL query against D1 database via Cloudflare API.

    When fatal=True (default), raises D1Error on failure instead of
    returning {"success": False}. This lets SQS-triggered Lambdas
    fail loudly so the message gets retried.
    """
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
# ECOSTRESS request helpers
# ---------------------------------------------------------------------------

def log_ecostress_request(
    task_id, trigger_type, triggered_by, description, sd, ed,
    request_id=None, fatal=True,
):
    """Log an ECOSTRESS request.

    If request_id is provided (manual triggers), UPDATE the existing pending row.
    Otherwise (timer triggers), INSERT a new row.
    """
    if request_id:
        sql = """
        UPDATE ecostress_requests
        SET task_id = ?, updated_at = ?
        WHERE id = ?
        """
        params = [task_id, int(time.time() * 1000), request_id]
    else:
        sql = """
        INSERT INTO ecostress_requests
        (task_id, trigger_type, triggered_by, description, start_date, end_date, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = [task_id, trigger_type, triggered_by, description, sd, ed, int(time.time() * 1000)]
    query_d1(sql, params, fatal=fatal)


def update_ecostress_request_error(task_id, error_message=None, fatal=True):
    """Update an ECOSTRESS request error by task_id."""
    query_d1(
        "UPDATE ecostress_requests SET updated_at = ?, error_message = ? WHERE task_id = ?",
        [int(time.time() * 1000), error_message, task_id],
        fatal=fatal,
    )


def update_ecostress_request_by_id_error(request_id, error_message=None, fatal=True):
    """Update an ECOSTRESS request error by row id."""
    query_d1(
        "UPDATE ecostress_requests SET updated_at = ?, error_message = ? WHERE id = ?",
        [int(time.time() * 1000), error_message, request_id],
        fatal=fatal,
    )


def update_ecostress_request_scenes(task_id, scenes_count, fatal=True):
    """Update ecostress_requests with scene count."""
    query_d1(
        "UPDATE ecostress_requests SET scenes_count = ?, updated_at = ? WHERE task_id = ?",
        [scenes_count, int(time.time() * 1000), task_id],
        fatal=fatal,
    )


# ---------------------------------------------------------------------------
# Task poller helpers
# ---------------------------------------------------------------------------

def get_pending_task_ids(fatal=True):
    """Return list of task_ids that need polling."""
    result = query_d1(
        """
        SELECT task_id FROM ecostress_requests
        WHERE task_id IS NOT NULL
          AND scenes_count IS NULL
          AND dispatched_at IS NULL
          AND error_message IS NULL
        """,
        [],
        fatal=fatal,
    )
    if not result:
        return []
    try:
        rows = result["result"][0]["results"]
        return [row["task_id"] for row in rows]
    except (KeyError, IndexError):
        return []


def mark_dispatched(task_id, fatal=True):
    query_d1(
        "UPDATE ecostress_requests SET dispatched_at = ? WHERE task_id = ?",
        [int(time.time() * 1000), task_id],
        fatal=fatal,
    )


def mark_error(task_id, error_message, fatal=True):
    query_d1(
        "UPDATE ecostress_requests SET error_message = ?, updated_at = ? WHERE task_id = ?",
        [error_message, int(time.time() * 1000), task_id],
        fatal=fatal,
    )
    query_d1(
        "UPDATE processing_jobs SET status = 'failed', completed_at = ?, error_message = ? WHERE task_id = ? AND status = 'started'",
        [int(time.time() * 1000), error_message, task_id],
        fatal=fatal,
    )
