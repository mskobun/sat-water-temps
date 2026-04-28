"""Catch-up window helpers for source initiators."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional, Sequence, Set, Tuple

from pystac_client import Client as STACClient

from d1 import get_setting, query_d1


DEFAULT_OVERLAP_DAYS = 3
DEFAULT_MAX_DAYS = 21
DEFAULT_LOOKBACK_DAYS = 90


@dataclass(frozen=True)
class CatchupSettings:
    enabled: bool
    overlap_days: int
    max_days: int


@dataclass(frozen=True)
class CatchupWindow:
    start_date: str
    end_date: str
    latest_processed_day: Optional[str]
    latest_catalog_day: Optional[str]
    overlap_days: int
    max_days: int
    enabled: bool
    reason: str


def feature_id_for_polygon(poly: dict) -> str:
    """Return the feature_id used by processors/D1 for a polygon record."""
    location = poly.get("location", "lake")
    name = poly["name"]
    return f"{name}/{location}" if location != "lake" else name


def combined_bbox(polygons: Sequence[dict]) -> Tuple[float, float, float, float]:
    """Return one bbox covering the supplied polygon records."""
    if not polygons:
        raise ValueError("No polygons supplied")
    minxs, minys, maxxs, maxys = zip(*(p["bbox"] for p in polygons))
    return (min(minxs), min(minys), max(maxxs), max(maxys))


def _parse_bool(value, default: bool = True) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _parse_int(value, default: int, min_value: int, max_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(parsed, max_value))


def get_catchup_settings() -> CatchupSettings:
    """Read and clamp catch-up settings from D1."""
    return CatchupSettings(
        enabled=_parse_bool(get_setting("catchup_enabled", default="true"), default=True),
        overlap_days=_parse_int(
            get_setting("catchup_overlap_days", default=DEFAULT_OVERLAP_DAYS),
            DEFAULT_OVERLAP_DAYS,
            0,
            30,
        ),
        max_days=_parse_int(
            get_setting("catchup_max_days", default=DEFAULT_MAX_DAYS),
            DEFAULT_MAX_DAYS,
            1,
            90,
        ),
    )


def latest_processed_day(source: str) -> Optional[str]:
    """Return the latest processed calendar day for a source from D1 metadata."""
    result = query_d1(
        "SELECT MAX(substr(date, 1, 10)) AS day FROM temperature_metadata WHERE source = ?",
        [source],
        fatal=False,
    )
    try:
        rows = result.get("result", [{}])[0].get("results", [])
        day = rows[0].get("day") if rows else None
        return str(day) if day else None
    except (IndexError, KeyError, TypeError):
        return None


def completed_feature_days(source: str, job_type: str, start_day: str, end_day: str) -> Set[Tuple[str, str]]:
    """Return completed ``(feature_id, YYYY-MM-DD)`` pairs for a source/window."""
    result = query_d1(
        """
        SELECT feature_id, substr(date, 1, 10) AS day
        FROM temperature_metadata
        WHERE source = ? AND substr(date, 1, 10) BETWEEN ? AND ?
        UNION
        SELECT feature_id, substr(date, 1, 10) AS day
        FROM processing_jobs
        WHERE job_type = ?
          AND status IN ('success', 'nodata')
          AND feature_id IS NOT NULL
          AND date IS NOT NULL
          AND substr(date, 1, 10) BETWEEN ? AND ?
        """,
        [source, start_day, end_day, job_type, start_day, end_day],
        fatal=False,
    )
    completed: Set[Tuple[str, str]] = set()
    try:
        rows = result.get("result", [{}])[0].get("results", [])
        for row in rows:
            feature_id = row.get("feature_id")
            day = row.get("day")
            if feature_id and day:
                completed.add((str(feature_id), str(day)))
    except (IndexError, KeyError, TypeError):
        pass
    return completed


def filter_uncompleted_bodies(
    bodies: Iterable[dict],
    *,
    source: str,
    job_type: str,
    start_day: str,
    end_day: str,
) -> Iterable[dict]:
    """Yield only bodies that are not already completed for source/feature/day."""
    completed = completed_feature_days(source, job_type, start_day, end_day)
    for body in bodies:
        feature_id = feature_id_for_polygon(body)
        day = body["date"][:10]
        if (feature_id, day) in completed:
            print(f"  Skip completed: {source} {feature_id} {day}")
            continue
        yield body


def calculate_catchup_window(
    *,
    latest_processed: Optional[str],
    latest_catalog: Optional[str],
    settings: CatchupSettings,
    fallback_start: str,
    fallback_end: str,
) -> CatchupWindow:
    """Resolve the default scan window for a scheduled source run."""
    if not settings.enabled:
        return CatchupWindow(
            fallback_start,
            fallback_end,
            latest_processed,
            latest_catalog,
            settings.overlap_days,
            settings.max_days,
            False,
            "catchup_disabled",
        )

    if latest_catalog is None:
        return CatchupWindow(
            fallback_start,
            fallback_end,
            latest_processed,
            latest_catalog,
            settings.overlap_days,
            settings.max_days,
            True,
            "no_catalog_date_fallback",
        )

    latest_catalog_date = date.fromisoformat(latest_catalog)
    if latest_processed:
        start = date.fromisoformat(latest_processed) - timedelta(days=settings.overlap_days)
    else:
        start = latest_catalog_date - timedelta(days=settings.max_days - 1)

    if start > latest_catalog_date:
        overlap = min(settings.overlap_days, settings.max_days - 1)
        start = latest_catalog_date - timedelta(days=overlap)

    max_end = start + timedelta(days=settings.max_days - 1)
    end = min(latest_catalog_date, max_end)

    return CatchupWindow(
        start.isoformat(),
        end.isoformat(),
        latest_processed,
        latest_catalog,
        settings.overlap_days,
        settings.max_days,
        True,
        "catchup",
    )


def latest_ecostress_cmr_day(
    *,
    bbox: Tuple[float, float, float, float],
    short_name: str,
    version: str,
) -> Optional[str]:
    """Return latest CMR granule day for ECOSTRESS over the monitored bbox."""
    params = {
        "short_name": short_name,
        "version": version,
        "bounding_box": ",".join(str(v) for v in bbox),
        "sort_key": "-start_date",
        "page_size": "1",
    }
    url = "https://cmr.earthdata.nasa.gov/search/granules.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "sat-water-temps-catchup"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    entries = body.get("feed", {}).get("entry", [])
    if not entries:
        return None
    start = entries[0].get("time_start")
    return str(start)[:10] if start else None


def latest_landsat_stac_day(
    *,
    bbox: Tuple[float, float, float, float],
    stac_url: str,
    collection: str,
    now: Optional[datetime] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Optional[str]:
    """Return latest Landsat scene day over the monitored bbox."""
    end_dt = now or datetime.now(timezone.utc)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=timezone.utc)
    start_dt = end_dt - timedelta(days=lookback_days)

    catalog = STACClient.open(stac_url)
    search = catalog.search(
        collections=[collection],
        bbox=list(bbox),
        datetime=f"{start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        max_items=500,
    )
    latest = None
    for item in search.items():
        if item.datetime and (latest is None or item.datetime > latest):
            latest = item.datetime
    return latest.strftime("%Y-%m-%d") if latest else None
