"""Generate maximally compressed PMTiles from CSV temperature data.

Fetches CSV from R2 (or reads local file), builds point + square GeoJSON,
pipes through tippecanoe with aggressive compression, outputs .pmtiles.

Usage:
    # Single observation from R2
    uv run python scripts/generate_pmtiles.py --feature Sirindhorn --date '2026-02-22T00:00:00'

    # From local CSV (must supply pixel sizes)
    uv run python scripts/generate_pmtiles.py --csv path/to/file.csv --pixel-size-x 0.00027 --pixel-size-y 0.00027

    # All observations for a feature
    uv run python scripts/generate_pmtiles.py --feature Sirindhorn --all

    # Upload result to R2
    uv run python scripts/generate_pmtiles.py --feature Sirindhorn --date '2026-02-22T00:00:00' --upload
"""

import argparse
import csv
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

import boto3
from dotenv import load_dotenv

load_dotenv()

DB_PATH = ".wrangler/state/v3/d1/miniflare-D1DatabaseObject/4096e3fb508d875520342c6f716b66d65fa16296ae16d7c2d6d40eba30883e65.sqlite"

R2_ENDPOINT = os.environ.get("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.environ.get("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.environ.get("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.environ.get("R2_BUCKET_NAME", "multitifs")


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def fetch_csv_from_r2(csv_path: str) -> str:
    """Download CSV from R2 and return as string."""
    client = get_r2_client()
    obj = client.get_object(Bucket=R2_BUCKET_NAME, Key=csv_path)
    return obj["Body"].read().decode("utf-8")


def parse_csv(csv_text: str) -> list[dict]:
    """Parse CSV into list of {lng, lat, temperature}."""
    reader = csv.DictReader(io.StringIO(csv_text))
    points = []
    for row in reader:
        lng = float(row.get("longitude") or row.get("x", 0))
        lat = float(row.get("latitude") or row.get("y", 0))
        temp = float(row.get("LST_filter") or row.get("temperature", 0))
        points.append({"lng": lng, "lat": lat, "temperature": temp})
    return points


def write_geojson_files(
    points: list[dict], pixel_size_x: float | None, pixel_size_y: float | None, tmpdir: str
) -> tuple[str, str | None]:
    """Write line-delimited GeoJSON to temp files for tippecanoe.

    Returns (points_file, squares_file_or_none).
    Coordinates rounded to 6 decimal places (~0.1m).
    Temperature rounded to 2 decimal places.
    """
    half_x = abs(pixel_size_x) / 2 if pixel_size_x else None
    half_y = abs(pixel_size_y) / 2 if pixel_size_y else None

    points_path = os.path.join(tmpdir, "points.geojson.nl")
    squares_path = os.path.join(tmpdir, "squares.geojson.nl") if half_x and half_y else None

    with open(points_path, "w") as pf, (open(squares_path, "w") if squares_path else open(os.devnull, "w")) as sf:
        for p in points:
            lng = round(p["lng"], 6)
            lat = round(p["lat"], 6)
            temp = round(p["temperature"], 1)

            feat = {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lng, lat]},
                "properties": {"temperature": temp},
            }
            pf.write(json.dumps(feat, separators=(",", ":")) + "\n")

            if half_x and half_y:
                sq = {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[
                            [round(lng - half_x, 6), round(lat - half_y, 6)],
                            [round(lng + half_x, 6), round(lat - half_y, 6)],
                            [round(lng + half_x, 6), round(lat + half_y, 6)],
                            [round(lng - half_x, 6), round(lat + half_y, 6)],
                            [round(lng - half_x, 6), round(lat - half_y, 6)],
                        ]],
                    },
                    "properties": {"temperature": temp},
                }
                sf.write(json.dumps(sq, separators=(",", ":")) + "\n")

    return points_path, squares_path


def run_tippecanoe(
    points_file: str,
    squares_file: str | None,
    output_path: str,
    min_zoom: int = 0,
    max_zoom: int = 14,
):
    """Run tippecanoe with maximum compression settings.

    Uses separate layer inputs so tippecanoe preserves layer names.
    Points get --drop-densest-as-needed to thin at low zoom.
    Squares only appear at z8+ where they're visible.
    """
    cmd = [
        "tippecanoe",
        "-o", output_path,
        "--force",
        f"-z{max_zoom}",
        f"-Z{min_zoom}",
        "--no-tile-size-limit",
        # Coordinate precision: fewer bits = smaller tiles
        "--full-detail=10",         # 1024 coordinate precision at max zoom
        "--low-detail=8",           # 256 at low zoom
        "--minimum-detail=6",       # 64 at very low zoom
        # Points layer: drop densest at low zoom for reasonable tile sizes
        "-L", json.dumps({
            "file": points_file,
            "layer": "temperature-points",
        }),
    ]

    if squares_file:
        cmd.extend([
            # Squares layer: z10+ only (invisible before due to opacity fade)
            "-L", json.dumps({
                "file": squares_file,
                "layer": "temperature-squares",
                "minzoom": 10,
            }),
        ])

    print(f"Running tippecanoe...")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        print(f"tippecanoe stderr:\n{stderr.decode()}", file=sys.stderr)
        sys.exit(1)

    if stderr:
        # tippecanoe prints progress to stderr
        for line in stderr.decode().splitlines():
            if "tile" in line.lower() or "layer" in line.lower() or "feature" in line.lower():
                print(f"  {line}")

    size = os.path.getsize(output_path)
    print(f"Output: {output_path} ({size:,} bytes, {size/1024/1024:.2f} MB)")
    return output_path


