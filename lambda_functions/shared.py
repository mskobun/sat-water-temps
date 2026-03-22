import re
from datetime import datetime, timedelta

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def get_token(user, password):
    """Authenticate with AppEEARS and return a bearer token."""
    response = requests.post(
        "https://appeears.earthdatacloud.nasa.gov/api/login", auth=(user, password)
    )
    response.raise_for_status()
    return response.json()["token"]


def create_http_session():
    """Create a requests Session with retry logic."""
    retries = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(pool_connections=16, pool_maxsize=16, max_retries=retries)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def extract_metadata(filename):
    """Extract AID number and date from an ECOSTRESS filename."""
    aid_match = re.search(r"aid(\d{4})", filename)
    date_match = re.search(r"doy(\d{13})", filename)
    aid_number = int(aid_match.group(1)) if aid_match else None
    date = date_match.group(1) if date_match else None
    return aid_number, date


def to_sort_date(date_str):
    """Convert any date string to YYYY-MM-DD for chronological comparison.

    Handles both ECOSTRESS DOY format ("2024362041923") and Landsat ISO
    format ("2024-12-27").  The returned value is suitable for SQL string
    comparison (ORDER BY, >, <) across both satellite types.
    """
    if len(date_str) == 10 and date_str[4] == "-":
        return date_str
    year = int(date_str[:4])
    doy = int(date_str[4:7])
    d = datetime(year, 1, 1) + timedelta(days=doy - 1)
    return d.strftime("%Y-%m-%d")


def to_iso_datetime(date_str):
    """Convert any date string to ISO datetime YYYY-MM-DDTHH:MM:SS.

    ECOSTRESS DOY "2024362041923" -> "2024-12-27T04:19:23"
    Landsat ISO   "2024-12-27"    -> "2024-12-27T00:00:00"
    Already normalized            -> pass through
    """
    if len(date_str) == 19 and date_str[4] == "-" and "T" in date_str:
        return date_str
    if len(date_str) == 10 and date_str[4] == "-":
        return date_str + "T00:00:00"
    # DOY format: YYYYDDDhhmmss
    year = int(date_str[:4])
    doy = int(date_str[4:7])
    hh = date_str[7:9] if len(date_str) >= 9 else "00"
    mm = date_str[9:11] if len(date_str) >= 11 else "00"
    ss = date_str[11:13] if len(date_str) >= 13 else "00"
    d = datetime(year, 1, 1) + timedelta(days=doy - 1)
    return f"{d.strftime('%Y-%m-%d')}T{hh}:{mm}:{ss}"
