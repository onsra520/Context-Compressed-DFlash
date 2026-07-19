"""Build and independently verify the Windows auto-SDPA parity review ZIP."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable
import zipfile

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]
RUN_ROOT = ROOT / "docs/artifacts/windows-auto-sdpa-parity-fix-smoke-n10"
STAGE = ROOT / "docs/artifacts/review-pack-windows-auto-sdpa-parity-fix-smoke-n10"
ARCHIVE = ROOT / "docs/reviews/review-pack-windows-auto-sdpa-parity-fix-smoke-n10.zip"
SIDECAR = ROOT / "docs/reviews/review-pack-windows-auto-sdpa-parity-fix-smoke-n10.zip.sha256"
LOCK = ROOT / "docs/artifacts/environment/environment-lock-windows.txt"
PRIOR_WINDOWS_ENV = (
    ROOT / "docs/artifacts/windows-environment-benchmark-rerun/environment"
)
PRIOR_DFLASH = (
    ROOT
    / "docs/audit/environment-package-refactor/review-pack-environment-package-refactor/"
    "tracked-source/src/ccdf/dflash"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _lines(command: list[str]) -> list[str]:
    record = _run(command)
    if record["exit_code"] != 0:
        raise RuntimeError(f"command failed: {record}")
    return sorted({line.strip().replace("\\", "/") for line in record["stdout"].splitlines() if line.strip()})


def _copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    for path in sorted(source.rglob("*")):
        if path.is_file():
            relative = path.relative_to(source)
            if _forbidden(relative):
                raise RuntimeError(f"forbidden artifact member: {relative}")
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)


def _copy(source: Path, target: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _forbidden(relative: Path) -> bool:
    lowered = str(relative).lower().replace("\\", "/")
    forbidden_parts = {
        ".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".cache"
    }
    weights = {".safetensors", ".bin", ".pt", ".pth", ".gguf"}
    archives = {".zip", ".tar", ".gz", ".tgz", ".7z"}
    return (
        bool(forbidden_parts.intersection(relative.parts))
        or relative.suffix.lower() in weights
        or relative.suffix.lower() in archives
        or (relative.parts and relative.parts[0].lower() == "models")
        or "/data/raw/" in f"/{lowered}"
    )


def _production_changes() -> dict[str, Any]:
    scope = ["src", "scripts", "config.yml", "pyproject.toml"]
    modified = _lines(
        ["git", "diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD", "--", *scope]
    )
    untracked = _lines(
        ["git", "ls-files", "--others", "--exclude-standard", "--", *scope]
    )
    deleted = _lines(
        ["git", "diff", "--name-only", "--diff-filter=D", "HEAD", "--", *scope]
    )
    existing = sorted(
        path for path in set(modified + untracked) if (ROOT / path).is_file()
    )
    missing = sorted(path for path in set(modified + untracked) if not (ROOT / path).is_file())
    return {
        "scope": scope,
        "modified": modified,
        "untracked": untracked,
        "deleted": deleted,
        "existing_required_content": existing,
        "unexpected_missing_content": missing,
    }


def _stage_production_sources(changes: dict[str, Any]) -> dict[str, Any]:
    included = []
    for relative in changes["existing_required_content"]:
        source = ROOT / relative
        target = STAGE / "production-source" / relative
        _copy(source, target)
        included.append(relative)
    expected = set(changes["existing_required_content"])
    actual = {
        str(path.relative_to(STAGE / "production-source")).replace("\\", "/")
        for path in (STAGE / "production-source").rglob("*")
        if path.is_file()
    }
    return {
        **changes,
        "included_content": sorted(included),
        "included_content_set_match": actual == expected,
        "source_completeness_pass": (
            not changes["unexpected_missing_content"] and actual == expected
        ),
    }


def _worker_records() -> list[dict[str, Any]]:
    groups = {
        "canonical-math": RUN_ROOT / "canonical-math/worker_attempts.json",
        "mock10-auto": RUN_ROOT / "mock10/condition_worker_attempts.json",
        "dataset-auto": RUN_ROOT / "dataset-smoke/condition_worker_attempts.json",
    }
    return [
        {"group": group, **record}
        for group, path in groups.items()
        for record in _json(path)
    ]


def _command_records() -> list[dict[str, Any]]:
    records = []
    for path in sorted((RUN_ROOT / "command-logs").glob("*.json")):
        payload = _json(path)
        if isinstance(payload, dict) and "command" in payload and "exit_code" in payload:
            records.append({"record_file": path.name, **payload})
    return records


def _dflash_proof() -> dict[str, Any]:
    rows = []
    for current in sorted((ROOT / "src/ccdf/dflash").glob("*.py")):
        baseline = PRIOR_DFLASH / current.name
        rows.append({
            "path": str(current.relative_to(ROOT)).replace("\\", "/"),
            "current_sha256": _sha256(current),
            "sealed_pre_goal_sha256": _sha256(baseline) if baseline.is_file() else None,
            "unchanged": baseline.is_file() and current.read_bytes() == baseline.read_bytes(),
        })
    return {"pass": bool(rows) and all(row["unchanged"] for row in rows), "files": rows}


def _report(
    status: str,
    config_hash: str,
    canonical: dict[str, Any],
    mock: dict[str, Any],
    dataset: dict[str, Any],
    caps: dict[str, Any],
    diagnostics: dict[str, Any],
    requirements: dict[str, Any],
) -> str:
    failed = [name for name, passed in requirements["hard_gates"].items() if not passed]
    failed_lines = "\n".join(f"- {name}" for name in failed) or "- None"
    qmsum_caps = caps["by_dataset"]["qmsum"]
    return f"""# FINAL_REPORT.md

