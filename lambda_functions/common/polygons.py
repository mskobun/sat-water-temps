import json
from typing import Optional

from shapely.geometry import shape

# Module-level caches (persist across warm invocations)
_polygon_data = None
_aid_folder_mapping = None


def load_polygons():
    """Load and cache polygon data with bounding boxes.

    Returns a list of dicts with keys: aid, name, location, geometry, bbox.
    """
    global _polygon_data
    if _polygon_data is not None:
        return _polygon_data

    with open("static/polygons_new.geojson") as f:
        roi = json.load(f)

    _polygon_data = []
    for idx, feature in enumerate(roi["features"]):
        props = feature["properties"]
        geom = shape(feature["geometry"])
        bounds = geom.bounds  # (minx, miny, maxx, maxy)
        _polygon_data.append({
            "aid": idx + 1,
            "name": props["name"],
            "location": props.get("location", "lake"),
            "geometry": geom,
            "bbox": list(bounds),
        })
    return _polygon_data


def filter_polygons_for_feature(polygons: list, feature_filter) -> Optional[list]:
    """Return polygons matching ``feature_filter`` (AID int/str or case-insensitive name).

    Returns None if no match (so callers can distinguish "no filter" from "filter found nothing").
    """
    if feature_filter is None:
        return polygons
    if isinstance(feature_filter, int) or (
        isinstance(feature_filter, str) and str(feature_filter).isdigit()
    ):
        filtered = [p for p in polygons if p["aid"] == int(feature_filter)]
    else:
        filtered = [
            p for p in polygons if p["name"].lower() == str(feature_filter).lower()
        ]
    return filtered if filtered else None


def get_aid_folder_mapping():
    """Load and cache ROI polygon mapping. Returns {aid: (name, location)}.

    Persists across warm Lambda invocations.
    """
    global _aid_folder_mapping
    if _aid_folder_mapping is None:
        polygons = load_polygons()
        _aid_folder_mapping = {
            p["aid"]: (p["name"], p["location"]) for p in polygons
        }
    return _aid_folder_mapping
