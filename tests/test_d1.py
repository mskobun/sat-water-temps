"""Tests for lambda_functions/d1.py — consolidated D1 helpers."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lambda_functions"))

from d1 import D1Error, query_d1, log_job_to_d1


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

D1_ENV = {
    "D1_DATABASE_ID": "fake-db-id",
    "CLOUDFLARE_ACCOUNT_ID": "fake-account",
    "CLOUDFLARE_API_TOKEN": "fake-token",
}


@pytest.fixture(autouse=True)
def d1_env(monkeypatch):
    for k, v in D1_ENV.items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def mock_post():
    with patch("d1.requests.post") as m:
        yield m


def _ok_response(meta=None):
    body = {"success": True, "result": [{"meta": meta or {}}]}
    resp = MagicMock()
    resp.json.return_value = body
    resp.raise_for_status.return_value = None
    return resp


def _err_response():
    import requests as _requests
    resp = MagicMock()
    resp.status_code = 500
    resp.json.return_value = {"errors": ["broke"]}
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = _requests.exceptions.HTTPError(response=resp)
    return mock_resp


def _get_sql(mock_post):
    return " ".join(mock_post.call_args[1]["json"]["sql"].split())


def _get_params(mock_post):
    return mock_post.call_args[1]["json"]["params"]


# ===========================================================================
# query_d1 — fatal vs non-fatal
# ===========================================================================


class TestQueryD1Fatal:
    def test_missing_creds_fatal_raises(self, monkeypatch):
        monkeypatch.delenv("D1_DATABASE_ID")
        with pytest.raises(D1Error, match="credentials"):
            query_d1("SELECT 1")

    def test_missing_creds_nonfatal_returns_failure(self, monkeypatch):
        monkeypatch.delenv("D1_DATABASE_ID")
        assert query_d1("SELECT 1", fatal=False) == {"success": False}

    def test_http_error_fatal_raises(self, mock_post):
        mock_post.return_value = _err_response()
        with pytest.raises(D1Error):
            query_d1("SELECT 1")

    def test_http_error_nonfatal_returns_failure(self, mock_post):
        mock_post.return_value = _err_response()
        assert query_d1("SELECT 1", fatal=False)["success"] is False

    def test_success_returns_json(self, mock_post):
        mock_post.return_value = _ok_response()
        assert query_d1("SELECT 1")["success"] is True


# ===========================================================================
# log_job_to_d1 — WHERE clause construction
# ===========================================================================


class TestLogJobInsert:
    def test_insert_includes_all_columns(self, mock_post):
        mock_post.return_value = _ok_response(meta={"last_row_id": 1})
        log_job_to_d1(job_type="process", task_id="t1", feature_id="Songkhla", date="2024001", status="started")
        sql = _get_sql(mock_post)
        assert "INSERT INTO processing_jobs" in sql
        params = _get_params(mock_post)
        assert params[:5] == ["process", "t1", "Songkhla", "2024001", "started"]

    def test_insert_returns_last_row_id(self, mock_post):
        mock_post.return_value = _ok_response(meta={"last_row_id": 99})
        assert log_job_to_d1(job_type="x", status="started") == 99


class TestLogJobUpdate:
    """The tricky part: WHERE clause changes based on which identifiers are passed."""

    def test_processor_pattern_all_identifiers(self, mock_post):
        """processor.py passes job_type + task_id + feature_id + date."""
        mock_post.return_value = _ok_response()
        log_job_to_d1(job_type="process", task_id="t1", feature_id="Songkhla", date="2024001", status="success", duration_ms=500)
        sql = _get_sql(mock_post)
        assert "job_type = ?" in sql
        assert "task_id = ?" in sql
        assert "feature_id = ?" in sql
        assert "date = ?" in sql
        assert "ORDER BY started_at DESC LIMIT 1" in sql

    def test_manifest_pattern_task_id_only(self, mock_post):
        """manifest_processor.py passes job_type + task_id only."""
        mock_post.return_value = _ok_response()
        log_job_to_d1(job_type="manifest", task_id="t1", status="success")
        sql = _get_sql(mock_post)
        assert "job_type = ?" in sql
        assert "task_id = ?" in sql
        assert "feature_id" not in sql
        assert "date = ?" not in sql

    def test_update_has_coalesce_metadata(self, mock_post):
        mock_post.return_value = _ok_response()
        log_job_to_d1(job_type="x", task_id="t1", status="success")
        assert "COALESCE(?, metadata)" in _get_sql(mock_post)

    def test_fatal_false_swallows_error(self, mock_post):
        mock_post.return_value = _err_response()
        assert log_job_to_d1(job_type="x", status="started", fatal=False) is None

    def test_fatal_true_raises_on_update(self, mock_post):
        mock_post.return_value = _err_response()
        with pytest.raises(D1Error):
            log_job_to_d1(job_type="x", task_id="t1", status="success")
