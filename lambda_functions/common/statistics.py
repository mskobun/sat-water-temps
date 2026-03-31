from typing import Dict

import numpy as np


def compute_filter_stats(filter_flags, total_pixels, padding_count=0):
    """Compute filter statistics as bit flag histogram.

    total_pixels counts only pixels inside the polygon (excludes grid padding).
    padding_count is tracked separately for reference.
    """
    # Create histogram of bit flag values (0-15, 4 bits)
    histogram = {}
    for flag_value in range(16):
        count = int(np.sum(filter_flags == flag_value))
        if count > 0:  # Only store non-zero counts
            histogram[str(flag_value)] = count

    stats = {"total_pixels": int(total_pixels), "histogram": histogram}
    if padding_count > 0:
        stats["padding_count"] = padding_count
    return stats


def summarize_temperature_series(values) -> Dict[str, float | None]:
    """Compute summary statistics for a temperature series, ignoring NaNs."""
    arr = np.asarray(values, dtype=np.float64)
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return {
            "min_temp": None,
            "max_temp": None,
            "mean_temp": None,
            "median_temp": None,
            "std_dev": None,
        }

    return {
        "min_temp": float(np.min(finite)),
        "max_temp": float(np.max(finite)),
        "mean_temp": float(np.mean(finite)),
        "median_temp": float(np.median(finite)),
        "std_dev": float(np.std(finite)),
    }
