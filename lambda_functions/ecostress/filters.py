"""ECOSTRESS QC/cloud/water filtering.

QC is a uint16 bitmask defined in PSD Table 3-5:
  https://ecostress.jpl.nasa.gov/downloads/psd/ECOSTRESS_SDS_PSD_L2_ver1-1.pdf

  Bits 1&0   Mandatory QA:   00=best, 01=nominal, 10=cloud detected, 11=not produced
  Bits 3&2   Data quality:   00=good L1B, 01=missing stripe, 10=not set, 11=missing/bad L1B
  Bits 5&4   Cloud/Ocean:    Not set (use separate cloud layer)
  Bits 7&6   Iterations:     00=slow, 01=nominal, 10=nominal, 11=fast
  Bits 9&8   Atm. Opacity:   informational
  Bits 11&10 MMD:            informational
  Bits 13&12 Emis accuracy:  informational
  Bits 15&14 LST accuracy:   00=>2K (poor), 01=1.5-2K (marginal), 10=1-1.5K (good), 11=<1K (excellent)

We reject pixels where:
  - Mandatory QA (bits 1&0) = 10 or 11 (cloud detected or not produced)
  - Data quality (bits 3&2) = 11 (missing/bad L1B data)

LST accuracy (bits 15&14) is tracked for diagnostics only and is not used as
a reject criterion.
"""

import numpy as np


def _qc_reject_mask(qc):
    """Build boolean mask for pixels that fail QC bitmask checks."""
    mandatory_qa = qc & 0b11  # bits 1&0
    data_quality = (qc >> 2) & 0b11  # bits 3&2

    return (mandatory_qa >= 2) | (data_quality == 3)


def summarize_qc_bits(qc):
    """Summarize ECOSTRESS QC bit categories for debugging/filter tuning."""
    mandatory_qa = qc & 0b11  # bits 1&0
    data_quality = (qc >> 2) & 0b11  # bits 3&2
    lst_accuracy = (qc >> 14) & 0b11  # bits 15&14

    mandatory_reject = mandatory_qa >= 2
    data_quality_reject = data_quality == 3
    lst_accuracy_poor_or_marginal = lst_accuracy <= 1

    return {
        "total_pixels": int(qc.size),
        "mandatory_qa_best": int(np.sum(mandatory_qa == 0)),
        "mandatory_qa_nominal": int(np.sum(mandatory_qa == 1)),
        "mandatory_qa_cloud": int(np.sum(mandatory_qa == 2)),
        "mandatory_qa_not_produced": int(np.sum(mandatory_qa == 3)),
        "data_quality_good_l1b": int(np.sum(data_quality == 0)),
        "data_quality_missing_stripe": int(np.sum(data_quality == 1)),
        "data_quality_not_set": int(np.sum(data_quality == 2)),
        "data_quality_bad_l1b": int(np.sum(data_quality == 3)),
        "lst_accuracy_poor": int(np.sum(lst_accuracy == 0)),
        "lst_accuracy_marginal": int(np.sum(lst_accuracy == 1)),
        "lst_accuracy_good": int(np.sum(lst_accuracy == 2)),
        "lst_accuracy_excellent": int(np.sum(lst_accuracy == 3)),
        "reject_by_mandatory_qa": int(np.sum(mandatory_reject)),
        "reject_by_data_quality": int(np.sum(data_quality_reject)),
        "reject_by_current_qc": int(np.sum(mandatory_reject | data_quality_reject)),
        "ignored_lst_accuracy_poor_or_marginal": int(np.sum(lst_accuracy_poor_or_marginal)),
    }


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

    # Bit 0: QC filtering (mandatory QA + data quality bitmask checks)
    qc_mask = _qc_reject_mask(qc)
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
