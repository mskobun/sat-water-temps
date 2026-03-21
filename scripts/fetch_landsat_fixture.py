#!/usr/bin/env python3
"""Download windowed ST_B10 + QA_PIXEL from USGS Landsat (requester-pays) for tests."""

from __future__ import annotations

import json
from pathlib import Path

import boto3
import rasterio
from rasterio.session import AWSSession
from rasterio.windows import from_bounds
from shapely.geometry import shape
from rasterio.warp import transform_bounds

REPO_ROOT = Path(__file__).resolve().parent.parent
GEOJSON = REPO_ROOT / "static" / "polygons_new.geojson"
OUT_DIR = REPO_ROOT / "tests" / "fixtures" / "landsat_lc09_116048_20241227"

# LC09 scene used in tests (Philippines path/row 116/048)
BASE = (
    "s3://usgs-landsat/collection02/level-2/standard/oli-tirs/"
    "2024/116/048/LC09_L2SP_116048_20241227_20241228_02_T1/"
    "LC09_L2SP_116048_20241227_20241228_02_T1_"
)


def main() -> None:
    with open(GEOJSON) as f:
        roi = json.load(f)
    poly = shape(roi["features"][0]["geometry"])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    aws = AWSSession(boto3.Session(), requester_pays=True)

    st_url = BASE + "ST_B10.TIF"
    qa_url = BASE + "QA_PIXEL.TIF"

    with rasterio.Env(aws, AWS_REQUEST_PAYER="requester"):
        with rasterio.open(st_url) as st:
            crs = st.crs
            minx, miny, maxx, maxy = transform_bounds(
                "EPSG:4326", crs, *poly.bounds, densify_pts=21
            )
            pad = 500.0
            wb = (minx - pad, miny - pad, maxx + pad, maxy + pad)
            win = from_bounds(*wb, st.transform).intersection(
                rasterio.windows.Window(0, 0, st.width, st.height)
            )
            data = st.read(1, window=win)
            tr = st.window_transform(win)
            meta = st.meta.copy()
            meta.update(
                height=win.height,
                width=win.width,
                transform=tr,
                compress="deflate",
                tiled=True,
            )
            out_st = OUT_DIR / "ST_B10.tif"
            with rasterio.open(out_st, "w", **meta) as dst:
                dst.write(data, 1)
            print(f"Wrote {out_st} shape={data.shape}")

        with rasterio.open(qa_url) as qa:
            win2 = from_bounds(*wb, qa.transform).intersection(
                rasterio.windows.Window(0, 0, qa.width, qa.height)
            )
            qdata = qa.read(1, window=win2)
            qtr = qa.window_transform(win2)
            qmeta = qa.meta.copy()
            qmeta.update(
                height=win2.height,
                width=win2.width,
                transform=qtr,
                compress="deflate",
                tiled=True,
            )
            out_qa = OUT_DIR / "QA_PIXEL.tif"
            with rasterio.open(out_qa, "w", **qmeta) as dst:
                dst.write(qdata, 1)
            print(f"Wrote {out_qa} shape={qdata.shape}")


if __name__ == "__main__":
    main()
