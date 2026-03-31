import io
from datetime import datetime, timezone
from typing import Dict

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from common.dates import to_parquet_date_utc


def parquet_date_type() -> pa.DataType:
    """Arrow type for canonical feature Parquet `date` column (microsecond UTC)."""
    return pa.timestamp("us", tz="UTC")


def parquet_feature_schema() -> pa.Schema:
    """Canonical schema for per-feature Parquet (ECOSTRESS + Landsat)."""
    return pa.schema(
        [
            pa.field("longitude", pa.float64()),
            pa.field("latitude", pa.float64()),
            pa.field("temperature", pa.float32()),
            pa.field("date", parquet_date_type()),
            pa.field("row", pa.int32(), nullable=True),
            pa.field("col", pa.int32(), nullable=True),
        ]
    )


def _row_group_first_date_key(tbl: pa.Table):
    """First row `date` instant for deduplication (UTC). Expects timestamp column after migration."""
    col = tbl.column("date")
    if tbl.num_rows == 0:
        return None
    scalar = col[0]
    if not scalar.is_valid:
        return None
    py = scalar.as_py()
    if py is None:
        return None
    if not isinstance(py, datetime):
        raise ValueError(
            "Parquet row group has non-timestamp `date`; re-run parquet backfill to migrate."
        )
    if py.tzinfo is None:
        return py.replace(tzinfo=timezone.utc)
    return py.astimezone(timezone.utc)


def align_parquet_table_to_feature_schema(tbl: pa.Table) -> pa.Table:
    """Cast older physical types (e.g. float32 lon/lat, missing row/col) to the current schema."""
    target = parquet_feature_schema()
    n = tbl.num_rows
    out: Dict[str, pa.Array] = {}
    for field in target:
        name = field.name
        if name in tbl.column_names:
            col = tbl.column(name)
            if col.type != field.type:
                col = pc.cast(col, field.type)
            out[name] = col
        elif name in ("row", "col"):
            out[name] = pa.array([None] * n, type=field.type)
        else:
            raise ValueError(f"Missing required Parquet column {name}")
    return pa.table(out, schema=target)


def upload_parquet_to_r2(s3_client, bucket_name, parquet_key, df, date):
    """Append data to a per-year, sorted Parquet file in R2.

    The caller passes a base key (without year suffix). This function derives
    the year from `date` and writes to `{base}_YYYY.parquet`.

    All rows for a year file are concatenated into one table sorted by
    (longitude, latitude) for optimal compression and fast full-file fetches.
    If the file already exists, existing data is merged (replacing any rows
    for the same date) before sorting and writing.

    Returns the actual year-suffixed key used.
    """
    schema = parquet_feature_schema()
    ts_type = parquet_date_type()
    date_utc = to_parquet_date_utc(date)

    # Derive year-suffixed key
    year = date_utc.year
    year_key = parquet_key.replace(".parquet", f"_{year}.parquet")

    new_table = pa.table(
        {
            "longitude": pa.array(df["longitude"].values, type=pa.float64()),
            "latitude": pa.array(df["latitude"].values, type=pa.float64()),
            "temperature": pa.array(df["LST_filter"].values, type=pa.float32()),
            "date": pa.array([date_utc] * len(df), type=ts_type),
            "row": pa.array(df["row"].astype("int32").values, type=pa.int32()),
            "col": pa.array(df["col"].astype("int32").values, type=pa.int32()),
        },
        schema=schema,
    )

    # Download existing year Parquet if it exists, to merge
    existing_tables = []
    try:
        resp = s3_client.get_object(Bucket=bucket_name, Key=year_key)
        existing_buf = resp["Body"].read()
        existing_pf = pq.ParquetFile(pa.BufferReader(existing_buf))
        for i in range(existing_pf.metadata.num_row_groups):
            rg_table = existing_pf.read_row_group(i)
            # Skip rows for the same date (we're replacing)
            rg_key = _row_group_first_date_key(rg_table)
            if rg_key == date_utc:
                continue
            existing_tables.append(align_parquet_table_to_feature_schema(rg_table))
    except Exception as e:
        err_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if err_code not in ("NoSuchKey", "404"):
            print(f"Warning: could not read existing Parquet {year_key}: {e}")

    # Concatenate all tables, sort by (longitude, latitude), write as one sorted file
    all_tables = existing_tables + [new_table]
    combined = pa.concat_tables(all_tables)
    sort_indices = pc.sort_indices(combined, sort_keys=[("longitude", "ascending"), ("latitude", "ascending")])
    combined = combined.take(sort_indices)

    buf = io.BytesIO()
    pq.write_table(combined, buf, compression="zstd")

    buf.seek(0)
    s3_client.put_object(
        Bucket=bucket_name, Key=year_key, Body=buf.getvalue(),
        ContentType="application/octet-stream",
    )
    print(f"Uploaded Parquet to {year_key} ({combined.num_rows:,} rows, {len(buf.getvalue()):,} bytes)")
    return year_key
