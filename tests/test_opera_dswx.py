"""Tests for OPERA DSWx-HLS water mask reprojection."""

import os
import sys

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.opera_dswx import (  # noqa: E402
    _reproject_datasets_via_merge,
    _reproject_datasets_windowed,
    opera_mask_to_water_bool,
)


def _memory_dataset(data, transform, crs):
    memfile = MemoryFile()
    with memfile.open(
        driver="GTiff",
        height=data.shape[0],
        width=data.shape[1],
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
        nodata=255,
    ) as dst:
        dst.write(data, 1)
    return memfile, memfile.open()


def test_windowed_opera_reprojection_matches_legacy_merge_water_mask():
    """Windowed per-tile reprojection must preserve legacy merge accuracy."""
    crs = CRS.from_epsg(3857)
    nodata = np.uint8(255)

    left = np.array(
        [
            [0, 1, 1, 1],
            [0, 1, 2, 1],
            [0, 0, 1, 1],
            [nodata, nodata, 1, 1],
        ],
        dtype=np.uint8,
    )
    right = np.array(
        [
            [0, 0, 2, 2],
            [2, 2, 2, 2],
            [1, 1, 0, 0],
            [1, 1, 0, 0],
        ],
        dtype=np.uint8,
    )

    left_mem, left_ds = _memory_dataset(left, from_origin(0, 4, 1, 1), crs)
    right_mem, right_ds = _memory_dataset(right, from_origin(2, 4, 1, 1), crs)
    try:
        datasets = [left_ds, right_ds]
        target_shape = (4, 6)
        target_transform = from_origin(0, 4, 1, 1)

        legacy = _reproject_datasets_via_merge(
            datasets, target_shape, target_transform, crs
        )
        windowed = _reproject_datasets_windowed(
            datasets, target_shape, target_transform, crs
        )

        np.testing.assert_array_equal(
            opera_mask_to_water_bool(windowed),
            opera_mask_to_water_bool(legacy),
        )
    finally:
        left_ds.close()
        right_ds.close()
        left_mem.close()
        right_mem.close()
