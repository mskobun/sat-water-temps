import re
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
