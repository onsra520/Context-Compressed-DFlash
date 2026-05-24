from pathlib import Path

from htfsd.cli.error_report import redact_text, write_runtime_error_report


def test_error_report_writes_required_markdown_sections(tmp_path: Path):
    report_path = write_runtime_error_report(
        summary="Model failed to load.",
        command=["python", "scripts/smoke_qwen.py"],
        environment={"python": {"version": "3.12"}},
        model_context={"qwen_drafter": {"status": "missing_model_file"}},
        error_message="missing model",
        traceback_text="Traceback line",
        suspected_cause="The configured model directory has no GGUF file.",
        proposed_fix="Place exactly one .gguf file in models/qwen3-0.6b.",
        verification_steps=["python scripts/check_env.py"],
        log_dir=tmp_path,
    )

    text = report_path.read_text(encoding="utf-8")
    assert report_path.parent == tmp_path
    assert report_path.name.endswith("-runtime-error.md")
    for heading in (
        "# Runtime Error Report",
        "## Summary",
        "## Command",
        "## Environment",
        "## Model Context",
        "## Error Message",
        "## Traceback",
        "## Suspected Cause",
        "## Proposed Fix",
        "## Verification Steps",
        "## Status",
    ):
        assert heading in text


def test_error_report_redacts_sensitive_values(tmp_path: Path):
    report_path = write_runtime_error_report(
        summary="Prompt failed.",
        command=["cmd", "--prompt", "PRIVATE_PROMPT", "--token=SECRET"],
        environment={},
        model_context={},
        error_message="PRIVATE_PROMPT SECRET",
        traceback_text="Traceback PRIVATE_PROMPT SECRET",
        suspected_cause="Input caused a failure.",
        proposed_fix="Retry without sensitive data.",
        verification_steps=["python scripts/check_env.py"],
        log_dir=tmp_path,
    )

    text = report_path.read_text(encoding="utf-8")
    assert "PRIVATE_PROMPT" not in text
    assert "SECRET" not in text
    assert "<redacted>" in text


def test_redact_text_handles_prompt_and_token_flags():
    redacted = redact_text(
        "cmd --prompt private --api-key secret --password=pw --token=tok",
        sensitive_values=["private", "secret", "pw", "tok"],
    )

    assert "private" not in redacted
    assert "secret" not in redacted
    assert "pw" not in redacted
    assert "tok" not in redacted
