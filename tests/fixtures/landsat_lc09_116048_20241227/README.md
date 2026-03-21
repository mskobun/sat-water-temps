# Landsat C2 L2 ST window (Magat overlap)

Small GeoTIFF crops from **real** USGS Landsat Collection 2 Level-2 Surface Temperature products:

- Scene: `LC09_L2SP_116048_20241227_20241228_02_T1` (WRS 116/048)
- Bands: `ST_B10` (lwir11) and `QA_PIXEL`
- CRS: **EPSG:32651** (same as delivered COGs)
- Extent: bounding box of the **Magat lake** polygon (aid=1 in `static/polygons_new.geojson`), padded ~500 m in projected coordinates

Used by `tests/test_landsat_processor.py::TestLandsatProcessOneRecordFixture` to exercise `process_one_record` without S3 reads.

## Regenerate

Requires AWS credentials with **requester-pays** S3 access to `usgs-landsat`:

```bash
uv run python scripts/fetch_landsat_fixture.py
```
