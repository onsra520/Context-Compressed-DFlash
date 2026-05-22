import json

import pytest

from cli.run_logging import RunLogSession


def read_log(session: RunLogSession) -> dict:
    return json.loads(session.path.read_text(encoding="utf-8"))


def test_run_log_session_writes_success_json(tmp_path):
    with RunLogSession("htfsd-generate", ["--config", "configs/local.yaml"], log_dir=tmp_path) as session:
        assert session.path.parent == tmp_path

    row = read_log(session)
    assert row["schema_version"] == 1
    assert row["command"] == "htfsd-generate"
    assert row["status"] == "ok"
    assert row["exit_code"] == 0
    assert row["error"] is None
    assert row["start_time"]
    assert row["end_time"]
    assert row["duration_ms"] >= 0.0


def test_run_log_session_records_exception_and_reraises(tmp_path):
    with pytest.raises(RuntimeError, match="boom"):
        with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
            raise RuntimeError("boom")

    row = read_log(session)
    assert row["status"] == "error"
    assert row["exit_code"] == 1
    assert row["error"]["exception_type"] == "RuntimeError"
    assert row["error"]["message"] == "boom"
    assert "RuntimeError: boom" in row["error"]["traceback"]


def test_run_log_session_treats_system_exit_zero_as_ok(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        with RunLogSession("htfsd-generate", ["--help"], log_dir=tmp_path) as session:
            raise SystemExit(0)

    assert exit_info.value.code == 0
    row = read_log(session)
    assert row["status"] == "ok"
    assert row["exit_code"] == 0
    assert row["error"] is None


def test_run_log_session_records_nonzero_system_exit(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
            raise SystemExit(2)

    assert exit_info.value.code == 2
    row = read_log(session)
    assert row["status"] == "error"
    assert row["exit_code"] == 2
    assert row["error"]["exception_type"] == "SystemExit"
    assert row["error"]["message"] == "2"


def test_run_log_session_mark_error_for_nonzero_return(tmp_path):
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        session.mark_error("runner returned nonzero", exit_code=7)

    row = read_log(session)
    assert row["status"] == "error"
    assert row["exit_code"] == 7
    assert row["error"]["exception_type"] == "CommandReturnedNonZero"
    assert row["error"]["message"] == "runner returned nonzero"
