"""Backfill handler: generate Parquet files from existing CSV.gz files in R2.

SQS message: {"type": "backfill:parquet", "feature_id": "NamTheun2"}

For each feature, looks up csv_path→date from D1, downloads the CSVs,
extracts longitude/latitude/temperature columns, and writes a single
Parquet file with one row group per date (using the full D1 timestamp).

When CSV rows lack ``row``/``col`` but ``tif_path`` is set in D1, pixel
indices are derived from the GeoTIFF (WGS84 → raster CRS, then inverse
affine) so Landsat legacy CSVs still get stable quad geometry.
"""

import io
import os
import tempfile
from collections import defaultdict

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import rasterio
from rasterio.transform import rowcol
from rasterio.warp import transform as warp_xy

from backfill.base import (
    get_s3_client,
    get_bucket_name,
    get_csv_date_tif_rows,
    update_parquet_path_in_d1,
)
from common.parquet import parquet_date_type, parquet_feature_schema
from common.dates import to_parquet_date_utc


def _csv_rowcol_complete(df_clean: pd.DataFrame, row_col: str | None, col_col: str | None) -> bool:
    if not row_col or not col_col:
        return False
    return bool((df_clean[row_col].notna() & df_clean[col_col].notna()).all())


def derive_row_col_from_tif(s3, bucket: str, tif_key: str, lons, lats) -> tuple[list[int | None], list[int | None]] | None:
    """Map WGS84 lon/lat to raster row/col using the filter GeoTIFF. Returns None on failure."""
    if not tif_key:
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
            tmp_path = tmp.name
        s3.download_file(bucket, tif_key, tmp_path)

        with rasterio.open(tmp_path) as src:
            if not src.crs:
                print(f"[backfill:parquet] TIF has no CRS, cannot derive row/col: {tif_key}")
                return None
            h, w = src.height, src.width
            lons_a = np.asarray(lons, dtype=np.float64).ravel()
            lats_a = np.asarray(lats, dtype=np.float64).ravel()
            n = lons_a.size
            row_py: list[int | None] = [None] * n
            col_py: list[int | None] = [None] * n
            chunk = 65536
            crs_wgs84 = "EPSG:4326"
            dst_crs = src.crs
            for start in range(0, n, chunk):
                end = min(start + chunk, n)
                sl = slice(start, end)
                xs, ys = warp_xy(
                    crs_wgs84,
                    dst_crs,
                    lons_a[sl].tolist(),
                    lats_a[sl].tolist(),
                )
                rows, cols = rowcol(src.transform, xs, ys)
                ri = np.asarray(rows, dtype=np.int64).ravel()
                ci = np.asarray(cols, dtype=np.int64).ravel()
                for i in range(end - start):
                    r, c = int(ri[i]), int(ci[i])
                    idx = start + i
                    if 0 <= r < h and 0 <= c < w:
                        row_py[idx] = r
                        col_py[idx] = c
        return row_py, col_py
    except Exception as ex:
        print(f"[backfill:parquet] derive row/col failed for {tif_key}: {ex}")
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def handle(body: dict):
    """Handle a backfill:parquet message for one feature."""
    feature_id = body["feature_id"]
    if "/" in feature_id:
        name, location = feature_id.split("/", 1)
    else:
        name, location = feature_id, "lake"

    print(f"[backfill:parquet][{feature_id}] Starting Parquet backfill")

    s3 = get_s3_client()
    bucket = get_bucket_name()

    csv_rows = get_csv_date_tif_rows(feature_id)
    if not csv_rows:
        print(f"[backfill:parquet][{feature_id}] No CSV records in D1, skipping")
        return

    print(f"[backfill:parquet][{feature_id}] Found {len(csv_rows)} CSV record(s) in D1")

    schema = parquet_feature_schema()

    # Build one Parquet file per source prefix (ECO vs LANDSAT)
    keys_by_prefix: dict[str, list[tuple[str, str, str | None]]] = {}
    for rec in csv_rows:
        csv_path = rec["csv_path"]
        date = rec["date"]
        tif_path = rec.get("tif_path")
        prefix = "LANDSAT" if csv_path.startswith("LANDSAT/") else "ECO"
        keys_by_prefix.setdefault(prefix, []).append((csv_path, date, tif_path))

    for prefix, entries in keys_by_prefix.items():
        # Group tables by year for per-year Parquet files
        tables_by_year: dict[int, list[pa.Table]] = defaultdict(list)
        dates_by_year: dict[int, list[str]] = defaultdict(list)

        for csv_path, date, tif_path in sorted(entries, key=lambda e: e[1]):
            try:
                resp = s3.get_object(Bucket=bucket, Key=csv_path)
                csv_text = resp["Body"].read().decode("utf-8")
                df = pd.read_csv(io.StringIO(csv_text))

                # Find the right columns
                lng_col = next((c for c in df.columns if c in ("longitude", "x")), None)
                lat_col = next((c for c in df.columns if c in ("latitude", "y")), None)
                temp_col = next(
                    (c for c in df.columns if c in ("LST_filter", "temperature")), None
                )
                row_col = "row" if "row" in df.columns else None
                col_col = "col" if "col" in df.columns else None

                if not all([lng_col, lat_col, temp_col]):
                    print(f"[backfill:parquet][{feature_id}] Skipping {csv_path}: missing columns")
                    continue

                use_cols = [lng_col, lat_col, temp_col]
                if row_col:
                    use_cols.append(row_col)
                if col_col:
                    use_cols.append(col_col)
                df_clean = df[use_cols].dropna(subset=[lng_col, lat_col, temp_col])
                if df_clean.empty:
                    print(f"[backfill:parquet][{feature_id}] Skipping {csv_path}: no valid rows")
                    continue

                n = len(df_clean)
                if _csv_rowcol_complete(df_clean, row_col, col_col):
                    row_arr = pa.array(df_clean[row_col].astype("int32").values, type=pa.int32())
                    col_arr = pa.array(df_clean[col_col].astype("int32").values, type=pa.int32())
                else:
                    derived = derive_row_col_from_tif(
                        s3,
                        bucket,
                        tif_path or "",
                        df_clean[lng_col].values,
                        df_clean[lat_col].values,
                    )
                    if derived is not None:
                        row_py, col_py = derived
                        print(
                            f"[backfill:parquet][{feature_id}] Derived row/col from TIF {tif_path} "
                            f"for {csv_path} ({n} points)"
                        )
                        row_arr = pa.array(row_py, type=pa.int32())
                        col_arr = pa.array(col_py, type=pa.int32())
                    else:
                        row_arr = pa.array([None] * n, type=pa.int32())
                        col_arr = pa.array([None] * n, type=pa.int32())
                        if tif_path:
                            print(
                                f"[backfill:parquet][{feature_id}] row/col missing in CSV and "
                                f"TIF derivation failed for {csv_path}"
                            )

                date_utc = to_parquet_date_utc(date)
                ts_type = parquet_date_type()
                table = pa.table(
                    {
                        "longitude": pa.array(df_clean[lng_col].values, type=pa.float64()),
                        "latitude": pa.array(df_clean[lat_col].values, type=pa.float64()),
                        "temperature": pa.array(df_clean[temp_col].values, type=pa.float32()),
                        "date": pa.array([date_utc] * n, type=ts_type),
                        "row": row_arr,
                        "col": col_arr,
                    },
                    schema=schema,
                )

                year = date_utc.year
                tables_by_year[year].append(table)
                dates_by_year[year].append(date)
            except Exception as e:
                print(f"[backfill:parquet][{feature_id}] Error processing {csv_path}: {e}")
                continue

        if not tables_by_year:
            print(f"[backfill:parquet][{feature_id}] No valid dates for {prefix}, skipping")
            continue

        # Write one sorted Parquet file per year
        for year in sorted(tables_by_year.keys()):
            year_tables = tables_by_year[year]
            year_dates = dates_by_year[year]
            parquet_key = f"{prefix}/{name}/{location}/{name}_{location}_{year}.parquet"

            # Concatenate all tables for this year, sort by (longitude, latitude)
            combined = pa.concat_tables(year_tables)
            sort_indices = pc.sort_indices(combined, sort_keys=[("longitude", "ascending"), ("latitude", "ascending")])
            combined = combined.take(sort_indices)

            buf = io.BytesIO()
            pq.write_table(combined, buf, compression="zstd")

            buf.seek(0)
            s3.put_object(
                Bucket=bucket, Key=parquet_key, Body=buf.getvalue(),
                ContentType="application/octet-stream",
            )
            print(
                f"[backfill:parquet][{feature_id}] Uploaded {parquet_key} "
                f"({combined.num_rows:,} rows, {len(buf.getvalue()):,} bytes)"
            )

            # Update D1 parquet_path for each date in this year
            for date in year_dates:
                update_parquet_path_in_d1(feature_id, date, parquet_key)

        total_dates = sum(len(d) for d in dates_by_year.values())
        print(f"[backfill:parquet][{feature_id}] Updated {total_dates} D1 records across {len(tables_by_year)} year file(s)")