def upload_to_r2(local_path: str, r2_key: str):
    """Upload PMTiles file to R2."""
    client = get_r2_client()
    print(f"Uploading to R2: {r2_key}")
    client.upload_file(
        local_path,
        R2_BUCKET_NAME,
        r2_key,
        ExtraArgs={"ContentType": "application/vnd.pmtiles"},
    )
    print(f"Uploaded: {r2_key}")


def get_observations(feature_id: str, date: str | None = None):
    """Get observation metadata from local D1 SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if date:
        cur.execute(
            "SELECT feature_id, date, csv_path, pixel_size, pixel_size_x "
            "FROM temperature_metadata WHERE feature_id = ? AND date = ?",
            (feature_id, date),
        )
    else:
        cur.execute(
            "SELECT feature_id, date, csv_path, pixel_size, pixel_size_x "
            "FROM temperature_metadata WHERE feature_id = ? ORDER BY date",
            (feature_id,),
        )

    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def pmtiles_r2_key(feature_id: str, date: str) -> str:
    """R2 key for a PMTiles file."""
    # Sanitize date for filename (replace colons)
    safe_date = date.replace(":", "")
    source_prefix = "LANDSAT" if "T00:00:00" in date else "ECO"
    return f"{source_prefix}/{feature_id}/lake/{feature_id}_{safe_date}.pmtiles"


def process_observation(obs: dict, upload: bool = False, output_dir: str = "output"):
    """Generate PMTiles for a single observation."""
    feature_id = obs["feature_id"]
    date = obs["date"]
    csv_path = obs["csv_path"]
    pixel_size_y = obs["pixel_size"]
    pixel_size_x = obs["pixel_size_x"] or pixel_size_y

    print(f"\n--- {feature_id} / {date} ---")
    print(f"CSV: {csv_path}")
    print(f"Pixel size: X={pixel_size_x}, Y={pixel_size_y}")

    # Fetch CSV
    csv_text = fetch_csv_from_r2(csv_path)
    points = parse_csv(csv_text)
    print(f"Points: {len(points):,}")

    if not points:
        print("No points, skipping")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        points_file, squares_file = write_geojson_files(points, pixel_size_x, pixel_size_y, tmpdir)

        # Output path
        os.makedirs(output_dir, exist_ok=True)
        safe_date = date.replace(":", "")
        out_path = os.path.join(output_dir, f"{feature_id}_{safe_date}.pmtiles")

        run_tippecanoe(points_file, squares_file, out_path)

    # Upload if requested
    if upload:
        r2_key = pmtiles_r2_key(feature_id, date)
        upload_to_r2(out_path, r2_key)


def process_csv_file(csv_file: str, pixel_size_x: float, pixel_size_y: float, output: str):
    """Generate PMTiles from a local CSV file."""
    with open(csv_file) as f:
        csv_text = f.read()

    points = parse_csv(csv_text)
    print(f"Points: {len(points):,}")

    if not points:
        print("No points")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        points_file, squares_file = write_geojson_files(points, pixel_size_x, pixel_size_y, tmpdir)
        run_tippecanoe(points_file, squares_file, output)


def main():
    parser = argparse.ArgumentParser(description="Generate compressed PMTiles from CSV temperature data")
    parser.add_argument("--feature", help="Feature ID (e.g., Sirindhorn)")
    parser.add_argument("--date", help="Observation date (e.g., 2026-02-22T00:00:00)")
    parser.add_argument("--all", action="store_true", help="Process all observations for the feature")
    parser.add_argument("--csv", help="Local CSV file path (instead of R2)")
    parser.add_argument("--pixel-size-x", type=float, help="Pixel size X (longitude degrees)")
    parser.add_argument("--pixel-size-y", type=float, help="Pixel size Y (latitude degrees)")
    parser.add_argument("--output", default="output", help="Output directory or file path")
    parser.add_argument("--upload", action="store_true", help="Upload to R2 after generation")
    args = parser.parse_args()

    if args.csv:
        if not args.pixel_size_x or not args.pixel_size_y:
            parser.error("--pixel-size-x and --pixel-size-y required with --csv")
        out = args.output if args.output.endswith(".pmtiles") else os.path.join(args.output, "output.pmtiles")
        process_csv_file(args.csv, args.pixel_size_x, args.pixel_size_y, out)
    elif args.feature:
        if args.all:
            observations = get_observations(args.feature)
        elif args.date:
            observations = get_observations(args.feature, args.date)
        else:
            parser.error("--date or --all required with --feature")
            return

        if not observations:
            print(f"No observations found for {args.feature}" + (f" on {args.date}" if args.date else ""))
            return

        print(f"Found {len(observations)} observation(s)")
        for obs in observations:
            process_observation(obs, upload=args.upload, output_dir=args.output)
    else:
        parser.error("--feature or --csv required")


if __name__ == "__main__":
    main()
