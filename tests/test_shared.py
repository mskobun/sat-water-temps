"""Tests for lambda_functions/shared.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from shared import extract_metadata


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
