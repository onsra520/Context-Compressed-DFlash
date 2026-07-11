from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "ccdf", *args],
        check=False,
        text=True,
        capture_output=True,
    )


def first_fixture(dataset: str) -> str:
    path = Path("data/eval") / dataset / f"{dataset}_n10.jsonl"
    return json.loads(path.read_text(encoding="utf-8").splitlines()[0])["fixture_id"]


def test_direct_prompt_text_mode() -> None:
    result = run_cli(
        "run",
        "--condition",
        "baseline-ar",
        "--prompt",
        "How many positive divisors does 196 have?",
    )
    assert result.returncode == 0
    assert "Condition: baseline-ar" in result.stdout
    assert "Answer:" in result.stdout


def test_direct_prompt_json_mode() -> None:
    result = run_cli(
        "run",
        "--condition",
        "dflash-r1",
        "--prompt",
        "How many positive divisors does 196 have?",
        "--format",
        "json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["condition"]["condition_id"] == "dflash-r1"
    assert payload["measurement_mode"] == "benchmark"


def test_fixture_profile_json_mode() -> None:
    fixture_id = first_fixture("gsm8k")
    result = run_cli(
        "run",
        "--condition",
        "dflash-r1",
        "--dataset",
        "gsm8k",
        "--fixture-id",
        fixture_id,
        "--profile",
        "--format",
        "json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["fixture_id"] == fixture_id
    assert payload["measurement_mode"] == "profiling"
    assert payload["quality"]["label"] == "strict_correct"


def test_context_file_question(tmp_path: Path) -> None:
    context = tmp_path / "meeting.txt"
    context.write_text("A: We approved the launch date.\nB: Ship it Friday.", encoding="utf-8")
    result = run_cli(
        "run",
        "--condition",
        "cc-dflash-r2",
        "--context-file",
        str(context),
        "--question",
        "What decision was made?",
        "--format",
        "json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["condition"]["condition_id"] == "cc-dflash-r2"


def test_save_writes_to_task_directory() -> None:
    result = run_cli(
        "run",
        "--condition",
        "baseline-ar",
        "--prompt",
        "How many positive divisors does 196 have?",
        "--save",
        "--format",
        "json",
    )
    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert Path(payload["saved_path"]).exists()


def test_validation_failure_nonzero() -> None:
    result = run_cli("run", "--condition", "baseline-ar")
    assert result.returncode != 0
    assert "provide --prompt" in result.stderr
