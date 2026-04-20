"""Physical-range and spatial outlier detection for LST pipelines.

Two checks are exposed for use by the ECOSTRESS and Landsat filter stages:

- ``range_outlier_mask`` — hard Kelvin bounds. Catches obviously broken pixels
  (raw sentinels, scaling mistakes, negative-Celsius artefacts).
- ``hampel_outlier_mask`` — local median-MAD test (Hampel identifier, applied
  spatially over a 5x5 window). Catches in-range pixels inconsistent with their
  neighbours, the signature of residual cloud/shadow/adjacency/shoreline mixing.

Bit positions used in filter_flags (see ``ecostress/filters.py`` and
``landsat/filters.py``):

    Bit 4 (value 16) = out-of-physical-range
    Bit 5 (value 32) = spatial outlier
"""

import warnings

import numpy as np

LST_MIN_K = 273.0
LST_MAX_K = 315.0

HAMPEL_K = 3.0
MAD_SCALE = 1.4826
LOCAL_WINDOW = 5
MIN_WINDOW_VALID = 5
MIN_FRAME_VALID = 20

# Minimum deviation (K) required to flag a spatial outlier, regardless of how
# small the local MAD is. Anchored to the published single-pixel LST product
# uncertainty (ECOSTRESS L2 LSTE target ~1.5 K, Landsat Collection 2 L2 ST
# ~2 K). Below this floor we can't distinguish genuine pixel-to-pixel product
# noise from real contamination, so we refuse to flag. Typical cloud-shadow /
# thin-cirrus / adjacency contamination is 3-15 K and still clears the floor.
MIN_OUTLIER_DELTA_K = 2.0

OUTLIER_RANGE_BIT = 4
OUTLIER_SPATIAL_BIT = 5


def range_outlier_mask(lst):
    """Boolean mask of pixels outside the physical LST range.

    Values that are NaN or <= 0 are already handled by the nodata bit and are
    not flagged here, so bit 4 means "plausibly-a-measurement-but-wrong"
    rather than overlapping with sentinel/missing indicators.
    """
    arr = np.asarray(lst)
    with np.errstate(invalid="ignore"):
        numeric = ~np.isnan(arr) & (arr > 0)
        return np.where(numeric, (arr < LST_MIN_K) | (arr > LST_MAX_K), False)


def hampel_outlier_mask(lst, valid_mask):
    """Boolean mask of pixels failing a local 5x5 median-MAD (Hampel) test.

    Only ``valid_mask`` pixels participate in the local statistics, so clouds,
    land, and earlier rejects don't contaminate the neighbour medians.

    Returns an all-False mask if the frame has fewer than ``MIN_FRAME_VALID``
    valid pixels. Individual pixels whose 5x5 window has fewer than
    ``MIN_WINDOW_VALID`` valid neighbours are also skipped.

    The rejection threshold is floored at ``MIN_OUTLIER_DELTA_K`` so that on
    very calm water (tiny local MAD) we don't reject pixels whose deviation is
    within the single-pixel product-uncertainty noise floor.
    """
    lst = np.asarray(lst, dtype=np.float32)
    valid_mask = np.asarray(valid_mask, dtype=bool)
    result = np.zeros(lst.shape, dtype=bool)

    if lst.ndim != 2:
        return result

    if int(np.sum(valid_mask)) < MIN_FRAME_VALID:
        return result

    working = np.where(valid_mask, lst, np.nan).astype(np.float32)
    pad = LOCAL_WINDOW // 2
    padded = np.pad(working, pad, mode="constant", constant_values=np.nan)
    windows = np.lib.stride_tricks.sliding_window_view(
        padded, (LOCAL_WINDOW, LOCAL_WINDOW)
    )
    flat = windows.reshape(lst.shape[0], lst.shape[1], -1)

    with np.errstate(invalid="ignore", all="ignore"), warnings.catch_warnings():
        # All-NaN windows are expected for isolated valid pixels — suppress the
        # numpy RuntimeWarning and let the guards below handle those pixels.
        warnings.filterwarnings("ignore", r"All-NaN slice encountered", RuntimeWarning)
        valid_count = np.sum(~np.isnan(flat), axis=-1)
        local_median = np.nanmedian(flat, axis=-1)
        local_mad = np.nanmedian(np.abs(flat - local_median[..., None]), axis=-1)
        deviation = np.abs(lst - local_median)
        threshold = np.maximum(HAMPEL_K * MAD_SCALE * local_mad, MIN_OUTLIER_DELTA_K)
        reject = deviation > threshold

    skip = (
        ~valid_mask
        | np.isnan(lst)
        | np.isnan(local_median)
        | np.isnan(local_mad)
        | (valid_count < MIN_WINDOW_VALID)
    )
    return np.where(skip, False, reject)
