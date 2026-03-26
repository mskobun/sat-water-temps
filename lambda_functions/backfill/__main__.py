"""CLI entry point for backfill operations.

Usage:
    uv run python -m backfill parquet                  # all features, run locally
    uv run python -m backfill parquet NamTheun2        # one feature, run locally
    uv run python -m backfill parquet --via-sqs        # fan out via SQS
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
from backfill.parquet import handle as handle_parquet
from backfill.regzip import handle as handle_regzip


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


def cmd_parquet(args):
    _run_backfill(args, "backfill:parquet", handle_parquet)


def cmd_regzip(args):
    _run_backfill(args, "backfill:regzip", handle_regzip)


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

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
