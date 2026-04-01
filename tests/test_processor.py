"""Tests for ECOSTRESS filter_flags and compute_filter_stats."""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.statistics import compute_filter_stats, summarize_temperature_series
from common.exceptions import NoDataError
from ecostress.filters import apply_ecostress_filters, _qc_reject_mask


# QC=0x8000: bits 15&14=10 (good LST accuracy), all other bits=00 (best/good)
GOOD_QC = 0x8000


def make_arrays(n=10, **overrides):
    """Create 1D numpy arrays mimicking clipped raster pixel data.

    By default all pixels are valid water pixels with good LST/QC.
    """
    defaults = {
        "lst": np.full(n, 300.0, dtype=np.float32),
        "qc": np.full(n, GOOD_QC, dtype=np.uint16),
        "cloud": np.zeros(n, dtype=np.float32),
        "water": np.ones(n, dtype=np.float32),  # all water
    }
    defaults.update(overrides)
    return defaults


class TestComputeFilterStats:
    def test_all_valid(self):
        flags = np.zeros(100, dtype=np.uint8)
        stats = compute_filter_stats(flags, 100)
        assert stats["total_pixels"] == 100
        assert stats["histogram"]["0"] == 100
        assert sum(stats["histogram"].values()) == 100

    def test_histogram_covers_16_buckets(self):
        flags = np.arange(16, dtype=np.uint8)
        stats = compute_filter_stats(flags, 16)
        for i in range(16):
            assert stats["histogram"][str(i)] == 1
        assert sum(stats["histogram"].values()) == 16

    def test_omits_zero_counts(self):
        flags = np.array([0, 0, 8, 8], dtype=np.uint8)
        stats = compute_filter_stats(flags, 4)
        assert set(stats["histogram"].keys()) == {"0", "8"}

    def test_padding_count_stored(self):
        flags = np.zeros(5, dtype=np.uint8)
        stats = compute_filter_stats(flags, 5, padding_count=10)
        assert stats["padding_count"] == 10

    def test_no_padding_count_when_zero(self):
        flags = np.zeros(5, dtype=np.uint8)
        stats = compute_filter_stats(flags, 5, padding_count=0)
        assert "padding_count" not in stats