## Overall verdict: {status}

This report is sealed from the runtime summaries and validation records in this ZIP.

## Configuration and SDPA

- Config SHA-256: `{config_hash}`
- Frozen canonical profile: `attention_backend=sdpa`, `sdpa_kernel=math`, block size 16.
- Active mock10/dataset profiles: `attention_backend=sdpa`, `sdpa_kernel=auto`, block size 8.
- Auto policy leaves Flash, memory-efficient, and math available to the PyTorch dispatcher.
- The separate profiler probe records actual execution for its representative CUDA shape; enabled flags alone are not presented as execution evidence.

## Canonical math regression: {canonical['status']}

- Runs: {canonical['run_counts']['baseline']} Baseline + {canonical['run_counts']['dflash']} DFlash.
- Rendered-input parity: {canonical['rendered_input_parity_count']}/{canonical['pair_count']}.
- Generated-token parity: {canonical['generated_token_parity_count']}/{canonical['pair_count']}.
- Frozen-reference parity: {canonical['canonical_reference_parity_count']}/{canonical['pair_count']}.
- DFlash peak reserved: {canonical['max_dflash_peak_reserved_bytes'] / 1024**3:.6f} GiB.

## Four-condition mock10 auto: {'PASS' if mock['overall_pass'] else 'FAIL'}

- Successful runs: {mock['condition_success']}.
- Generated-token parity: {mock['pair_token_parity']}.
- Exact quality: {mock['output_exact_field_quality']}.
- Metric validity: {mock['metric_validity']['valid_rows']}/{mock['metric_validity']['checked_rows']}.

## GSM8K n10 + QMSum n10 auto: {dataset['status']}

