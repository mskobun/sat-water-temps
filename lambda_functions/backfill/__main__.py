"""CLI entry point for backfill operations.

Usage:
    uv run python -m backfill parquet                  # all features, run locally
    uv run python -m backfill parquet NamTheun2        # one feature, run locally
    uv run python -m backfill parquet --via-sqs        # fan out via SQS
    uv run python -m backfill raster_meta              # backfill D1 source_crs + transform from TIFs
    uv run python -m backfill raster_meta Magat --force
    uv run python -m backfill temp_stats               # backfill missing mean/median/std from CSVs
    uv run python -m backfill temp_stats Magat --force
"""

import argparse
import sys
import unittest.mock

# Stub out X-Ray before importing processor (it calls patch_all() at module level)
sys.modules["aws_xray_sdk"] = unittest.mock.MagicMock()
sys.modules["aws_xray_sdk.core"] = unittest.mock.MagicMock()

from dotenv import load_dotenv

load_dotenv()

from backfill.base import list_features, send_sqs_message
from backfill.nodata import handle as handle_nodata
from backfill.parquet import handle as handle_parquet
from backfill.raster_meta import handle as handle_raster_meta
from backfill.regzip import handle as handle_regzip
from backfill.temp_stats import handle as handle_temp_stats


def _run_backfill(args, msg_type, handler):
    features = args.features or list_features()
    if not features:
        print("No features found")
        return

    print(f"Backfilling {msg_type} for {len(features)} feature(s)")

    if args.via_sqs:
        for fid in features:
            send_sqs_message({"type": msg_type, "feature_id": fid})
            print(f"  Sent SQS message for {fid}")
        print(f"Done — sent {len(features)} SQS message(s)")
    else:
        for fid in features:
            try:
                handler({"feature_id": fid})
            except Exception as e:
                print(f"  ERROR processing {fid}: {e}")


def cmd_nodata(args):
    _run_backfill(args, "backfill:nodata", handle_nodata)


def cmd_parquet(args):
    _run_backfill(args, "backfill:parquet", handle_parquet)


def cmd_regzip(args):
    _run_backfill(args, "backfill:regzip", handle_regzip)


def cmd_raster_meta(args):
    features = args.features or list_features()
    if not features:
        print("No features found")
        return
    print(f"Backfilling backfill:raster_meta for {len(features)} feature(s)")
    if args.via_sqs:
        for fid in features:
            send_sqs_message(
                {"type": "backfill:raster_meta", "feature_id": fid, "force": args.force}
            )
            print(f"  Sent SQS message for {fid}")
        print(f"Done — sent {len(features)} SQS message(s)")
    else:
        for fid in features:
            try:
                handle_raster_meta({"feature_id": fid, "force": args.force})
            except Exception as e:
                print(f"  ERROR processing {fid}: {e}")


def cmd_temp_stats(args):
    features = args.features or list_features()
    if not features:
        print("No features found")
        return
    print(f"Backfilling backfill:temp_stats for {len(features)} feature(s)")
    if args.via_sqs:
        for fid in features:
            send_sqs_message(
                {"type": "backfill:temp_stats", "feature_id": fid, "force": args.force}
            )
            print(f"  Sent SQS message for {fid}")
        print(f"Done — sent {len(features)} SQS message(s)")
    else:
        for fid in features:
            try:
                handle_temp_stats({"feature_id": fid, "force": args.force})
            except Exception as e:
                print(f"  ERROR processing {fid}: {e}")


def main():
    parser = argparse.ArgumentParser(prog="backfill", description="Backfill data operations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_parquet = subparsers.add_parser("parquet", help="Generate Parquet from existing CSVs")
    p_parquet.add_argument("features", nargs="*", help="Feature IDs (default: all)")
    p_parquet.add_argument("--via-sqs", action="store_true", help="Fan out via SQS instead of running locally")
    p_parquet.set_defaults(func=cmd_parquet)

    p_regzip = subparsers.add_parser("regzip", help="Re-upload CSVs with ContentEncoding:gzip")
    p_regzip.add_argument("features", nargs="*", help="Feature IDs (default: all)")
    p_regzip.add_argument("--via-sqs", action="store_true", help="Fan out via SQS instead of running locally")
    p_regzip.set_defaults(func=cmd_regzip)

    p_geom = subparsers.add_parser(
        "raster_meta",
        help="Backfill source_crs and affine transform from GeoTIFFs in R2",
    )
    p_geom.add_argument("features", nargs="*", help="Feature IDs (default: all)")
    p_geom.add_argument("--via-sqs", action="store_true", help="Fan out via SQS instead of running locally")
    p_geom.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing source_crs/transform columns",
    )
    p_geom.set_defaults(func=cmd_raster_meta)

    p_temp_stats = subparsers.add_parser(
        "temp_stats",
        help="Backfill mean/median/std temperature stats from CSVs",
    )
    p_temp_stats.add_argument("features", nargs="*", help="Feature IDs (default: all)")
    p_temp_stats.add_argument("--via-sqs", action="store_true", help="Fan out via SQS instead of running locally")
    p_temp_stats.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing mean/median/std values",
    )
    p_temp_stats.set_defaults(func=cmd_temp_stats)

    p_nodata = subparsers.add_parser(
        "nodata",
        help="Reclassify zero-data observations and clean up stale R2/D1 data",
    )
    p_nodata.add_argument("features", nargs="*", help="Feature IDs (default: all)")
    p_nodata.add_argument("--via-sqs", action="store_true", help="Fan out via SQS instead of running locally")
    p_nodata.set_defaults(func=cmd_nodata)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