class TestApplyEcostressFilters:
    def test_qc_reject_mask_operates_on_uint16_inputs(self):
        qc = np.array([GOOD_QC, 0b11, 0x4000], dtype=np.uint16)

        assert _qc_reject_mask(qc).tolist() == [False, True, True]

    def test_all_valid_pixels(self):
        """All good pixels -> all in bucket 0."""
        a = make_arrays(5)
        filtered_lst, flags, has_water = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        stats = compute_filter_stats(flags.ravel(), len(flags.ravel()))
        assert stats["histogram"] == {"0": 5}
        assert has_water is True
        assert np.all(~np.isnan(filtered_lst))

    def test_nodata_swath_gap(self):
        """LST NaN with valid QC -> bit 3 (swath gap)."""
        a = make_arrays(5)
        a["lst"][0] = np.nan  # swath gap
        a["lst"][1] = 0.0  # swath gap (LST <= 0)
        a["lst"][2] = -5.0  # swath gap

        filtered_lst, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("8", 0) == 3  # nodata only
        assert stats["histogram"].get("0", 0) == 2  # valid

    def test_qc_mandatory_qa_not_produced(self):
        """Mandatory QA bits 1&0 = 11 (not produced) -> bit 0."""
        a = make_arrays(4)
        a["qc"][0] = 0b11  # not produced
        a["qc"][1] = 0b10  # cloud detected in QC

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("1", 0) == 2

    def test_qc_data_quality_bad_l1b(self):
        """Data quality bits 3&2 = 11 (missing/bad L1B) -> bit 0."""
        a = make_arrays(4)
        a["qc"][0] = 0b1100  # bad L1B, good mandatory QA

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("1", 0) == 1

    def test_qc_nominal_quality_passes(self):
        """Mandatory QA bits 1&0 = 01 (nominal) should pass QC."""
        a = make_arrays(4)
        a["qc"][0] = GOOD_QC | 0b01  # nominal quality + good LST accuracy

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("0", 0) == 4

    def test_qc_informational_bits_dont_reject(self):
        """Informational QC bits (iterations, opacity, MMD) don't cause rejection."""
        a = make_arrays(4)
        # Set informational bits (6-13) high, keep mandatory QA + data quality good,
        # LST accuracy = good (10)
        a["qc"][0] = GOOD_QC | 0b00110011000000  # bits 6-13 set

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("0", 0) == 4

    def test_qc_lst_accuracy_poor_rejected(self):
        """LST accuracy bits 15&14 = 00 (>2K, poor) -> bit 0."""
        a = make_arrays(4)
        a["qc"][0] = 0  # all zeros = poor LST accuracy

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("1", 0) == 1

    def test_qc_lst_accuracy_marginal_rejected(self):
        """LST accuracy bits 15&14 = 01 (1.5-2K, marginal) -> bit 0."""
        a = make_arrays(4)
        a["qc"][0] = 0b01_00_00_00_00_00_00_00  # 0x4000, marginal

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("1", 0) == 1

    def test_qc_lst_accuracy_good_passes(self):
        """LST accuracy bits 15&14 = 10 (1-1.5K, good) passes."""
        a = make_arrays(4)
        a["qc"][:] = 0x8000  # good LST accuracy

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("0", 0) == 4

    def test_qc_lst_accuracy_excellent_passes(self):
        """LST accuracy bits 15&14 = 11 (<1K, excellent) passes."""
        a = make_arrays(4)
        a["qc"][:] = 0xC000  # excellent LST accuracy

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("0", 0) == 4

    def test_cloud_filtering(self):
        """cloud=1 -> bit 1 (value 2)."""
        a = make_arrays(4)
        a["cloud"][0] = 1

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("2", 0) == 1

    def test_water_mask(self):
        """water=0 (non-water) -> bit 2 (value 4)."""
        a = make_arrays(4)
        a["water"][0] = 0
        a["water"][1] = 0

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("4", 0) == 2

    def test_no_water_pixels_skips_water_mask(self):
        """When no water pixels exist, has_water is False and bit 2 is never set."""
        a = make_arrays(3)
        a["water"][:] = 0  # no water at all

        _, flags, has_water = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        assert has_water is False
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        # All pixels valid since water mask not applied
        assert stats["histogram"] == {"0": 3}

    def test_overlapping_nodata_qc_cloud(self):
        """Pixel with NaN LST + bad QC + cloud -> bits 0,1,3 = 11."""
        a = make_arrays(3)
        a["lst"][0] = np.nan
        a["qc"][0] = 0b11  # not produced
        a["cloud"][0] = 1

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["histogram"].get("11", 0) == 1  # 8|1|2 = 11
        assert stats["histogram"].get("0", 0) == 2

    def test_total_equals_histogram_sum(self):
        """total_pixels must always equal sum of histogram values."""
        a = make_arrays(20)
        a["lst"][0:3] = np.nan
        a["qc"][3:6] = 0b11  # not produced
        a["cloud"][6:9] = 1
        a["water"][9:12] = 0
        a["lst"][12] = 0.0

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert sum(stats["histogram"].values()) == stats["total_pixels"]

    def test_all_pixels_accounted_for(self):
        """Every pixel lands in exactly one histogram bucket."""
        a = make_arrays(6)
        a["lst"][0] = np.nan  # swath gap
        a["qc"][1] = 0b11  # not produced (mandatory QA)
        a["cloud"][2] = 1  # cloud
        a["water"][3] = 0  # non-water
        a["lst"][4] = np.nan  # swath gap + cloud
        a["cloud"][4] = 1
        # pixel 5: valid

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        stats = compute_filter_stats(flat, len(flat))
        assert stats["total_pixels"] == 6
        assert sum(stats["histogram"].values()) == 6
        assert stats["histogram"].get("0", 0) == 1  # pixel 5
        assert stats["histogram"].get("8", 0) == 1  # pixel 0: nodata
        assert stats["histogram"].get("1", 0) == 1  # pixel 1: QC
        assert stats["histogram"].get("2", 0) == 1  # pixel 2: cloud
        assert stats["histogram"].get("4", 0) == 1  # pixel 3: water
        assert stats["histogram"].get("10", 0) == 1  # pixel 4: nodata(8) + cloud(2)

    def test_filtered_lst_nans_rejected(self):
        """Rejected pixels have NaN in filtered_lst."""
        a = make_arrays(3)
        a["qc"][0] = 0b1111  # mandatory QA=11 + data quality=11

        filtered_lst, _, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        assert np.isnan(filtered_lst.ravel()[0])
        assert not np.isnan(filtered_lst.ravel()[1])
        assert not np.isnan(filtered_lst.ravel()[2])


class TestNoDataError:
    def test_carries_filter_stats(self):
        """NoDataError stores filter_stats for logging."""
        stats = {"total_pixels": 100, "histogram": {"8": 100}}
        err = NoDataError(stats)
        assert err.filter_stats == stats
        assert str(err) == "No valid pixels after filtering"

    def test_raised_when_all_pixels_filtered(self):
        """All pixels filtered -> NoDataError with correct stats."""
        a = make_arrays(5)
        a["lst"][:] = np.nan  # all nodata

        _, flags, _ = apply_ecostress_filters(
            a["lst"], a["qc"], a["water"], a["cloud"]
        )
        flat = flags.ravel()
        filter_stats = compute_filter_stats(flat, len(flat))

        with pytest.raises(NoDataError) as exc_info:
            raise NoDataError(filter_stats)
        assert exc_info.value.filter_stats["histogram"].get("8", 0) == 5


class TestSummarizeTemperatureSeries:
    def test_computes_all_summary_stats(self):
        stats = summarize_temperature_series(pd.Series([300.0, 302.0, 304.0]))
        assert stats == {
            "min_temp": 300.0,
            "max_temp": 304.0,
            "mean_temp": 302.0,
            "median_temp": 302.0,
            "std_dev": pytest.approx(np.std([300.0, 302.0, 304.0])),
        }

    def test_ignores_nan_values(self):
        stats = summarize_temperature_series(pd.Series([300.0, np.nan, 306.0]))
        assert stats["min_temp"] == 300.0
        assert stats["max_temp"] == 306.0
        assert stats["mean_temp"] == 303.0
        assert stats["median_temp"] == 303.0

    def test_returns_none_when_all_values_missing(self):
        stats = summarize_temperature_series(pd.Series([np.nan, np.nan]))
        assert stats == {
            "min_temp": None,
            "max_temp": None,
            "mean_temp": None,
            "median_temp": None,
            "std_dev": None,
        }