- Successful runs: {dataset['counts']['successful']}/{dataset['counts']['runs']}.
- Rendered-input parity: {dataset['pair_parity']['input_token_parity_count']}/{dataset['pair_parity']['pairs']}.
- Generated-token parity: {dataset['pair_parity']['generated_token_parity_count']}/{dataset['pair_parity']['pairs']}.
- GSM8K cap: {dataset['generation_limits']['gsm8k']} tokens.
- QMSum cap: {dataset['generation_limits']['qmsum']} tokens; cap-hits {qmsum_caps['cap_hits']}/{qmsum_caps['runs']}.
- Cap-hit outputs are evaluated only as actually generated prefixes and are never marked complete.
- QMSum coverage: {dataset['qmsum_compression']['coverage_rate'] * 100:.1f}%; hidden truncation: {dataset['qmsum_compression']['hidden_truncated_tokens']}.
- DFlash-R1 peak reserved: {dataset['conditions']['dflash-r1']['peak_reserved_vram_bytes'] / 1024**3:.6f} GiB.
- CC-DFlash-R2 peak reserved: {dataset['conditions']['cc-dflash-r2']['peak_reserved_vram_bytes'] / 1024**3:.6f} GiB.

## Parity diagnostics

- First-divergence records: {diagnostics['failure_count']}.
- Every failure record contains rendered input IDs/hash, AR and D-Flash tokens, verifier counters, cache/block state, and stopping state when available.
- Unisolated block-shaped numerical drift is not mislabeled as SDPA drift.

## D-Flash core blocker

- Sealed evidence shows same-input AR versus block-verification target top-1 divergence while cache progression and structural checks pass.
- Resolving the remaining parity failures would require changing the D-Flash core/numerical verification path or introducing an AR oracle fallback. Both are outside the permitted fix scope, so the blocker remains sealed as FAIL.

## Portability and source completeness

- Windows Triton bridge lock entry is project-relative: **{'PASS' if requirements['windows_lock_project_relative'] else 'FAIL'}**.
- All modified/untracked production sources in the declared scope are included: **{'PASS' if requirements['source_completeness_pass'] else 'FAIL'}**.
- D-Flash core unchanged from the sealed pre-goal snapshot: **{'PASS' if requirements['dflash_core_unchanged'] else 'FAIL'}**.
- No commit or push was performed.

## Failed hard gates

{failed_lines}

## Final conclusion

