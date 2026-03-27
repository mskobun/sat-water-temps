"""Tests for Landsat processor: QA_PIXEL bitmask filtering and processing pipeline."""
import os
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

# Real ST_B10 + QA_PIXEL window crops from USGS Landsat C2 L2 ST (see fixture README).
LANDSAT_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "landsat_lc09_116048_20241227"

from landsat_processor import (
    apply_landsat_filters,
    SCALE_FACTOR,
    ADD_OFFSET,
    QA_BIT_FILL,
    QA_BIT_DILATED_CLOUD,
    QA_BIT_CLOUD,
    QA_BIT_CLOUD_SHADOW,
    QA_BIT_WATER,
)


# Magat reservoir polygon bbox (from plan fixture)
MAGAT_BBOX = [121.378, 16.791, 121.457, 16.861]

# Helper: create a small synthetic raster matching Magat's polygon extent
ROWS, COLS = 10, 10
TRANSFORM = from_bounds(*MAGAT_BBOX, COLS, ROWS)
CRS_EPSG = CRS.from_epsg(32651)


def make_lst_kelvin(n=ROWS * COLS, temp_k=300.0):
    """Create an array of LST values in Kelvin."""
    return np.full((ROWS, COLS), temp_k, dtype=np.float32)


def make_qa_pixel(n=ROWS * COLS, water=True):
    """Create QA_PIXEL array. By default all pixels are water (bit 7 set)."""
    val = (1 << QA_BIT_WATER) if water else 0
    return np.full((ROWS, COLS), val, dtype=np.uint16)


