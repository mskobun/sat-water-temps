"""ECOSTRESS QC/cloud/water filtering."""

import numpy as np

INVALID_QC_VALUES = {15, 2501, 3525, 65535}


def apply_ecostress_filters(lst, qc, water, cloud):
    """Apply ECOSTRESS-specific filtering to clipped raster arrays.

    All inputs are 2D numpy arrays of the same shape.

    Returns:
        filtered_lst: LST array with rejected pixels set to NaN
        filter_flags: 4-bit flags per pixel
        has_water: whether water filtering was applied
    """
    filter_flags = np.zeros(lst.shape, dtype=np.uint8)

    # Bit 3: NoData / swath gap (no LST data)
    nodata_mask = np.isnan(lst) | (lst <= 0)
    filter_flags = np.where(nodata_mask, filter_flags | 8, filter_flags)

    # Bit 0: QC filtering
    qc_mask = np.isin(qc, list(INVALID_QC_VALUES))
    filter_flags = np.where(qc_mask, filter_flags | 1, filter_flags)

    # Bit 1: Cloud filtering
    cloud_mask = cloud == 1
    filter_flags = np.where(cloud_mask, filter_flags | 2, filter_flags)

    # Bit 2: Water mask — keep only water pixels
    has_water = bool(np.any(water != 0))
    if has_water:
        non_water_mask = water == 0
        filter_flags = np.where(non_water_mask, filter_flags | 4, filter_flags)

    # Apply all filters to LST
    filtered_lst = lst.astype(np.float32).copy()
    reject_mask = filter_flags > 0
    filtered_lst[reject_mask] = np.nan

    return filtered_lst, filter_flags, has_water
