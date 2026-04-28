#!/usr/bin/env python3
"""Invoke prod initiator Lambdas month-by-month for backfills.

Examples:
    uv run python scripts/backfill_prod_monthly.py --years-back 2
    uv run python scripts/backfill_prod_monthly.py --start-date 2024-04-21 --end-date 2026-04-21
    uv run python scripts/backfill_prod_monthly.py --source ecostress --years-back 2 --dry-run
"""

from __future__ import annotations

import argparse
import json
import time
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

import boto3
from botocore.config import Config


DEFAULT_REGION = "us-west-2"
DEFAULT_FUNCTIONS = {
    "ecostress": "eco-water-temps-initiator",
    "landsat": "eco-water-temps-landsat-initiator",
}


@dataclass(frozen=True)
class MonthChunk:
    start_date: date
    end_date: date


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill prod initiators month-by-month via Lambda invoke."
    )
    parser.add_argument(
        "--start-date",
        help="Inclusive start date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--end-date",
        help="Inclusive end date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--years-back",
        type=int,
        help="Alternative to --start-date: start this many years before --end-date (or today).",
    )
    parser.add_argument(
        "--source",
        choices=("ecostress", "landsat", "both"),
        default="both",
        help="Which source(s) to invoke. Default: both.",
    )
    parser.add_argument(
        "--region",
        default=DEFAULT_REGION,
        help=f"AWS region for Lambda invoke. Default: {DEFAULT_REGION}.",
    )
    parser.add_argument(
        "--triggered-by",
        default="manual-cli",
        help="Value recorded in D1 as triggered_by. Default: manual-cli.",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=1.0,
        help="Sleep between invokes to avoid hammering the initiators. Default: 1.0.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the invokes without calling AWS.",
    )
    parser.add_argument(
        "--request-response",
        action="store_true",
        help="Wait for each Lambda to finish instead of invoking asynchronously.",
    )
    return parser.parse_args()


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def subtract_years_safe(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        # Handle Feb 29 by clamping to the last valid day for that month.
        target_year = value.year - years
        last_day = monthrange(target_year, value.month)[1]
        return value.replace(year=target_year, day=min(value.day, last_day))


def resolve_date_range(args: argparse.Namespace) -> tuple[date, date]:
    if args.start_date and args.years_back is not None:
        raise SystemExit("Use either --start-date or --years-back, not both.")

    if not args.start_date and args.years_back is None:
        raise SystemExit("Provide --start-date or --years-back.")

    end_date = parse_iso_date(args.end_date) if args.end_date else date.today()

    if args.start_date:
        start_date = parse_iso_date(args.start_date)
    else:
        start_date = subtract_years_safe(end_date, args.years_back)

    if end_date < start_date:
        raise SystemExit("--end-date must be on or after --start-date.")

    return start_date, end_date


def month_chunks(start_date: date, end_date: date) -> Iterable[MonthChunk]:
    current = start_date
    while current <= end_date:
        last_day = monthrange(current.year, current.month)[1]
        chunk_end = date(current.year, current.month, last_day)
        if chunk_end > end_date:
            chunk_end = end_date
        yield MonthChunk(start_date=current, end_date=chunk_end)
        current = chunk_end + timedelta(days=1)


def sources_for(selection: str) -> list[str]:
    if selection == "both":
        return ["ecostress", "landsat"]
    return [selection]


def build_payload(source: str, chunk: MonthChunk, triggered_by: str) -> dict[str, str]:
    label = "ECOSTRESS" if source == "ecostress" else "Landsat"
    start_text = chunk.start_date.isoformat()
    end_text = chunk.end_date.isoformat()
    return {
        "start_date": start_text,
        "end_date": end_text,
        "trigger_type": "manual",
        "triggered_by": triggered_by,
        "description": f"{label} monthly backfill {start_text} to {end_text}",
    }


def invoke_chunk(
    client,
    function_name: str,
    payload: dict[str, str],
    dry_run: bool,
    request_response: bool,
) -> None:
    payload_text = json.dumps(payload)
    if dry_run:
        print(f"[dry-run] {function_name} <= {payload_text}")
        return

    response = client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse" if request_response else "Event",
        Payload=payload_text.encode("utf-8"),
    )
    status_code = response.get("StatusCode")
    if request_response:
        response_payload = response["Payload"].read().decode("utf-8")
        print(f"[invoke] {function_name} -> HTTP {status_code} :: {response_payload}")
    else:
        print(f"[invoke] {function_name} -> HTTP {status_code} :: accepted")

    function_error = response.get("FunctionError")
    if function_error:
        raise RuntimeError(f"{function_name} returned FunctionError={function_error}")


def main() -> int:
    args = parse_args()
    start_date, end_date = resolve_date_range(args)
    chunks = list(month_chunks(start_date, end_date))
    selected_sources = sources_for(args.source)

    print(
        f"Preparing {len(chunks)} monthly chunk(s) from {start_date.isoformat()} to {end_date.isoformat()} "
        f"for source(s): {', '.join(selected_sources)}"
    )

    client = None if args.dry_run else boto3.client(
        "lambda",
        region_name=args.region,
        config=Config(
            read_timeout=900 if args.request_response else 60,
            connect_timeout=10,
            retries={"max_attempts": 10, "mode": "standard"},
        ),
    )

    for chunk in chunks:
        for source in selected_sources:
            function_name = DEFAULT_FUNCTIONS[source]
            payload = build_payload(source, chunk, args.triggered_by)
            invoke_chunk(
                client,
                function_name,
                payload,
                args.dry_run,
                args.request_response,
            )
            if not args.dry_run and args.pause_seconds > 0:
                time.sleep(args.pause_seconds)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
