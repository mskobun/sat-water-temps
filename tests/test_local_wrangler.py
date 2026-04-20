"""Tests for Wrangler CLI helpers (no subprocess to real wrangler required)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from common.local_wrangler import (  # noqa: E402
    inline_sql_params,
    resolve_wrangler_project_root,
)
from d1 import query_d1  # noqa: E402


class TestResolveWranglerProjectRoot:
    def test_finds_root_from_lambda_functions_cwd(self, monkeypatch, tmp_path):
        repo = tmp_path / "repo"
        (repo / "static").mkdir(parents=True)
        (repo / "wrangler.toml").write_text("name = x\n")
        sub = repo / "lambda_functions"
        sub.mkdir()
        monkeypatch.chdir(sub)
        assert resolve_wrangler_project_root() == repo.resolve()


class TestInlineSqlParams:
    def test_strings_and_null(self):
        sql = "SELECT * FROM t WHERE a = ? AND b = ? AND c = ?"
        out = inline_sql_params(sql, ["x'y", 42, None])
        assert out == "SELECT * FROM t WHERE a = 'x''y' AND b = 42 AND c = NULL"


class TestQueryD1LocalRuntime:
    def test_local_uses_wrangler_path(self, monkeypatch):
        monkeypatch.setenv("PROCESSOR_RUNTIME", "local")
        monkeypatch.delenv("D1_DATABASE_ID", raising=False)
        from unittest.mock import patch

        with patch(
            "common.local_wrangler.query_d1_via_wrangler",
            return_value={"success": True, "result": []},
        ) as m:
            r = query_d1("SELECT 1", fatal=False)
        m.assert_called_once()
        assert r["success"] is True
