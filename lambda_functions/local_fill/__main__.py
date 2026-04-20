"""Run ECOSTRESS or Landsat processors in-process for one feature and date range.

Examples::

    cd lambda_functions
    uv run python -m local_fill --source ecostress --feature Magat \\
        --start-date 2024-12-01 --end-date 2024-12-03

Local Wrangler D1/R2 (repo root is found by walking up from cwd for ``wrangler.toml`` + ``static/``)::

    cd lambda_functions
    uv run python -m local_fill --runtime local --source landsat --feature Magat \\
        --start-date 2024-12-27 --end-date 2024-12-27

Override root only if needed: ``--project-dir /path/to/repo`` or ``WRANGLER_PROJECT_DIR``.

ECOSTRESS/STAC needs network + Earthdata. Landsat STAC needs network (+ AWS for ``s3://usgs-landsat`` COGs).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Repo-root .env (Earthdata, R2, etc.) when cwd is lambda_functions/
_REPO_ENV = Path(__file__).resolve().parent.parent.parent / ".env"
if _REPO_ENV.is_file():
    load_dotenv(_REPO_ENV)
load_dotenv()

from common.local_wrangler import resolve_wrangler_project_root


def _repo_root_from_package() -> Path:
    """Fallback when cwd is not under the repo (e.g. odd invocations)."""
    return Path(__file__).resolve().parent.parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fill processor outputs for one feature / date range")
    parser.add_argument("--source", choices=("ecostress", "landsat"), required=True)
    parser.add_argument(
        "--feature",
        required=True,
        help="Feature name (e.g. Magat) or numeric AID",
    )
    parser.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="YYYY-MM-DD (default: start-date)")
    parser.add_argument(
        "--runtime",
        choices=("cloud", "local"),
        default=os.environ.get("PROCESSOR_RUNTIME", "cloud"),
        help="cloud: Cloudflare D1 API + R2 via boto3; local: wrangler d1/r2 --local",
    )
    parser.add_argument(
        "--project-dir",
        default=None,
        help="Repo root (wrangler.toml + static/). "
        "Default: walk up from cwd, else WRANGLER_PROJECT_DIR, else package parent.",
    )
    parser.add_argument(
        "--prefer-http-hrefs",
        action="store_true",
        help="ECOSTRESS: prefer HTTPS COG links over s3:// (default when --runtime local)",
    )
    parser.add_argument(
        "--prefer-s3-hrefs",
        action="store_true",
        help="ECOSTRESS: use s3:// links even with --runtime local (Lambda-style; needs Earthdata S3 creds)",
    )
    args = parser.parse_args(argv)

    if args.project_dir:
        repo_root = Path(args.project_dir).resolve()
    elif os.environ.get("WRANGLER_PROJECT_DIR"):
        repo_root = Path(os.environ["WRANGLER_PROJECT_DIR"]).resolve()
    else:
        discovered = resolve_wrangler_project_root()
        repo_root = discovered if discovered is not None else _repo_root_from_package()

    if not (repo_root / "static").is_dir() or not (repo_root / "wrangler.toml").is_file():
        print(
            f"Not a project root (need wrangler.toml + static/): {repo_root}\n"
            f"  cd into the repo (or any subfolder) or pass --project-dir",
            file=sys.stderr,
        )
        return 2

    os.chdir(repo_root)
    os.environ["PROCESSOR_RUNTIME"] = args.runtime
    os.environ["WRANGLER_PROJECT_DIR"] = str(repo_root)

    sd = args.start_date
    ed = args.end_date or sd

    from common.exceptions import NoDataError
    from common.polygons import load_polygons, filter_polygons_for_feature

    if args.source == "ecostress":
        from ecostress.initiator import iter_ecostress_processor_bodies
        from ecostress.processor import process_one_record

        polys = filter_polygons_for_feature(load_polygons(), args.feature)
        if not polys:
            print(f"No feature match for {args.feature!r}", file=sys.stderr)
            return 1
        task_id = f"local-fill-eco-{int(time.time() * 1000)}"
        ok, nodata, failed = 0, 0, 0
        prefer_http = (
            args.prefer_http_hrefs or args.runtime == "local"
        ) and not args.prefer_s3_hrefs
        for body in iter_ecostress_processor_bodies(
            sd,
            ed,
            task_id=task_id,
            polygons=polys,
            prefer_http_hrefs=prefer_http,
        ):
            try:
                process_one_record(body)
                ok += 1
            except NoDataError:
                nodata += 1
            except Exception as e:
                print(f"[fail] {body.get('date')} aid={body.get('aid')}: {e}", file=sys.stderr)
                failed += 1
        print(f"Done: success={ok} nodata={nodata} failed={failed}")
        return 0 if failed == 0 else 1

    from landsat.initiator import iter_landsat_processor_bodies
    from landsat.processor import process_one_record as process_landsat

    polys = filter_polygons_for_feature(load_polygons(), args.feature)
    if not polys:
        print(f"No feature match for {args.feature!r}", file=sys.stderr)
        return 1
    ok, nodata, failed = 0, 0, 0
    for body in iter_landsat_processor_bodies(sd, ed, polygons=polys):
        try:
            process_landsat(body)
            ok += 1
        except NoDataError:
            nodata += 1
        except Exception as e:
            print(f"[fail] {body.get('date')} aid={body.get('aid')}: {e}", file=sys.stderr)
            failed += 1
    print(f"Done: success={ok} nodata={nodata} failed={failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
