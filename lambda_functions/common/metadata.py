import json
import time
from typing import Dict

from aws_xray_sdk.core import xray_recorder

from common.dates import to_iso_datetime
from d1 import query_d1


def affine_transform_to_dict(affine) -> Dict[str, float]:
    """Serialize rasterio Affine to dict keys a..f for D1 columns."""
    return {
        "a": float(affine.a),
        "b": float(affine.b),
        "c": float(affine.c),
        "d": float(affine.d),
        "e": float(affine.e),
        "f": float(affine.f),
    }


def insert_metadata_to_d1(
    feature_id: str,
    date: str,
    metadata: Dict,
    csv_r2_key: str,
    tif_r2_key: str,
    png_r2_keys: Dict[str, str],
    source: str = "ecostress",
    parquet_path: str = None,
):
    """Insert only metadata into D1 (temperature data stays in R2).

    query_d1 raises on failure by default, so no manual success checks needed.
    """
    # Use actual R2 paths from upload
    csv_path = csv_r2_key
    tif_path = tif_r2_key
    # Store base path (without scale suffix) so API can append _${scale}.png
    full_png_path = png_r2_keys.get("relative", png_r2_keys.get("fixed", ""))
    png_path = full_png_path.replace("_relative.png", "").replace("_fixed.png", "")

    # Normalize date to ISO datetime at write boundary
    date = to_iso_datetime(date)

    # Insert/update feature record FIRST (to satisfy foreign key constraint)
    name, location = (
        feature_id.split("/") if "/" in feature_id else (feature_id, "lake")
    )
    feature_sql = """
    INSERT INTO features (id, name, location, latest_date, last_updated)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        latest_date = CASE
            WHEN excluded.latest_date > COALESCE(latest_date, '') THEN excluded.latest_date
            ELSE latest_date
        END,
        last_updated = excluded.last_updated
    """

    feature_params = [feature_id, name, location, date, int(time.time())]

    with xray_recorder.capture("d1_insert_feature") as subsegment:
        if subsegment is not None:
            subsegment.put_metadata("feature_id", feature_id)
        query_d1(feature_sql, feature_params)

    # Now insert metadata with file paths (after feature exists)
    meta_sql = """
    INSERT OR REPLACE INTO temperature_metadata
    (feature_id, date, min_temp, max_temp, mean_temp, median_temp, std_dev,
     data_points, water_pixel_count, land_pixel_count, wtoff,
     csv_path, tif_path, png_path, filter_stats, source, pixel_size, pixel_size_x,
     parquet_path, source_crs, transform_a, transform_b, transform_c, transform_d,
     transform_e, transform_f)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    # Serialize filter_stats to JSON
    filter_stats_json = json.dumps(metadata.get("filter_stats", {}))

    tf = metadata.get("transform") or {}
    meta_params = [
        feature_id,
        date,
        metadata.get("min_temp"),
        metadata.get("max_temp"),
        metadata.get("mean_temp"),
        metadata.get("median_temp"),
        metadata.get("std_dev"),
        metadata.get("data_points", 0),
        metadata.get("water_pixel_count", 0),
        metadata.get("land_pixel_count", 0),
        1 if metadata.get("wtoff", False) else 0,
        csv_path,
        tif_path,
        png_path,
        filter_stats_json,
        source,
        metadata.get("pixel_size"),
        metadata.get("pixel_size_x"),
        parquet_path,
        metadata.get("source_crs"),
        tf.get("a"),
        tf.get("b"),
        tf.get("c"),
        tf.get("d"),
        tf.get("e"),
        tf.get("f"),
    ]
    with xray_recorder.capture("d1_insert_temperature_metadata") as subsegment:
        if subsegment is not None:
            subsegment.put_metadata("feature_id", feature_id)
            subsegment.put_metadata("date", date)
            subsegment.put_metadata(
                "has_filter_stats", bool(filter_stats_json and filter_stats_json != "{}")
            )
        query_d1(meta_sql, meta_params)

    print(f"✓ Inserted metadata to D1 with R2 paths")
