"""Tests for date conversion and metadata extraction functions."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.dates import extract_metadata, to_sort_date


class TestToSortDate:
    def test_iso_passthrough(self):
        assert to_sort_date("2024-12-27") == "2024-12-27"

    def test_doy_jan_1(self):
        assert to_sort_date("2024001120000") == "2024-01-01"

    def test_doy_dec_27(self):
        assert to_sort_date("2024362041923") == "2024-12-27"

    def test_doy_leap_year(self):
        assert to_sort_date("2024366000000") == "2024-12-31"

    def test_cross_format_comparison(self):
        """Landsat ISO and ECOSTRESS DOY for the same date should produce equal sort keys."""
        assert to_sort_date("2024-12-27") == to_sort_date("2024362041923")


class TestExtractMetadata:
    def test_valid_filename(self):
        aid, date = extract_metadata("ECO_L2T_LSTE_aid0001_doy2024001120000_002_LST_doy.tif")
        assert aid == 1
        assert date == "2024001120000"

    def test_no_match(self):
        assert extract_metadata("random.csv") == (None, None)

    def test_full_path(self):
        aid, date = extract_metadata("/tmp/task/ECO_aid0042_doy2023365235959_QC.tif")
        assert aid == 42
        assert date == "2023365235959"
