"""Build and verify the REC-3 D-Flash verifier diagnostic review pack."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_ROOT = ROOT / "docs/artifacts/rec3-dflash-verifier-diagnostic"
EVIDENCE = ROOT / "docs/artifacts/review-pack/rec3-dflash-verifier-diagnostic"
ARCHIVE = ROOT / "docs/reviews/review-pack-rec3-dflash-verifier-diagnostic.tar.gz"
SOURCE_FILES = [
    ".gitignore", "config.yml", "pyproject.toml",
    "src/ccdf/config.py", "src/ccdf/determinism.py", "src/ccdf/device.py", "src/ccdf/schemas.py",
    "src/ccdf/models/loaders.py", "src/ccdf/runtime/engine.py",
    "src/ccdf/inference/baseline.py", "src/ccdf/inference/sampling.py",
    "src/ccdf/dflash/acceptance.py", "src/ccdf/dflash/generate.py",
    "src/ccdf/dflash/policy.py", "src/ccdf/dflash/verifier.py",
    "tests/run_rec3_dflash_verifier_diagnostic.py",
    "tests/run_rec3_four_condition_protocol.py",
    "tests/run_rec3_mock02_divergence.py",
    "tests/build_rec3_dflash_verifier_review_pack.py",
    "tests/test_rec3_protocol_helpers.py", "tests/test_dflash_integration.py", "tests/test_metrics.py",
]
ARTIFACT_FILES = [
    "docs/artifacts/rec3-dflash-verifier-diagnostic/diagnostic.json",
    "docs/artifacts/rec3-dflash-verifier-diagnostic/raw_divergence_logits.pt",
    "docs/artifacts/rec3-dflash-verifier-diagnostic/BLOCKER.md",
    "docs/artifacts/rec3-four-condition-mock10/summary.json",
    "docs/artifacts/rec3-four-condition-mock10/raw_runs.json",
    "docs/artifacts/rec3-four-condition-mock10/rec3_mock_02_divergence.json",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _run(label: str, command: list[str], environment: dict[str, str]) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        command, cwd=ROOT, env=environment, text=True, capture_output=True, check=False
    )
    return {
        "label": label, "command": command, "exit_code": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def _validate_diagnostic() -> dict[str, Any]:
    report_path = DIAGNOSTIC_ROOT / "diagnostic.json"
    logits_path = DIAGNOSTIC_ROOT / "raw_divergence_logits.pt"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    logits = torch.load(logits_path, map_location="cpu", weights_only=True)
    expected_keys = set(report["raw_logits"]["keys"])
    actual_keys = set(logits)
    vectors_valid = all(
        isinstance(value, torch.Tensor)
        and value.dtype == torch.float32
        and value.ndim == 1
        and value.numel() == 151936
        for value in logits.values()
    )
    shapes = report["paths"]["block_target_verification"]
    block_sizes = [item["block_size"] for item in shapes]
    classification = report["classification"]
    gates = {
        "classification_is_block_shape_awq_drift": (
            classification["primary_classification"]
            == "block_shape_numerical_drift_on_active_awq_path"
        ),
        "active_quantization_is_awq": classification["active_quantization"] == "AWQ",
        "input_contract_locked": all(
            report["locked_runtime"][key] is False
            for key in ("fixture_changed", "prompt_changed", "compression_output_changed", "model_changed")
        ),
        "sdpa_math_locked": report["locked_runtime"]["sdpa_kernel"] == "math",
        "awq_split_k_locked": report["locked_runtime"]["awq_split_k_iters"] == 1,
        "all_block_sizes_present": block_sizes == [2, 4, 8, 16],
        "position_indexing_pass": classification["indexing_position_ids_pass"],
        "cache_crop_pass": classification["cache_crop_boundary_pass"],
        "attention_mask_not_causal": not classification["attention_mask_changes_top1"],
        "block_shape_changes_top1": classification["block_shape_changes_top1"],
        "raw_logits_file_hash_match": report["raw_logits"]["sha256"] == _sha256(logits_path),
        "raw_logits_keys_match": expected_keys == actual_keys,
        "raw_logits_vectors_valid": vectors_valid,
        "core_patch_not_applied": not classification["dflash_core_patch_applied"],
        "dataset_smoke_blocked": classification["dataset_smoke_blocked"],
    }
    return {"pass": all(gates.values()), "gates": gates, "report_summary": classification}


def _git_evidence(environment: dict[str, str]) -> tuple[str, str, str]:
    base = _run("base-commit", ["git", "rev-parse", "HEAD"], environment)
    if base["exit_code"] != 0:
        raise RuntimeError(f"cannot resolve base commit: {base['stderr']}")
    base_sha = str(base["stdout"]).strip()
    changed = [
        _run("git-diff-name-status", ["git", "diff", "--name-status", base_sha], environment),
        _run("git-diff-cached-name-status", ["git", "diff", "--cached", "--name-status", base_sha], environment),
        _run("git-untracked", ["git", "ls-files", "--others", "--exclude-standard"], environment),
        _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment),
        _run(
            "git-ignored-validation-sources",
            [
                "git", "check-ignore", "-v",
                "tests/run_rec3_dflash_verifier_diagnostic.py",
                "tests/run_rec3_four_condition_protocol.py",
                "tests/run_rec3_mock02_divergence.py",
                "tests/build_rec3_dflash_verifier_review_pack.py",
                "tests/test_rec3_protocol_helpers.py",
            ],
            environment,
        ),
    ]
    changed_text = "".join(
        f"# {item['label']}\n$ {' '.join(item['command'])}\nexit={item['exit_code']}\n{item['stdout']}{item['stderr']}\n"
        for item in changed
    )
    dflash = [
        _run("dflash-status", ["git", "status", "--short", "--", "src/ccdf/dflash"], environment),
        _run("dflash-diff-numstat", ["git", "diff", "--numstat", base_sha, "--", "src/ccdf/dflash"], environment),
        _run("dflash-untracked", ["git", "ls-files", "--others", "--exclude-standard", "src/ccdf/dflash"], environment),
        _run("dflash-diff-check", ["git", "diff", "--check", base_sha, "--", "src/ccdf/dflash"], environment),
    ]
    dflash_text = (
        f"base_commit_sha={base_sha}\n"
        "scope=src/ccdf/dflash\n"
        "claim=No D-Flash core patch was applied in this diagnostic batch.\n\n"
        + "".join(
            f"# {item['label']}\n$ {' '.join(item['command'])}\nexit={item['exit_code']}\n{item['stdout']}{item['stderr']}\n"
            for item in dflash
        )
    )
    return base_sha, changed_text, dflash_text


def main() -> None:
    environment = os.environ.copy()
    environment["PROJECT_ROOT"] = str(ROOT)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    commands = [
        _run(
            "rec3-dflash-verifier-diagnostic",
            [str(ROOT / ".venv/bin/python"), "tests/run_rec3_dflash_verifier_diagnostic.py"],
            environment,
        ),
        _run(
            "rec3-four-condition-protocol",
            [str(ROOT / ".venv/bin/python"), "tests/run_rec3_four_condition_protocol.py"],
            environment,
        ),
        _run(
            "compileall",
            [str(ROOT / ".venv/bin/python"), "-m", "compileall", "-q", "src", "scripts", "tests"],
            environment,
        ),
        _run("pytest", [str(ROOT / ".venv/bin/pytest"), "-q"], environment),
        _run("git-diff-check", ["git", "diff", "--check"], environment),
    ]
    _write(EVIDENCE / "commands.json", json.dumps(commands, indent=2, sort_keys=True) + "\n")
    _write(EVIDENCE / "test-results.txt", "".join(
        f"$ {' '.join(item['command'])}\nexit={item['exit_code']}\n{item['stdout']}{item['stderr']}\n"
        for item in commands
    ))

    diagnostic_validation = _validate_diagnostic()
    protocol_summary = json.loads(
        (ROOT / "docs/artifacts/rec3-four-condition-mock10/summary.json").read_text(encoding="utf-8")
    )
    base_sha, changed_text, dflash_proof = _git_evidence(environment)
    _write(EVIDENCE / "base-commit.txt", base_sha + "\n")
    _write(EVIDENCE / "changed-files.txt", changed_text)
    _write(EVIDENCE / "dflash-core-diff-proof.txt", dflash_proof)
    _write(
        EVIDENCE / "environment.json",
        json.dumps(
            json.loads((DIAGNOSTIC_ROOT / "diagnostic.json").read_text(encoding="utf-8"))["environment"],
            indent=2, sort_keys=True,
        ) + "\n",
    )
    status = _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment)
    diff = _run("git-diff", ["git", "diff", "--no-ext-diff"], environment)
    _write(EVIDENCE / "git-status.txt", str(status["stdout"]))
    _write(EVIDENCE / "git-diff.patch", str(diff["stdout"]))

    gates = {
        "fresh_diagnostic_command_pass": commands[0]["exit_code"] == 0,
        "diagnostic_contract_pass": diagnostic_validation["pass"],
        "protocol_expected_blocker_exit": commands[1]["exit_code"] == 1,
        "protocol_metric_validity_pass": protocol_summary["metric_validity_pass"] is True,
        "quality_and_format_are_separate": (
            "output_exact_field_quality" in protocol_summary
            and "output_format_compliance" in protocol_summary
            and protocol_summary["output_exact_field_quality"] != protocol_summary["output_format_compliance"]
        ),
        "dataset_smoke_blocked": diagnostic_validation["report_summary"]["dataset_smoke_blocked"] is True,
        "compileall_pass": commands[2]["exit_code"] == 0,
        "pytest_pass": commands[3]["exit_code"] == 0,
        "git_diff_check_pass": commands[4]["exit_code"] == 0,
    }
    validation = {
        "pack_complete": all(gates.values()),
        "dataset_smoke_blocked": True,
        "gates": gates,
        "diagnostic_validation": diagnostic_validation,
        "protocol_summary": protocol_summary,
    }
    _write(EVIDENCE / "validation-summary.json", json.dumps(validation, indent=2, sort_keys=True) + "\n")

    required = [ROOT / name for name in SOURCE_FILES + ARTIFACT_FILES]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing review-pack members: {missing}")
    manifest_path = EVIDENCE / "archive-manifest.json"
    pack_members_path = EVIDENCE / "pack-members.txt"
    members = list(required)
    members.extend(
        path for path in EVIDENCE.rglob("*")
        if path.is_file() and path not in {manifest_path, pack_members_path}
    )
    forbidden_prefixes = (
        "models/", "data/raw/", "data/processed/", ".venv/", ".git/", "__pycache__/"
    )
    relative = [str(path.relative_to(ROOT)) for path in members]
    if any(name.startswith(forbidden_prefixes) or name.endswith(".tar.gz") for name in relative):
        raise RuntimeError("review pack member violates exclusion policy")
    planned = sorted({*relative, str(pack_members_path.relative_to(ROOT)), str(manifest_path.relative_to(ROOT))})
    _write(pack_members_path, "\n".join(planned) + "\n")
    members.append(pack_members_path)
    manifest = {
        "manifest_version": "ccdf.rec3-dflash-verifier-diagnostic-review-pack.v1",
        "base_commit_sha": base_sha,
        "self_entry_policy": "archive-manifest.json is omitted from its own hash map",
        "members": {
            str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in sorted(set(members))
        },
    }
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    all_members = [*members, manifest_path]
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE, "w:gz") as archive:
        for path in sorted(set(all_members)):
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)

    with tempfile.TemporaryDirectory(prefix="ccdf-rec3-verifier-pack-") as temporary:
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            archived = [item.name for item in archive.getmembers() if item.isfile()]
            if any(name.startswith(forbidden_prefixes) or name.endswith(".tar.gz") for name in archived):
                raise RuntimeError("sealed archive violates exclusion policy")
            archive.extractall(temporary, filter="data")
        extracted = Path(temporary)
        sealed = json.loads(
            (extracted / manifest_path.relative_to(ROOT)).read_text(encoding="utf-8")
        )
        expected = sorted([*sealed["members"], str(manifest_path.relative_to(ROOT))])
        if sorted(archived) != expected:
            raise RuntimeError("archive membership differs from manifest")
        listed = (extracted / pack_members_path.relative_to(ROOT)).read_text(encoding="utf-8").splitlines()
        if sorted(listed) != expected:
            raise RuntimeError("pack-members.txt differs from archive")
        verified = {
            name: {
                "bytes": (extracted / name).stat().st_size,
                "sha256": _sha256(extracted / name),
            } == expected_hash
            for name, expected_hash in sealed["members"].items()
        }
        if not all(verified.values()):
            raise RuntimeError(f"archive hash verification failed: {[name for name, ok in verified.items() if not ok]}")
    result = {
        "pack_complete": all(gates.values()),
        "dataset_smoke_blocked": True,
        "archive": str(ARCHIVE), "archive_sha256": _sha256(ARCHIVE),
        "member_count": len(archived),
        "manifest_hashes_verified": f"{sum(verified.values())}/{len(verified)}",
        "gates": gates,
    }
    print(json.dumps(result, sort_keys=True))
    if not result["pack_complete"]:
        raise SystemExit("REC-3 verifier diagnostic review pack failed validation")


if __name__ == "__main__":
    main()
