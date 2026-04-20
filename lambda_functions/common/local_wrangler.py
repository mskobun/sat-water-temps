"""Local development helpers: run Wrangler CLI for D1 and R2 bindings.

When ``PROCESSOR_RUNTIME=local``, processors use this module instead of the
Cloudflare HTTP API (D1) and boto3 S3 (R2).

Project directory for Wrangler defaults to the current working directory, walking
upward until a folder with both ``wrangler.toml`` and ``static/`` is found.
Override with ``WRANGLER_PROJECT_DIR`` if needed. Optional: ``WRANGLER_PERSIST_TO``
to match ``wrangler dev --persist-to``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


def _d1_error(msg: str):
    from d1 import D1Error

    return D1Error(msg)


def resolve_wrangler_project_root(start: Optional[Path] = None) -> Optional[Path]:
    """Find repo root from ``start`` (default: cwd): directory with ``wrangler.toml`` and ``static/``."""
    p = (start or Path.cwd()).resolve()
    for _ in range(12):
        if (p / "wrangler.toml").is_file() and (p / "static").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return None


def _project_dir() -> str:
    env = os.environ.get("WRANGLER_PROJECT_DIR")
    if env:
        return env
    found = resolve_wrangler_project_root()
    if found is not None:
        return str(found)
    return os.getcwd()


def _persist_args() -> List[str]:
    p = os.environ.get("WRANGLER_PERSIST_TO")
    if p:
        return ["--persist-to", p]
    return []


def _wrangler_base() -> List[str]:
    wr = os.environ.get("WRANGLER_COMMAND")
    if wr:
        return shlex_split_compat(wr)
    npx = shutil.which("npx")
    if npx:
        return [npx, "wrangler"]
    exe = shutil.which("wrangler")
    if exe:
        return [exe]
    raise _d1_error("Neither npx nor wrangler found on PATH (set WRANGLER_COMMAND)")


def shlex_split_compat(cmd: str) -> List[str]:
    import shlex

    return shlex.split(cmd)


def _d1_database_name() -> str:
    return os.environ.get("WRANGLER_D1_DATABASE_NAME", "sat-water-temps-db")


def inline_sql_params(sql: str, params: Optional[List[Any]]) -> str:
    """Replace ``?`` placeholders with SQLite-safe literals (local dev only)."""
    if not params:
        return sql
    parts = sql.split("?")
    if len(parts) - 1 != len(params):
        raise _d1_error(
            f"SQL placeholder count mismatch: {len(parts) - 1} vs {len(params)} params"
        )
    out: List[str] = []
    for i, val in enumerate(params):
        out.append(parts[i])
        if val is None:
            out.append("NULL")
        elif isinstance(val, bool):
            out.append("1" if val else "0")
        elif isinstance(val, int):
            out.append(str(val))
        elif isinstance(val, float):
            out.append(repr(val))
        else:
            s = str(val).replace("'", "''")
            out.append(f"'{s}'")
    out.append(parts[-1])
    return "".join(out)


def _parse_wrangler_d1_json(stdout: str) -> Dict:
    text = stdout.strip()
    if not text:
        return {"success": False, "error": "empty wrangler output"}
    # Wrangler may print a banner; find JSON array start
    start = text.find("[")
    if start == -1:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                success = all(x.get("success") for x in data if isinstance(x, dict))
                return {"success": success, "result": data}
        except json.JSONDecodeError:
            pass
        return {"success": False, "error": text}
    try:
        data = json.loads(text[start:])
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"invalid JSON from wrangler: {e}\n{text}"}
    if not isinstance(data, list):
        return {"success": False, "error": f"unexpected wrangler JSON shape: {data!r}"}
    success = all(x.get("success", True) for x in data if isinstance(x, dict))
    return {"success": success, "result": data}


def query_d1_via_wrangler(
    sql: str, params: List = None, fatal: bool = True
) -> Dict:
    """Run ``wrangler d1 execute --local --json`` and normalize output like HTTP API."""
    sql_run = inline_sql_params(sql, params)
    cmd = (
        _wrangler_base()
        + ["d1", "execute", _d1_database_name(), "--local", "--json", "--command", sql_run]
        + _persist_args()
    )
    try:
        proc = subprocess.run(
            cmd,
            cwd=_project_dir(),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("WRANGLER_TIMEOUT_SEC", "300")),
        )
    except subprocess.TimeoutExpired as e:
        msg = f"wrangler d1 execute timed out: {e}"
        if fatal:
            raise _d1_error(msg) from e
        return {"success": False, "error": msg}
    except FileNotFoundError as e:
        msg = f"wrangler not executable: {e}"
        if fatal:
            raise _d1_error(msg) from e
        return {"success": False, "error": msg}

    if proc.returncode != 0:
        msg = f"wrangler d1 failed ({proc.returncode}): {proc.stderr or proc.stdout}"
        if fatal:
            raise _d1_error(msg)
        return {"success": False, "error": msg}

    parsed = _parse_wrangler_d1_json(proc.stdout)
    if not parsed.get("success") and fatal:
        raise _d1_error(f"D1 command reported failure: {parsed}")
    return parsed


class WranglerLocalR2Backend:
    """R2 read/write via ``wrangler r2 object`` --local."""

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("R2_BUCKET_NAME", "multitifs")

    def upload_file_from_path(
        self, bucket: str, key: str, path: str, content_type: Optional[str] = None
    ) -> None:
        object_path = f"{bucket}/{key}"
        cmd = (
            _wrangler_base()
            + ["r2", "object", "put", object_path, "--local", "--file", path]
            + _persist_args()
        )
        if content_type:
            cmd.extend(["--content-type", content_type])
        self._run(cmd)

    def put_object(
        self,
        bucket: str,
        key: str,
        body: bytes,
        content_type: Optional[str] = None,
        content_encoding: Optional[str] = None,
    ) -> None:
        fd, tmp_path = tempfile.mkstemp(prefix="r2put_", suffix=".bin")
        os.close(fd)
        try:
            with open(tmp_path, "wb") as f:
                f.write(body)
            object_path = f"{bucket}/{key}"
            cmd = (
                _wrangler_base()
                + ["r2", "object", "put", object_path, "--local", "--file", tmp_path]
                + _persist_args()
            )
            if content_type:
                cmd.extend(["--content-type", content_type])
            if content_encoding:
                cmd.extend(["--content-encoding", content_encoding])
            self._run(cmd)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def get_object_bytes(self, bucket: str, key: str) -> bytes:
        object_path = f"{bucket}/{key}"
        fd, tmp_path = tempfile.mkstemp(prefix="r2get_", suffix=".bin")
        os.close(fd)
        try:
            cmd = (
                _wrangler_base()
                + ["r2", "object", "get", object_path, "--local", "--file", tmp_path]
                + _persist_args()
            )
            try:
                self._run(cmd)
            except Exception as e:
                # Treat missing object like S3 NoSuchKey (boto vs wrangler wording)
                msg = str(e).lower()
                if (
                    "not found" in msg
                    or "does not exist" in msg
                    or "404" in msg
                ):
                    raise FileNotFoundError(key) from e
                raise
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _run(self, cmd: List[str]) -> None:
        proc = subprocess.run(
            cmd,
            cwd=_project_dir(),
            capture_output=True,
            text=True,
            timeout=int(os.environ.get("WRANGLER_TIMEOUT_SEC", "600")),
        )
        if proc.returncode != 0:
            raise _d1_error(
                f"wrangler failed ({proc.returncode}): {proc.stderr or proc.stdout}"
            )