class TestApplyLandsatFilters:
    def test_all_valid_water_pixels(self):
        """All water pixels with valid LST -> all pass (flag 0)."""
        lst = make_lst_kelvin(temp_k=300.0)
        qa = make_qa_pixel(water=True)
        filtered, flags, has_water = apply_landsat_filters(lst, qa)

        assert has_water is True
        assert np.sum(flags == 0) == ROWS * COLS
        assert np.all(~np.isnan(filtered))

    def test_fill_pixels_flagged(self):
        """Fill bit (bit 0) -> nodata flag (bit 3 = 8)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        # Set first 3 pixels as fill
        qa.flat[:3] = (1 << QA_BIT_FILL) | (1 << QA_BIT_WATER)

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        assert np.all((flags.flat[:3] & 8) != 0)  # bit 3 set for fill pixels
        assert np.all(np.isnan(filtered.flat[:3]))

    def test_cloud_pixels_flagged(self):
        """Cloud bit (bit 3) -> cloud flag (bit 1 = 2)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        # Set pixel 0 as cloud
        qa.flat[0] = (1 << QA_BIT_CLOUD) | (1 << QA_BIT_WATER)

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        assert flags.flat[0] & 2  # bit 1 set
        assert np.isnan(filtered.flat[0])
        # Other pixels should be valid
        assert np.sum(flags == 0) == ROWS * COLS - 1

    def test_dilated_cloud_flagged(self):
        """Dilated cloud bit (bit 1) -> cloud flag (bit 1 = 2)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        qa.flat[0] = (1 << QA_BIT_DILATED_CLOUD) | (1 << QA_BIT_WATER)

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        assert flags.flat[0] & 2

    def test_cloud_shadow_flagged(self):
        """Cloud shadow bit (bit 4) -> cloud flag (bit 1 = 2)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        qa.flat[0] = (1 << QA_BIT_CLOUD_SHADOW) | (1 << QA_BIT_WATER)

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        assert flags.flat[0] & 2

    def test_non_water_pixels_flagged(self):
        """Non-water pixels -> water mask flag (bit 2 = 4)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        # Set 5 pixels as non-water (no water bit)
        for i in range(5):
            qa.flat[i] = 0  # no water bit set

        filtered, flags, has_water = apply_landsat_filters(lst, qa)

        assert has_water is True  # some water exists
        non_water_count = np.sum((flags & 4) > 0)
        assert non_water_count == 5
        # Non-water pixels should be NaN
        assert np.sum(np.isnan(filtered.flat[:5])) == 5

    def test_no_water_detected(self):
        """When no water pixels at all, water mask is not applied."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=False)  # no water bit set on any pixel

        filtered, flags, has_water = apply_landsat_filters(lst, qa)

        assert has_water is False
        # No bit 2 should be set
        assert np.sum((flags & 4) > 0) == 0
        # All pixels should be valid (no cloud, no fill)
        assert np.sum(flags == 0) == ROWS * COLS

    def test_nodata_from_zero_lst(self):
        """LST <= 0 -> nodata flag (bit 3 = 8)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        lst.flat[0] = 0.0
        lst.flat[1] = -5.0

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        assert flags.flat[0] & 8
        assert flags.flat[1] & 8

    def test_nodata_from_nan(self):
        """NaN LST -> nodata flag (bit 3 = 8)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        lst.flat[0] = np.nan

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        assert flags.flat[0] & 8

    def test_overlapping_flags(self):
        """Cloud + non-water -> bits 1 and 2 both set (flag = 6)."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        # Pixel 0: cloud (bit 3) + no water bit
        qa.flat[0] = (1 << QA_BIT_CLOUD)  # cloud, but NOT water

        filtered, flags, _ = apply_landsat_filters(lst, qa)

        # Should have both cloud (2) and non-water (4) = 6
        assert flags.flat[0] == 6
        assert np.isnan(filtered.flat[0])

    def test_all_flags_accounted(self):
        """Every pixel gets exactly one flag value; total matches."""
        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        # Mix of conditions
        lst.flat[0] = np.nan  # nodata
        qa.flat[1] = (1 << QA_BIT_CLOUD) | (1 << QA_BIT_WATER)  # cloud
        qa.flat[2] = 0  # non-water
        qa.flat[3] = (1 << QA_BIT_FILL) | (1 << QA_BIT_WATER)  # fill

        _, flags, _ = apply_landsat_filters(lst, qa)

        # All pixels should have a flag value
        assert flags.size == ROWS * COLS
        # Check specific flags
        assert flags.flat[0] & 8  # nodata
        assert flags.flat[1] & 2  # cloud
        assert flags.flat[2] & 4  # non-water
        assert flags.flat[3] & 8  # fill -> nodata


class TestScaleFactor:
    def test_scale_to_kelvin(self):
        """Verify DN-to-Kelvin conversion produces reasonable values."""
        # A typical DN value for ~300K
        dn = (300.0 - ADD_OFFSET) / SCALE_FACTOR
        kelvin = dn * SCALE_FACTOR + ADD_OFFSET
        assert abs(kelvin - 300.0) < 0.01

    def test_zero_dn_is_cold(self):
        """DN=0 should produce the offset temperature (149K, very cold)."""
        kelvin = 0 * SCALE_FACTOR + ADD_OFFSET
        assert kelvin == pytest.approx(149.0)


class TestSTACMocking:
    """Test STAC response handling with mock data matching the fixture scene."""

    FIXTURE_SCENE = {
        "id": "LC09_L2SP_116048_20241227_20241228_02_T1_ST",
        "datetime": "2024-12-27T02:16:48Z",
        "properties": {
            "platform": "LANDSAT_9",
            "eo:cloud_cover": 11.47,
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [121.0, 16.5], [122.0, 16.5],
                [122.0, 17.0], [121.0, 17.0],
                [121.0, 16.5],
            ]]
        },
        "assets": {
            "lwir11": {
                "href": "s3://usgs-landsat/collection02/level-2/standard/oli-tirs/2024/116/048/LC09_L2SP_116048_20241227_20241228_02_T1/LC09_L2SP_116048_20241227_20241228_02_T1_ST_B10.TIF",
            },
            "qa": {
                "href": "s3://usgs-landsat/collection02/level-2/standard/oli-tirs/2024/116/048/LC09_L2SP_116048_20241227_20241228_02_T1/LC09_L2SP_116048_20241227_20241228_02_T1_ST_QA.TIF",
            },
            "qa_pixel": {
                "href": "s3://usgs-landsat/collection02/level-2/standard/oli-tirs/2024/116/048/LC09_L2SP_116048_20241227_20241228_02_T1/LC09_L2SP_116048_20241227_20241228_02_T1_QA_PIXEL.TIF",
            },
        }
    }

    def test_fixture_scene_covers_magat(self):
        """Verify fixture scene geometry intersects Magat bbox."""
        from shapely.geometry import shape, box
        scene_geom = shape(self.FIXTURE_SCENE["geometry"])
        magat_box = box(*MAGAT_BBOX)
        assert scene_geom.intersects(magat_box)

    def test_required_assets_present(self):
        """Verify fixture has all required STAC assets."""
        from landsat_initiator import REQUIRED_ASSETS
        for key in REQUIRED_ASSETS:
            assert key in self.FIXTURE_SCENE["assets"]


class TestFilterStatsIntegration:
    """Test that apply_landsat_filters output is compatible with compute_filter_stats."""

    def test_stats_from_landsat_filters(self):
        """compute_filter_stats should work with Landsat filter output."""
        from processor import compute_filter_stats

        lst = make_lst_kelvin()
        qa = make_qa_pixel(water=True)
        # Create a mix of conditions
        lst.flat[0] = np.nan  # nodata
        qa.flat[1] = (1 << QA_BIT_CLOUD) | (1 << QA_BIT_WATER)  # cloud
        qa.flat[2] = 0  # non-water

        _, flags, _ = apply_landsat_filters(lst, qa)
        stats = compute_filter_stats(flags.flatten(), flags.size)

        assert stats["total_pixels"] == ROWS * COLS
        assert sum(stats["histogram"].values()) == ROWS * COLS
        # At least some valid (flag 0) and some filtered pixels
        assert stats["histogram"].get("0", 0) > 0
        assert stats["histogram"].get("0", 0) < ROWS * COLS


class TestLandsatProcessOneRecordFixture:
    """End-to-end processor test using real Landsat COG windows (EPSG:32651) + WGS84 polygons."""

    @pytest.fixture
    def magat_landsat_body(self):
        st_path = LANDSAT_FIXTURE_DIR / "ST_B10.tif"
        qa_path = LANDSAT_FIXTURE_DIR / "QA_PIXEL.tif"
        assert st_path.is_file(), f"Missing fixture: {st_path}"
        assert qa_path.is_file(), f"Missing fixture: {qa_path}"
        return {
            "source": "landsat",
            "aid": 1,
            "date": "2024-12-27",
            "name": "Magat",
            "location": "lake",
            "scenes": [
                {
                    "scene_id": "LC09_L2SP_116048_20241227_20241228_02_T1",
                    "hrefs": {
                        "lwir11": str(st_path),
                        "qa_pixel": str(qa_path),
                    },
                    "cloud_cover": 11.47,
                }
            ],
        }

    @pytest.mark.filterwarnings("ignore:All-NaN slice encountered:RuntimeWarning")
    def test_process_one_record_completes_with_real_cog_fixture(self, magat_landsat_body, monkeypatch):
        """WGS84 polygon must clip UTM Landsat rasters without 'Input shapes do not overlap raster'."""
        repo_root = Path(__file__).resolve().parent.parent
        monkeypatch.chdir(repo_root)

        inserted = []
        uploaded_csvs = {}

        def capture_insert(feature_id, date, metadata, csv_r2_key, tif_r2_key, png_r2_keys, source="ecostress", parquet_path=None):
            inserted.append(
                {
                    "feature_id": feature_id,
                    "date": date,
                    "metadata": metadata,
                    "csv_r2_key": csv_r2_key,
                    "tif_r2_key": tif_r2_key,
                    "png_r2_keys": png_r2_keys,
                    "source": source,
                    "parquet_path": parquet_path,
                }
            )

        def capture_upload(s3_client, bucket, key, local_path, content_type=None):
            if ".csv" in key:
                uploaded_csvs[key] = local_path

        def capture_csv_upload(s3_client, bucket, key, csv_file_path):
            capture_upload(s3_client, bucket, key, csv_file_path)

        mock_s3 = MagicMock()

        with patch("landsat_processor.upload_to_r2", side_effect=capture_upload) as _upload, patch(
            "landsat_processor.upload_csv_to_r2", side_effect=capture_csv_upload
        ), patch(
            "landsat_processor.upload_parquet_to_r2"
        ), patch(
            "landsat_processor.insert_metadata_to_d1", side_effect=capture_insert
        ), patch("landsat_processor.log_job_to_d1"), patch(
            "landsat_processor._get_s3_client", return_value=mock_s3
        ), patch("landsat_processor.tif_to_png", return_value=__import__('io').BytesIO(b'\x89PNG')):
            from landsat_processor import process_one_record

            # Read CSV before cleanup by capturing it in upload
            process_one_record(magat_landsat_body)

        assert len(inserted) == 1
        row = inserted[0]
        assert row["feature_id"] == "Magat"
        assert row["source"] == "landsat"
        assert row["metadata"]["date"] == "2024-12-27"
        assert row["metadata"]["data_points"] > 0
        assert row["metadata"]["min_temp"] is not None
        assert row["metadata"]["max_temp"] is not None
        assert row["metadata"]["mean_temp"] is not None
        assert row["metadata"]["median_temp"] is not None
        assert row["metadata"]["std_dev"] is not None
        assert "LANDSAT/Magat/lake/" in row["csv_r2_key"]
        assert "filter_stats" in row["metadata"]
        assert row["metadata"].get("source_crs")
        tf = row["metadata"].get("transform")
        assert tf and "a" in tf and abs(tf["a"]) > 1e-6

    @pytest.mark.filterwarnings("ignore:All-NaN slice encountered:RuntimeWarning")
    def test_csv_coordinates_are_wgs84(self, magat_landsat_body, monkeypatch, tmp_path):
        """CSV longitude/latitude must be in WGS84 (degrees), not projected UTM (meters)."""
        repo_root = Path(__file__).resolve().parent.parent
        monkeypatch.chdir(repo_root)

        saved_csv = [None]

        def capture_upload(s3_client, bucket, key, local_path, content_type=None):
            if ".csv" in key:
                import shutil
                dest = tmp_path / "output.csv"
                shutil.copy2(local_path, dest)
                saved_csv[0] = dest

        def capture_csv_upload(s3_client, bucket, key, csv_file_path):
            capture_upload(s3_client, bucket, key, csv_file_path)

        with patch("landsat_processor.upload_to_r2", side_effect=capture_upload), patch(
            "landsat_processor.upload_csv_to_r2", side_effect=capture_csv_upload
        ), patch(
            "landsat_processor.upload_parquet_to_r2"
        ), patch(
            "landsat_processor.insert_metadata_to_d1"
        ), patch("landsat_processor.log_job_to_d1"), patch(
            "landsat_processor._get_s3_client", return_value=MagicMock()
        ), patch("landsat_processor.tif_to_png", return_value=__import__('io').BytesIO(b'\x89PNG')):
            from landsat_processor import process_one_record
            process_one_record(magat_landsat_body)

        assert saved_csv[0] is not None, "No CSV was uploaded"
        df = pd.read_csv(saved_csv[0])
        assert len(df) > 0

        # WGS84 coordinates: longitude ~98-99, latitude ~8-9 for Magat
        # UTM coordinates would be ~400000-500000 for easting
        assert df["longitude"].max() < 180, f"Longitude {df['longitude'].max()} looks like projected CRS, not WGS84"
        assert df["longitude"].min() > -180, f"Longitude {df['longitude'].min()} out of WGS84 range"
        assert df["latitude"].max() < 90, f"Latitude {df['latitude'].max()} looks like projected CRS, not WGS84"
        assert df["latitude"].min() > -90, f"Latitude {df['latitude'].min()} out of WGS84 range"

    def test_mask_fails_if_polygon_left_in_wgs84(self):
        """Regression: passing lon/lat shapes to mask() on a UTM raster does not overlap."""
        import json
        from shapely.geometry import shape, mapping
        from rasterio.mask import mask

        st_path = LANDSAT_FIXTURE_DIR / "ST_B10.tif"
        with open(Path(__file__).resolve().parent.parent / "static" / "polygons_new.geojson") as f:
            roi = json.load(f)
        polygon_geom = shape(roi["features"][0]["geometry"])
        wgs_shapes = [mapping(polygon_geom)]

        with rasterio.open(st_path) as src:
            with pytest.raises(ValueError, match="do not overlap"):
                mask(src, wgs_shapes, crop=True)
