"""Tests for filter_flags and compute_filter_stats in processor.py"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from processor import (
    compute_filter_stats,
    apply_filters,
    NoDataError,
    INVALID_QC_VALUES,
    summarize_temperature_series,
)


def make_df(n=10, **overrides):
    """Create a DataFrame mimicking raster pixel data.

    By default all pixels are inside the polygon (valid QC, valid LST).
    """
    defaults = {
        "LST": np.full(n, 300.0),
        "LST_err": np.full(n, 0.5),
        "QC": np.zeros(n, dtype=np.float64),
        "cloud": np.zeros(n, dtype=np.float64),
        "wt": np.ones(n, dtype=np.float64),  # all water
        "EmisWB": np.full(n, 0.98),
        "height": np.full(n, 100.0),
    }
    defaults.update(overrides)
    return pd.DataFrame(defaults)


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


class TestApplyFilters:
    def test_all_valid_pixels(self):
        """All good pixels -> all in bucket 0."""
        df = make_df(5)
        flags, suffix, padding = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df), padding)
        assert stats["histogram"] == {"0": 5}
        assert padding == 0
        assert suffix == ""

    def test_padding_dropped(self):
        """Pixels with QC=-99999 or QC=NaN are padding and get dropped."""
        df = make_df(6)
        df.loc[0, "QC"] = -99999  # padding
        df.loc[1, "QC"] = np.nan  # padding
        # pixels 2-5 are inside polygon

        flags, _, padding = apply_filters(df, water_mask_flag=True)
        assert padding == 2
        assert len(df) == 4  # only polygon pixels remain
        stats = compute_filter_stats(flags, len(df), padding)
        assert stats["total_pixels"] == 4
        assert stats["histogram"] == {"0": 4}

    def test_nodata_swath_gap(self):
        """LST NaN with valid QC -> bit 3 (swath gap inside polygon)."""
        df = make_df(5)
        df.loc[0, "LST"] = np.nan  # swath gap (QC is valid 0)
        df.loc[1, "LST"] = 0.0     # swath gap
        df.loc[2, "LST"] = -5.0    # swath gap

        flags, _, padding = apply_filters(df, water_mask_flag=True)
        assert padding == 0
        stats = compute_filter_stats(flags, len(df))

        assert stats["histogram"].get("8", 0) == 3  # nodata only
        assert stats["histogram"].get("0", 0) == 2  # valid

    def test_padding_vs_swath_gap(self):
        """Padding (QC fill) is excluded; swath gap (QC real, LST NaN) is bit 3."""
        df = make_df(6)
        df.loc[0, "QC"] = -99999       # padding
        df.loc[1, "QC"] = -99999       # padding
        df.loc[2, "LST"] = np.nan      # swath gap (QC=0, real value)
        df.loc[3, "LST"] = np.nan      # swath gap
        # pixels 4-5 are fully valid

        flags, _, padding = apply_filters(df, water_mask_flag=True)
        assert padding == 2
        assert len(df) == 4
        stats = compute_filter_stats(flags, len(df), padding)
        assert stats["total_pixels"] == 4
        assert stats["histogram"].get("0", 0) == 2   # valid
        assert stats["histogram"].get("8", 0) == 2   # swath gap

    def test_nodata_nans_filter_columns(self):
        """Swath gap pixels must have NaN in _filter columns."""
        df = make_df(3)
        df.loc[0, "LST"] = np.nan

        apply_filters(df, water_mask_flag=True)

        assert pd.isna(df.iloc[0]["LST_filter"])
        assert df.iloc[1]["LST_filter"] == 300.0

    def test_qc_bad_values(self):
        """Bad QC -> bit 0."""
        df = make_df(4)
        df.loc[0, "QC"] = 15
        df.loc[1, "QC"] = 65535

        flags, _, _ = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df))

        assert stats["histogram"].get("1", 0) == 2

    def test_cloud_filtering(self):
        """cloud=1 -> bit 1 (value 2)."""
        df = make_df(4)
        df.loc[0, "cloud"] = 1

        flags, _, _ = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df))

        assert stats["histogram"].get("2", 0) == 1

    def test_water_mask(self):
        """wt=0 (non-water) -> bit 2 (value 4)."""
        df = make_df(4)
        df.loc[0, "wt"] = 0
        df.loc[1, "wt"] = 0

        flags, _, _ = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df))

        assert stats["histogram"].get("4", 0) == 2

    def test_no_water_flag_skips_bit2(self):
        """When water_mask_flag=False, bit 2 is never set and suffix is _wtoff."""
        df = make_df(3)
        df.loc[0, "wt"] = 0

        flags, suffix, _ = apply_filters(df, water_mask_flag=False)
        stats = compute_filter_stats(flags, len(df))

        for k in stats["histogram"]:
            assert not (int(k) & 4)
        assert suffix == "_wtoff"

    def test_overlapping_nodata_qc_cloud(self):
        """Pixel with NaN LST + bad QC + cloud -> bits 0,1,3 = 11."""
        df = make_df(3)
        df.loc[0, "LST"] = np.nan
        df.loc[0, "QC"] = 65535
        df.loc[0, "cloud"] = 1

        flags, _, _ = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df))

        assert stats["histogram"].get("11", 0) == 1  # 8|1|2 = 11
        assert stats["histogram"].get("0", 0) == 2

    def test_total_equals_histogram_sum(self):
        """total_pixels must always equal sum of histogram values."""
        df = make_df(20)
        df.loc[0:2, "LST"] = np.nan
        df.loc[3:5, "QC"] = 65535
        df.loc[6:8, "cloud"] = 1
        df.loc[9:11, "wt"] = 0
        df.loc[12, "LST"] = 0.0

        flags, _, _ = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df))

        assert sum(stats["histogram"].values()) == stats["total_pixels"]

    def test_all_pixels_accounted_for(self):
        """Every non-padding pixel lands in exactly one histogram bucket."""
        df = make_df(8)
        df.loc[0, "QC"] = -99999       # padding (dropped)
        df.loc[1, "QC"] = np.nan        # padding (dropped)
        df.loc[2, "LST"] = np.nan       # swath gap
        df.loc[3, "QC"] = 2501          # bad QC
        df.loc[4, "cloud"] = 1          # cloud
        df.loc[5, "wt"] = 0             # non-water
        df.loc[6, "LST"] = np.nan       # swath gap + cloud
        df.loc[6, "cloud"] = 1
        # pixel 7: valid

        flags, _, padding = apply_filters(df, water_mask_flag=True)
        stats = compute_filter_stats(flags, len(df), padding)

        assert padding == 2
        assert stats["total_pixels"] == 6
        assert sum(stats["histogram"].values()) == 6
        assert stats["histogram"].get("0", 0) == 1   # pixel 7
        assert stats["histogram"].get("8", 0) == 1   # pixel 2: nodata
        assert stats["histogram"].get("1", 0) == 1   # pixel 3: QC
        assert stats["histogram"].get("2", 0) == 1   # pixel 4: cloud
        assert stats["histogram"].get("4", 0) == 1   # pixel 5: water
        assert stats["histogram"].get("10", 0) == 1  # pixel 6: nodata(8) + cloud(2)


class TestNoDataError:
    def test_carries_filter_stats(self):
        """NoDataError stores filter_stats for logging."""
        stats = {"total_pixels": 100, "histogram": {"8": 100}}
        err = NoDataError(stats)
        assert err.filter_stats == stats
        assert str(err) == "No valid pixels after filtering"

    def test_raised_when_all_pixels_filtered(self):
        """All pixels filtered -> NoDataError with correct stats."""
        df = make_df(5)
        df["LST"] = np.nan  # all nodata

        flags, _, padding = apply_filters(df, water_mask_flag=True)
        filter_stats = compute_filter_stats(flags, len(df), padding)

        # Simulate the processor check
        df_valid = df.dropna(subset=["LST_filter"])
        assert len(df_valid) == 0

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
