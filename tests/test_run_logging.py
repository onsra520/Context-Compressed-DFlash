import json
from argparse import Namespace
from dataclasses import dataclass

import pytest

import cli.run_logging as run_logging
from cli.run_logging import RunLogSession, sanitize_argv


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


def test_run_log_session_scrubs_sensitive_argv_from_exception_payload(tmp_path):
    prompt = "PROMPT_SENTINEL"

    with pytest.raises(RuntimeError, match=prompt):
        with RunLogSession("htfsd-generate", ["--prompt", prompt], log_dir=tmp_path) as session:
            raise RuntimeError(f"failed prompt {prompt}")

    log_text = session.path.read_text(encoding="utf-8")
    row = json.loads(log_text)
    assert row["status"] == "error"
    assert row["exit_code"] == 1
    assert row["error"]["exception_type"] == "RuntimeError"
    assert prompt not in row["error"]["message"]
    assert prompt not in row["error"]["traceback"]
    assert prompt not in log_text


def test_run_log_write_failure_warns_without_masking_command_exception(tmp_path, capsys):
    with pytest.raises(RuntimeError, match="command failed"):
        with RunLogSession("htfsd-generate", ["\udcff"], log_dir=tmp_path):
            raise RuntimeError("command failed")

    assert "warning: failed to write HTFSD run log:" in capsys.readouterr().err


def test_run_log_session_treats_system_exit_zero_as_ok(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        with RunLogSession("htfsd-generate", ["--help"], log_dir=tmp_path) as session:
            raise SystemExit(0)

    assert exit_info.value.code == 0
    row = read_log(session)
    assert row["status"] == "ok"
    assert row["exit_code"] == 0
    assert row["error"] is None


def test_run_log_session_treats_system_exit_none_as_ok(tmp_path):
    with pytest.raises(SystemExit) as exit_info:
        with RunLogSession("htfsd-generate", ["--help"], log_dir=tmp_path) as session:
            raise SystemExit()

    assert exit_info.value.code is None
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


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["--prompt", "private prompt"], ["--prompt", "<redacted>"]),
        (["--prompt=private prompt"], ["--prompt=<redacted>"]),
        (["--pro", "private prompt"], ["--pro", "<redacted>"]),
        (["--pro=private prompt"], ["--pro=<redacted>"]),
    ],
)
def test_run_log_session_redacts_prompt_argv(tmp_path, argv, expected):
    with RunLogSession("htfsd-generate", argv, log_dir=tmp_path) as session:
        pass

    row = read_log(session)
    assert row["argv"] == {
        "sanitized": expected,
        "prompt_present": True,
        "prompt_chars": len("private prompt"),
        "prompt_sha256": None,
    }
    assert "private prompt" not in session.path.read_text(encoding="utf-8")


@pytest.mark.parametrize("flag", ["--hf-token", "--token", "--api-key", "--password"])
@pytest.mark.parametrize(
    ("suffix", "expected"),
    [
        (["secret"], ["<redacted>"]),
        (["=secret"], ["=<redacted>"]),
    ],
)
def test_sanitize_argv_redacts_sensitive_values(flag, suffix, expected):
    raw_argv = [flag + suffix[0]] if suffix[0].startswith("=") else [flag, suffix[0]]
    expected_argv = [flag + expected[0]] if expected[0].startswith("=") else [flag, expected[0]]

    sanitized = sanitize_argv(raw_argv)

    assert sanitized["sanitized"] == expected_argv


@pytest.mark.parametrize(
    ("argv", "expected", "sentinel"),
    [
        (
            ["--prompt", "--api-key", "API_KEY_SENTINEL"],
            ["--prompt", "--api-key", "<redacted>"],
            "API_KEY_SENTINEL",
        ),
        (
            ["--token", "--prompt", "PROMPT_SENTINEL"],
            ["--token", "--prompt", "<redacted>"],
            "PROMPT_SENTINEL",
        ),
    ],
)
def test_run_log_session_redacts_adjacent_sensitive_argv(tmp_path, argv, expected, sentinel):
    with RunLogSession("htfsd-generate", argv, log_dir=tmp_path) as session:
        pass

    row = read_log(session)
    assert row["argv"]["sanitized"] == expected
    assert sentinel not in row["argv"]["sanitized"]
    assert sentinel not in session.path.read_text(encoding="utf-8")


@dataclass(frozen=True)
class FakeModelConfig:
    model_id_or_path: str


@dataclass(frozen=True)
class FakeRuntimeConfig:
    execution_mode: str


@dataclass(frozen=True)
class FakeDecodingConfig:
    default: str


@dataclass(frozen=True)
class FakeConfig:
    qwen_drafter: FakeModelConfig
    gemma_e2b: FakeModelConfig
    gemma_e4b_baseline: FakeModelConfig
    runtime: FakeRuntimeConfig
    decoding: FakeDecodingConfig


def test_run_log_session_records_paths_and_config_metadata(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = FakeConfig(
        qwen_drafter=FakeModelConfig("qwen-local"),
        gemma_e2b=FakeModelConfig("gemma-e2b-local"),
        gemma_e4b_baseline=FakeModelConfig("gemma-e4b-local"),
        runtime=FakeRuntimeConfig("concurrent"),
        decoding=FakeDecodingConfig("greedy"),
    )

    with RunLogSession("htfsd-benchmark-low", [], log_dir=tmp_path / "logs") as session:
        session.record_cli_args(Namespace(config="configs/local.yaml"))
        session.record_artifact("benchmark_output_path", tmp_path / "runs" / "low.jsonl")
        session.record_config(config, config_path=tmp_path / "configs" / "local.yaml")

    row = read_log(session)
    assert row["paths"]["config_path"] == "configs/local.yaml"
    assert row["paths"]["benchmark_output_path"] == "runs/low.jsonl"
    assert row["runtime"]["execution_mode"] == "concurrent"
    assert row["runtime"]["decoding_mode"] == "greedy"
    assert row["models"] == {
        "qwen_drafter": "qwen-local",
        "gemma_e2b": "gemma-e2b-local",
        "gemma_e4b_baseline": "gemma-e4b-local",
    }


def test_run_log_session_rejects_unknown_artifact_key(tmp_path):
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        with pytest.raises(ValueError, match="unknown artifact key"):
            session.record_artifact("transcript_path", tmp_path / "transcript.txt")


def test_run_log_session_metadata_and_config_recording_are_best_effort(tmp_path):
    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        session.record_metadata(good_metadata={"nested": ["json"]}, bad_metadata=object())
        session.record_config(object(), config_path=tmp_path / "configs" / "local.yaml")

    row = read_log(session)
    assert row["runtime"]["good_metadata"] == {"nested": ["json"]}
    assert row["paths"]["config_path"]


def test_run_log_session_records_runtime_versions_best_effort(tmp_path, monkeypatch):
    monkeypatch.setattr(run_logging, "_git_commit", lambda: "abc123")
    monkeypatch.setattr(run_logging, "_vllm_version", lambda: "9.9.9")

    with RunLogSession("htfsd-generate", [], log_dir=tmp_path) as session:
        pass

    row = read_log(session)
    assert row["runtime"]["git_commit"] == "abc123"
    assert row["runtime"]["vllm_version"] == "9.9.9"
