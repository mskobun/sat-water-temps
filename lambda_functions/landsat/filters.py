"""Landsat QA_PIXEL bitmask filtering.

filter_flags bit positions written by apply_landsat_filters:
  Bit 0 = reserved (unused on Landsat path today)
  Bit 1 = cloud / dilated cloud / cloud shadow
  Bit 2 = non-water reject (when a water mask is active)
  Bit 3 = nodata / fill
  Bit 4 = out-of-physical-range (Kelvin bounds, see common.outliers)
  Bit 5 = spatial outlier (local median-MAD / Hampel test, see common.outliers)
"""

import numpy as np

from common.outliers import hampel_outlier_mask, range_outlier_mask

# QA_PIXEL bitmask positions
QA_BIT_FILL = 0          # Bit 0: fill
QA_BIT_DILATED_CLOUD = 1 # Bit 1: dilated cloud
QA_BIT_CLOUD = 3          # Bit 3: cloud
QA_BIT_CLOUD_SHADOW = 4   # Bit 4: cloud shadow
QA_BIT_WATER = 7           # Bit 7: water


def _check_bit(array, bit):
    """Check if a specific bit is set in the array."""
    return (array & (1 << bit)) != 0


def apply_landsat_filters(lst_kelvin, qa_pixel):
    """Apply QA_PIXEL bitmask filtering to Landsat data.

    Returns:
        filtered_lst: LST array with rejected pixels set to NaN
        filter_flags: 4-bit flags per pixel (bit 0=fill/cloud/shadow, bit 2=non-water, bit 3=nodata)
        water_mask_active: whether water filtering was applied
    """
    filter_flags = np.zeros(lst_kelvin.shape, dtype=np.uint8)

    # Bit 3: NoData (fill pixels or zero LST)
    fill_mask = _check_bit(qa_pixel, QA_BIT_FILL)
    nodata_mask = fill_mask | np.isnan(lst_kelvin) | (lst_kelvin <= 0)
    filter_flags = np.where(nodata_mask, filter_flags | 8, filter_flags)

    # Bit 1: Cloud filtering (dilated cloud, cloud, cloud shadow)
    cloud_mask = (
        _check_bit(qa_pixel, QA_BIT_DILATED_CLOUD) |
        _check_bit(qa_pixel, QA_BIT_CLOUD) |
        _check_bit(qa_pixel, QA_BIT_CLOUD_SHADOW)
    )
    filter_flags = np.where(cloud_mask, filter_flags | 2, filter_flags)

    # Bit 2: Water mask — keep only water pixels
    water_mask = _check_bit(qa_pixel, QA_BIT_WATER)
    has_water = bool(np.any(water_mask))
    if has_water:
        non_water_mask = ~water_mask
        filter_flags = np.where(non_water_mask, filter_flags | 4, filter_flags)
    else:
        # No water detected — don't apply water filter
        pass

    # Bit 4: Out-of-physical-range LST (hard Kelvin bounds)
    range_mask = range_outlier_mask(lst_kelvin)
    filter_flags = np.where(range_mask, filter_flags | 16, filter_flags)

    # Bit 5: Spatial outlier (local median-MAD / Hampel test over 5x5 window)
    valid_so_far = filter_flags == 0
    spatial_mask = hampel_outlier_mask(lst_kelvin, valid_so_far)
    filter_flags = np.where(spatial_mask, filter_flags | 32, filter_flags)

    # Apply all filters to LST
    filtered_lst = lst_kelvin.copy()
    reject_mask = filter_flags > 0
    filtered_lst[reject_mask] = np.nan

    return filtered_lst, filter_flags, has_water
