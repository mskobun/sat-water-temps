"""Tests for common.raster_inputs (local path / env helpers)."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_bounds

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.raster_inputs import (  # noqa: E402
    landsat_rasterio_env,
    open_landsat_band,
    open_raster_http_local_or_file,
)

LANDSAT_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "landsat_lc09_116048_20241227"


class TestLandsatRasterInputs:
    def test_open_landsat_local_fixture_path(self):
        st = LANDSAT_FIXTURE_DIR / "ST_B10.tif"
        assert st.is_file()
        with landsat_rasterio_env(
            [
                {
                    "hrefs": {
                        "lwir11": str(st),
                        "qa_pixel": str(LANDSAT_FIXTURE_DIR / "QA_PIXEL.tif"),
                    }
                }
            ]
        ):
            src = open_landsat_band(str(st))
            try:
                assert src.count >= 1
            finally:
                src.close()

    def test_landsat_env_not_used_for_local_paths_only(self):
        mock_env = MagicMock()
        mock_env.__enter__ = MagicMock(return_value=None)
        mock_env.__exit__ = MagicMock(return_value=None)
        with patch("common.raster_inputs.rasterio.Env", return_value=mock_env) as env_cls:
            with landsat_rasterio_env(
                [{"hrefs": {"lwir11": "/tmp/a.tif", "qa_pixel": "/tmp/b.tif"}}]
            ):
                pass
        env_cls.assert_not_called()


def test_open_raster_http_with_earthdata_session_streams_via_session():
    """LP DAAC HTTPS needs EDL bearer auth; session.get must be used (not raw requests)."""
    data = np.zeros((1, 8, 8), dtype=np.uint8)
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            width=8,
            height=8,
            count=1,
            dtype="uint8",
            crs="EPSG:4326",
            transform=from_bounds(-1, -1, 1, 1, 8, 8),
        ) as dst:
            dst.write(data)
        tif_bytes = mem.read()

    sess = MagicMock()

    def _fake_get(url, timeout=600, stream=True):
        assert url == "https://data.lpdaac.earthdatacloud.nasa.gov/protected/x.tif"
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.iter_content = MagicMock(return_value=[tif_bytes])
        return resp

    sess.get.side_effect = _fake_get

    ds = open_raster_http_local_or_file(
        "https://data.lpdaac.earthdatacloud.nasa.gov/protected/x.tif",
        session=sess,
    )
    try:
        assert ds.width == 8
        assert ds.height == 8
    finally:
        ds.close()
    sess.get.assert_called_once()