**{status}** — this verdict follows the configured hard gates; fixtures, expected answers, evaluator rules, block size, and stopping contract were not altered to manufacture a pass.
"""


def _verify_archive(manifest: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ccdf-auto-sdpa-pack-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(ARCHIVE) as archive:
            names = sorted(name for name in archive.namelist() if not name.endswith("/"))
            archive.extractall(target)
        mismatches = []
        for name, expected in manifest["members"].items():
            path = target / name
            if (
                not path.is_file()
                or path.stat().st_size != expected["bytes"]
                or _sha256(path) != expected["sha256"]
            ):
                mismatches.append(name)
        forbidden = [name for name in names if _forbidden(Path(name))]
        return {
            "pass": not mismatches and not forbidden,
            "archive_members": len(names),
            "manifest_members": len(manifest["members"]),
            "hash_or_size_mismatches": mismatches,
            "forbidden_members": forbidden,
        }


def main() -> None:
    config = load_config(ROOT / "config.yml")
    config_hash = _sha256(config.path)
    canonical = _json(RUN_ROOT / "canonical-math/summary.json")
    mock = _json(RUN_ROOT / "mock10/summary.json")
    dataset = _json(RUN_ROOT / "dataset-smoke/summary.json")
    caps = _json(RUN_ROOT / "dataset-smoke/cap_hit_breakdown.json")
    diagnostics = _json(RUN_ROOT / "parity-diagnostics/first-divergences.json")
    sdpa_probe = _json(RUN_ROOT / "environment/sdpa-runtime-probe.json")
    environment = _json(RUN_ROOT / "environment/environment.json")
    commands = _command_records()
    workers = _worker_records()
    benchmark_labels = ["canonical-math", "mock10-auto", "dataset-auto"]
    benchmark_commands = sorted(
        (record for record in commands if record["label"] in benchmark_labels),
        key=lambda record: record["started_at_utc"],
    )
    actual_order = [record["label"] for record in benchmark_commands]
    repository_labels = ("compileall", "pytest", "pip-check", "git-diff-check")
    repository_checks = {
        label: next(
            (record["exit_code"] == 0 for record in commands if record["label"] == label),
            False,
        )
        for label in repository_labels
    }
    changes = _production_changes()
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    (RUN_ROOT / "archive-verification.json").unlink(missing_ok=True)
    _copy_tree(RUN_ROOT, STAGE / "evidence")
    source_completeness = _stage_production_sources(changes)
    _write_json(STAGE / "repository/source-completeness.json", source_completeness)
    _write_json(STAGE / "repository/deleted-production-paths.json", changes["deleted"])
    _copy(LOCK, STAGE / "environment/environment-lock-windows.txt")
    _copy_tree(PRIOR_WINDOWS_ENV, STAGE / "environment/prior-windows-rerun")
    for relative in (
        "tests/build_windows_auto_sdpa_parity_diagnostics.py",
        "tests/build_windows_auto_sdpa_parity_review_pack.py",
        "tests/run_windows_canonical_regression.py",
        "tests/run_windows_command_capture.py",
        "tests/run_windows_sdpa_runtime_probe.py",
    ):
        _copy(ROOT / relative, STAGE / "review-tooling" / relative)

    lock_text = LOCK.read_text(encoding="utf-8")
    lock_project_relative = (
        "./scripts/windows_triton_compat" in lock_text
        and "file:///D:/" not in lock_text
        and "file:///d:/" not in lock_text.lower()
    )
    dflash = _dflash_proof()
    _write_json(STAGE / "repository/dflash-core-unchanged-proof.json", dflash)
    status_record = _run(["git", "status", "--short", "--untracked-files=all"])
    diff_record = _run(["git", "diff", "--binary", "HEAD"])
    _write(STAGE / "repository/git-status.txt", status_record["stdout"] + status_record["stderr"])
    _write(STAGE / "repository/git-diff.patch", diff_record["stdout"] + diff_record["stderr"])
    _write_json(STAGE / "commands/command-records.json", commands)
    _write_json(STAGE / "commands/worker-records.json", workers)
    execution_order = {
        "required": benchmark_labels,
        "actual": actual_order,
        "pass": actual_order == benchmark_labels,
        "records": benchmark_commands,
    }
    _write_json(STAGE / "commands/execution-order.json", execution_order)

    config_hashes_match = (
        canonical.get("config_sha256") == config_hash
        and mock.get("source_config_sha256") == config_hash
        and dataset.get("config_sha256") == config_hash
        and diagnostics.get("config_sha256") == config_hash
        and sdpa_probe.get("config_sha256") == config_hash
    )
    worker_stability = (
        len(workers) == 10
        and all(record.get("exit_code") == 0 for record in workers)
        and all(record.get("retry_count") == 0 for record in workers)
        and all(record.get("resume_enabled") is False for record in workers)
        and all(record.get("native_crash_code") is None for record in workers)
        and all(record.get("faulthandler_enabled") is True for record in workers)
    )
    parent_stability = (
        len(benchmark_commands) == 3
        and all(record["exit_code"] == 0 for record in benchmark_commands)
        and all(record["python_faulthandler_environment"] == "1" for record in benchmark_commands)
    )
    sdpa_contract = (
        sdpa_probe["canonical_profile"]["configured_policy"] == "math"
        and sdpa_probe["canonical_profile"]["effective_allowed_backends"] == ["math"]
        and sdpa_probe["active_profile"]["configured_policy"] == "auto"
        and set(sdpa_probe["active_profile"]["effective_allowed_backends"])
        == {"flash", "memory_efficient", "math"}
        and sdpa_probe["active_profile"]["backend_observed_from_profiler"] is True
    )
    hard_gates = {
        "config_hashes_match": config_hashes_match,
        "canonical_regression_pass": canonical["status"] == "PASS",
        "mock10_pass": mock["overall_pass"] is True,
        "dataset_smoke_pass": dataset["status"] == "PASS",
        "benchmark_execution_order_pass": execution_order["pass"],
        "parent_process_stability_pass": parent_stability,
        "worker_process_stability_pass": worker_stability,
        "sdpa_policy_and_probe_pass": sdpa_contract,
        "environment_probe_pass": environment.get("status") == "PASS",
        "repository_checks_pass": all(repository_checks.values()),
        "source_completeness_pass": source_completeness["source_completeness_pass"],
        "windows_lock_project_relative": lock_project_relative,
        "dflash_core_unchanged": dflash["pass"],
    }
    status = "PASS" if all(hard_gates.values()) else "FAIL"
    requirements = {
        "overall_status": status,
        "config_sha256": config_hash,
        "hard_gates": hard_gates,
        "repository_checks": repository_checks,
        "source_completeness_pass": source_completeness["source_completeness_pass"],
        "windows_lock_project_relative": lock_project_relative,
        "dflash_core_unchanged": dflash["pass"],
        "dflash_core_blocker": (
            "same-input target top-1 divergence in structurally valid block verification; "
            "a permitted orchestration/stopping/metric fix is not evidenced"
            if diagnostics["failure_count"]
            else None
        ),
        "execution_order": execution_order,
        "worker_count": len(workers),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "no_commit_or_push_performed": True,
    }
    _write_json(STAGE / "requirements-audit.json", requirements)
    _write(
        STAGE / "FINAL_REPORT.md",
        _report(status, config_hash, canonical, mock, dataset, caps, diagnostics, requirements),
    )

    manifest_path = STAGE / "sha256-manifest.json"
    verification_path = STAGE / "manifest-verification.json"
    planned = sorted(
        str(path.relative_to(STAGE)).replace("\\", "/")
        for path in STAGE.rglob("*")
        if path.is_file()
    ) + ["manifest-verification.json", "sha256-manifest.json"]
    _write(STAGE / "pack-members.txt", "\n".join(sorted(set(planned + ["pack-members.txt"]))) + "\n")
    forbidden = [
        str(path.relative_to(STAGE)).replace("\\", "/")
        for path in STAGE.rglob("*")
        if path.is_file() and _forbidden(path.relative_to(STAGE))
    ]
    if forbidden:
        raise RuntimeError(f"forbidden staged members: {forbidden}")
    hashed = sorted(
        path
        for path in STAGE.rglob("*")
        if path.is_file() and path not in {manifest_path, verification_path}
    )
    manifest = {
        "manifest_version": "ccdf.windows-auto-sdpa-parity-fix-smoke-n10.v1",
        "self_entry_policy": "manifest and verification files are excluded from the hash map",
        "members": {
            str(path.relative_to(STAGE)).replace("\\", "/"): {
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in hashed
        },
    }
    _write_json(manifest_path, manifest)
    local_checks = {
        name: {
            "bytes_match": (STAGE / name).stat().st_size == expected["bytes"],
            "sha256_match": _sha256(STAGE / name) == expected["sha256"],
        }
        for name, expected in manifest["members"].items()
    }
    _write_json(verification_path, {
        "pass": all(all(check.values()) for check in local_checks.values()),
        "checks": local_checks,
    })
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVE.unlink(missing_ok=True)
    with zipfile.ZipFile(
        ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(STAGE)).replace("\\", "/"))
    verification = _verify_archive(manifest)
    if not verification["pass"]:
        raise RuntimeError(f"ZIP verification failed: {verification}")
    _write_json(RUN_ROOT / "archive-verification.json", verification)
    archive_hash = _sha256(ARCHIVE)
    _write(SIDECAR, f"{archive_hash}  {ARCHIVE.name}\n")
    print(json.dumps({
        "status": status,
        "archive": str(ARCHIVE),
        "archive_sha256": archive_hash,
        "archive_bytes": ARCHIVE.stat().st_size,
        "manifest_members": len(manifest["members"]),
        "source_completeness_pass": source_completeness["source_completeness_pass"],
        "verified": verification["pass"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
