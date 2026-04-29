"""OPERA DSWx-HLS water mask integration.

OPERA_L3_DSWX-HLS_V1: 30m per-pixel water classification derived from
Harmonized Landsat Sentinel-2 (HLS) surface reflectance.

B01_WTR classification values:
  0   = Not Water
  1   = Open Water
  2   = Partial Surface Water
  252 = Snow/Ice
  253 = Cloud/Cloud Shadow
  254 = Ocean Masked
  255 = Fill

fetch_opera_water_mask() returns a boolean water mask (True = water pixel)
reprojected to match the target LST raster grid. Returns None on any failure
or when no OPERA granule is found, allowing callers to fall back to
sensor-native masks.

Whether to use OPERA is controlled by processing_settings["water_mask"] in
the SQS message body (set by the Landsat initiator from D1 app_settings or
an explicit per-run override in the Lambda event payload).
"""

from __future__ import annotations

import os
from typing import Optional

import earthaccess
import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling


OPERA_SHORT_NAME = "OPERA_L3_DSWX-HLS_V1"

# B01_WTR values that represent surface water
WATER_VALUES = {1, 2}  # Open Water, Partial Surface Water


def search_opera_dswx(bbox: tuple, date: str, tolerance_days: int = 0) -> list:
    """Search NASA CMR for OPERA DSWx-HLS granules matching bbox and date.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) in WGS84
        date: YYYY-MM-DD
        tolerance_days: expand temporal window by this many days on each side

    Returns:
        List of earthaccess DataGranule objects, may be empty.
    """
    from datetime import date as date_cls, timedelta

    d = date_cls.fromisoformat(date)
    start = (d - timedelta(days=tolerance_days)).isoformat()
    end = (d + timedelta(days=tolerance_days)).isoformat()

    min_lon, min_lat, max_lon, max_lat = bbox

    try:
        results = earthaccess.search_data(
            short_name=OPERA_SHORT_NAME,
            bounding_box=(min_lon, min_lat, max_lon, max_lat),
            temporal=(f"{start}T00:00:00Z", f"{end}T23:59:59Z"),
        )
        return list(results)
    except Exception as e:
        print(f"[OPERA] CMR search failed: {e}")
        return []


def _get_wtr_href(granule) -> Optional[str]:
    """Extract the B01_WTR band S3 URI from an OPERA DSWx granule.

    Prefers direct S3 access (s3://) over HTTPS — Lambda runs in us-west-2,
    the same region as podaac-ops-cumulus-protected, so S3 direct access avoids
    the PO.DAAC HTTP auth layer entirely.
    """
    try:
        links = granule.data_links(access="direct")
        for link in links:
            if "_B01_WTR.tif" in link:
                return link
        # Fallback: HTTPS external links
        for link in granule.data_links(access="external"):
            if "_B01_WTR.tif" in link:
                return link
    except Exception as e:
        print(f"[OPERA] Failed to get WTR href: {e}")
    return None


def opera_mask_to_water_bool(wtr_array: np.ndarray) -> np.ndarray:
    """Convert B01_WTR classification to a boolean water mask.

    Returns True for pixels classified as Open Water (1) or Partial Surface
    Water (2). Everything else (land, cloud, fill, ocean) is False.
    """
    return np.isin(wtr_array, list(WATER_VALUES))


def fetch_opera_water_mask(
    bbox: tuple,
    date: str,
    target_shape: tuple,
    target_transform: Affine,
    target_crs: CRS,
    tolerance_days: int = 0,
) -> Optional[np.ndarray]:
    """Fetch an OPERA DSWx-HLS water mask co-registered to a target raster grid.

    Searches CMR for OPERA DSWx-HLS granules matching the bbox and date, opens
    the B01_WTR band(s), merges if multiple tiles, reprojects to the target
    grid using nearest-neighbour resampling, and returns a boolean mask where
    True = water pixel.

    Returns None if:
    - No OPERA granule found for this date/location
    - Any network or raster I/O error occurs
    - earthaccess is not authenticated

    Callers should fall back to sensor-native water masks when None is returned.
    """
    earthaccess.login()

    granules = search_opera_dswx(bbox, date, tolerance_days=tolerance_days)
    if not granules:
        print(f"[OPERA] No granules found for bbox={bbox} date={date} ±{tolerance_days}d")
        return None

    # Log granule acquisition dates so temporal matching can be verified
    for g in granules:
        try:
            links = g.data_links(access="direct") or g.data_links(access="external")
            b01 = next((l for l in links if "B01_WTR" in l), None)
            # Filename contains acquisition datetime, e.g. _T51QUU_20260330T021623Z_
            if b01:
                import re as _re
                m = _re.search(r'_(\d{8}T\d{6}Z)_', b01)
                acq = m.group(1) if m else "?"
                print(f"[OPERA]   granule acq={acq} (target={date})")
        except Exception:
            pass
    print(f"[OPERA] Found {len(granules)} granule(s) for {date}")

    # Collect B01_WTR hrefs
    hrefs = []
    for g in granules:
        href = _get_wtr_href(g)
        if href:
            hrefs.append(href)

    if not hrefs:
        print("[OPERA] No B01_WTR links found in granules")
        return None

    try:
        # Open COGs via direct S3 access (Lambda runs in us-west-2, same region
        # as podaac-ops-cumulus-protected). in_region=True + PO.DAAC credentials
        # endpoint mirrors how ECOSTRESS opens LP DAAC COGs.
        earthaccess.__store__.in_region = True
        file_objs = earthaccess.open(
            hrefs,
            credentials_endpoint="https://archive.podaac.earthdata.nasa.gov/s3credentials",
        )
        datasets = []
        try:
            for fobj in file_objs:
                datasets.append(rasterio.open(fobj))

            # Merge multiple tiles if needed
            if len(datasets) == 1:
                src_ds = datasets[0]
                wtr_data = src_ds.read(1)
                src_transform = src_ds.transform
                src_crs = src_ds.crs
            else:
                merged, merged_transform = merge(datasets)
                wtr_data = merged[0]
                src_transform = merged_transform
                src_crs = datasets[0].crs

            # Reproject to target grid (nearest neighbour — categorical data)
            dst_array = np.zeros(target_shape, dtype=np.uint8)
            reproject(
                source=wtr_data,
                destination=dst_array,
                src_transform=src_transform,
                src_crs=src_crs,
                dst_transform=target_transform,
                dst_crs=target_crs,
                resampling=Resampling.nearest,
            )

            water_bool = opera_mask_to_water_bool(dst_array)
            n_water = int(np.sum(water_bool))
            print(f"[OPERA] Water mask ready: {n_water}/{water_bool.size} pixels classified as water")
            return water_bool

        finally:
            for ds in datasets:
                try:
                    ds.close()
                except Exception:
                    pass
            for fobj in file_objs:
                try:
                    fobj.close()
                except Exception:
                    pass

    except Exception as e:
        print(f"[OPERA] Failed to fetch/process water mask: {e}")
        return None
