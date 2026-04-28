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

When enabled (OPERA_WATER_MASK_ENABLED=1), fetch_opera_water_mask() returns
a boolean water mask (True = water pixel) reprojected to match the target LST
raster grid. Returns None on any failure or when no OPERA granule is found,
allowing callers to fall back to sensor-native masks.
"""

from __future__ import annotations

import os
import tempfile
from typing import Optional

import earthaccess
import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.merge import merge
from rasterio.warp import reproject, Resampling


OPERA_SHORT_NAME = "OPERA_L3_DSWX-HLS"
OPERA_VERSION = "1"

# B01_WTR values that represent surface water
WATER_VALUES = {1, 2}  # Open Water, Partial Surface Water


def is_opera_enabled() -> bool:
    """Return True if OPERA water mask is enabled via env var."""
    return os.environ.get("OPERA_WATER_MASK_ENABLED", "").strip() in ("1", "true", "yes")


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
            version=OPERA_VERSION,
            bounding_box=(min_lon, min_lat, max_lon, max_lat),
            temporal=(f"{start}T00:00:00Z", f"{end}T23:59:59Z"),
        )
        return list(results)
    except Exception as e:
        print(f"[OPERA] CMR search failed: {e}")
        return []


def _get_wtr_href(granule) -> Optional[str]:
    """Extract the B01_WTR band HTTPS link from an OPERA DSWx granule."""
    try:
        links = granule.data_links(access="external")
        for link in links:
            if "_B01_WTR.tif" in link:
                return link
        # Fallback: try all links
        for link in granule.data_links():
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
    try:
        earthaccess.login()
    except Exception as e:
        print(f"[OPERA] earthaccess login failed: {e}")
        return None

    granules = search_opera_dswx(bbox, date, tolerance_days=tolerance_days)
    if not granules:
        print(f"[OPERA] No granules found for bbox={bbox} date={date} ±{tolerance_days}d")
        return None

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
        https_session = earthaccess.get_requests_https_session()

        # Download and open each tile
        tmp_paths = []
        datasets = []
        try:
            for href in hrefs:
                r = https_session.get(href, timeout=120, stream=True)
                r.raise_for_status()
                fd, tmp_path = tempfile.mkstemp(suffix=".tif")
                os.close(fd)
                tmp_paths.append(tmp_path)
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                datasets.append(rasterio.open(tmp_path))

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
            for p in tmp_paths:
                try:
                    os.unlink(p)
                except OSError:
                    pass

    except Exception as e:
        print(f"[OPERA] Failed to fetch/process water mask: {e}")
        return None
