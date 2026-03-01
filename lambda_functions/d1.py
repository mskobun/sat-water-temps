import os
import requests
from typing import Dict, List


def query_d1(sql: str, params: List = None) -> Dict:
    """Execute SQL query against D1 database via Cloudflare API."""
    d1_db_id = os.environ.get("D1_DATABASE_ID")
    cf_account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    cf_api_token = os.environ.get("CLOUDFLARE_API_TOKEN")

    if not all([d1_db_id, cf_account_id, cf_api_token]):
        print("Warning: D1 credentials not configured, skipping query")
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
            print(f"D1 query error: {e}, Details: {error_details}")
        except Exception:
            print(f"D1 query error: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        print(f"D1 query error: {e}")
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
