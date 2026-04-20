"""Open raster datasets from s3://, http(s)://, file://, or local filesystem paths.

Used by ECOSTRESS and Landsat processors for local testing and HTTP COG access.
"""

from __future__ import annotations

import os
import tempfile
import urllib.parse
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import boto3
import earthaccess
import rasterio
import requests
from rasterio.session import AWSSession


def _is_http_or_https(uri: str) -> bool:
    return uri.startswith(("http://", "https://"))


def _download_http_to_temp_tif(uri: str, get) -> rasterio.DatasetReader:
    """Stream ``uri`` to a temp file via ``get(uri, ...)`` and open with rasterio."""
    r = get(uri, timeout=600, stream=True)
    r.raise_for_status()
    fd, path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    try:
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        return rasterio.open(path)
    except Exception:
        if os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass
        raise


def open_raster_http_local_or_file(
    uri: str, session: Optional[requests.Session] = None
):
    """Return a rasterio dataset for a non-AWS-s3 URI (http(s), file://, local path).

    For HTTP(S) without ``session``, tries GDAL/vsi first; on failure downloads with
    plain ``requests``. For NASA EDL-protected HTTPS (e.g. LP DAAC), pass
    ``session=earthaccess.get_requests_https_session()`` after ``earthaccess.login()``.

    Caller must close the dataset.
    """
    if uri.startswith("file://"):
        return rasterio.open(uri[7:])
    if _is_http_or_https(uri):
        if session is not None:
            return _download_http_to_temp_tif(uri, session.get)
        try:
            return rasterio.open(uri)
        except Exception:
            return _download_http_to_temp_tif(uri, requests.get)
    return rasterio.open(uri)


@contextmanager
def landsat_rasterio_env(scenes: List[dict]):
    """Use requester-pays AWS session when any scene href is s3://."""
    need_aws = False
    for scene in scenes:
        hrefs = scene.get("hrefs") or {}
        for key in ("lwir11", "qa_pixel"):
            h = hrefs.get(key) or ""
            if h.startswith("s3://"):
                need_aws = True
                break
        if need_aws:
            break
    if not need_aws:
        yield
        return
    aws_session = AWSSession(boto3.Session(), requester_pays=True)
    with rasterio.Env(AWSSession=aws_session, AWS_REQUEST_PAYER="requester"):
        yield


def open_landsat_band(href: str):
    """Open one Landsat COG href (s3 with env already entered, or http/file path)."""
    if href.startswith("s3://"):
        return rasterio.open(href)
    return open_raster_http_local_or_file(href)


def _ecostress_bands_subset(hrefs: dict) -> Dict[str, str]:
    return {k: hrefs[k] for k in ("LST", "QC", "water", "cloud")}


def _all_uris_s3(uris: Dict[str, str]) -> bool:
    for u in uris.values():
        p = urllib.parse.urlparse(u)
        if p.scheme != "s3":
            return False
    return True


def open_ecostress_granule_rasters(hrefs: dict) -> Dict[str, Any]:
    """Open LST/QC/water/cloud rasters for one ECOSTRESS granule.

    - All s3://: one batched ``earthaccess.open`` call (Lambda-friendly).
    - Any http(s):// or local path: authenticated session download (EDL bearer token).

    Caller must close all returned datasets.
    """
    band_keys = ["LST", "QC", "water", "cloud"]
    uris = _ecostress_bands_subset(hrefs)

    earthaccess.login()

    if _all_uris_s3(uris):
        # in_region=True tells earthaccess to use direct S3 access (us-west-2).
        # Only needed for S3 paths — HTTP paths use EDL bearer auth instead.
        earthaccess.__store__.in_region = True
        file_objects = earthaccess.open(
            list(uris.values()),
            credentials_endpoint="https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials",
        )
        file_map = dict(zip(band_keys, file_objects))
        return {k: rasterio.open(file_map[k]) for k in band_keys}

    https_session = earthaccess.get_requests_https_session()
    out: Dict[str, rasterio.DatasetReader] = {}
    for k in band_keys:
        u = uris[k]
        if u.startswith("s3://"):
            earthaccess.__store__.in_region = True
            fo = earthaccess.open(
                [u],
                credentials_endpoint="https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials",
            )[0]
            out[k] = rasterio.open(fo)
        else:
            out[k] = open_raster_http_local_or_file(u, session=https_session)
    return out
