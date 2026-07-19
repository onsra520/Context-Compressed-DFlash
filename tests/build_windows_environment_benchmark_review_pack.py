"""Assemble and verify the Windows environment/benchmark rerun review pack."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import zipfile

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "docs/artifacts/windows-environment-benchmark-rerun"
STAGE = ARTIFACTS / "review-pack-windows-environment-benchmark-rerun"
ARCHIVE = ROOT / "docs/reviews/review-pack-windows-environment-benchmark-rerun.zip"
LOCK = ROOT / "docs/artifacts/environment/environment-lock-windows.txt"
MOCK = ROOT / "docs/artifacts/rec3-four-condition-mock10"
DATASET = ROOT / "docs/artifacts/dataset-protocol-evaluator-smoke-n10"
CANONICAL = ARTIFACTS / "canonical-regression"
PRIOR_DFLASH = (
    ROOT
    / "docs/audit/environment-package-refactor/review-pack-environment-package-refactor"
    / "tracked-source/src/ccdf/dflash"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".working", "__pycache__", "*.pyc"),
    )


def _environment_evidence(config_hash: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pre_root = ARTIFACTS / "environment/pre-fix"
    post_root = ARTIFACTS / "environment/post-fix"
    pre = {path.stem: _json(path) for path in sorted(pre_root.glob("*.json"))}
    post = {path.stem: _json(path) for path in sorted(post_root.glob("*.json"))}
    component_names = ("compressor", "baseline", "target", "drafter")
    comparison = {
        "config_sha256": config_hash,
        "pre_environment_status": pre["environment"]["status"],
        "post_environment_status": post["environment"]["status"],
        "pre_pip_check_exit": pre["environment"]["pip_check"]["exit_code"],
        "post_pip_check_exit": post["environment"]["pip_check"]["exit_code"],
        "pre_dataset_allocator": pre["environment"]["trusted_settings"]["dataset_allocator"],
        "post_dataset_allocator": post["environment"]["trusted_settings"]["dataset_allocator"],
        "post_effective_platform": post["environment"]["trusted_settings"][
            "dataset_effective_platform"
        ],
        "post_component_status": {name: post[name]["status"] for name in component_names},
        "post_component_config_hashes_match": all(
            post[name]["config_sha256"] == config_hash for name in component_names
        ),
        "baseline_dtype": {
            "pre_requested": pre["baseline"]["result"]["model_metadata"]["requested_dtype"],
            "pre_effective": pre["baseline"]["result"]["model_metadata"]["effective_dtypes"],
            "post_requested": post["baseline"]["result"]["model_metadata"]["requested_dtype"],
            "post_effective": post["baseline"]["result"]["model_metadata"]["effective_dtypes"],
        },
        "target_dtype": {
            "pre_requested": pre["target"]["result"]["requested_dtype"],
            "pre_effective": pre["target"]["result"]["effective_dtypes"],
            "post_requested": post["target"]["result"]["requested_dtype"],
            "post_effective": post["target"]["result"]["effective_dtypes"],
        },
        "drafter_dtype": {
            "requested": post["drafter"]["result"]["requested_dtype"],
            "effective": post["drafter"]["result"]["effective_dtypes"],
        },
    }
    matrix = [
        {
            "component": "PyTorch CUDA allocator",
            "finding": "expandable_segments is unsupported on native Windows",
            "classification": "unsupported_on_windows",
            "fatal": False,
            "pre_fix": "reproduced warning with successful allocation",
            "fix": "config.yml win32 platform override resolves cuda_allocator_conf to null",
            "post_fix": "PASS; no unsupported option is passed by benchmark workers",
            "evidence": "environment/pre-fix/environment.json and environment/post-fix/environment.json",
        },
        {
            "component": "Baseline and target AWQ",
            "finding": "BF16 request is cast to FP16 by AWQ CUDA kernels",
            "classification": "invalid_config_effective_dtype_claim",
            "fatal": False,
            "pre_fix": "requested bfloat16; effective tensors include float16",
            "fix": "models.baseline.dtype and models.dflash.target.dtype set to float16",
            "post_fix": "PASS; requested and effective AWQ dtype are FP16",
            "evidence": "pre/post baseline.json and target.json",
        },
        {
            "component": "AutoAWQ 0.2.9",
            "finding": "upstream package is deprecated but project inference remains operational",
            "classification": "deprecated_but_operational_compatibility_risk",
            "fatal": False,
            "pre_fix": "all AWQ component probes PASS through project compatibility alias",
            "fix": "version pinned to 0.2.9; backend not replaced",
            "post_fix": "PASS with deprecation warning retained as risk",
            "evidence": "worker stderr logs, pyproject.toml, post component probes",
        },
        {
            "component": "AutoAWQ Triton dependency metadata",
            "finding": "official triton 3.7.1 has no win_amd64 wheel; triton-windows provides module under another distribution name",
            "classification": "platform_package_metadata_incompatibility",
            "fatal": True,
            "pre_fix": "pip check failed: autoawq requires triton",
            "fix": "pinned triton-windows plus metadata-only local triton bridge",
            "post_fix": "pip check PASS and triton import origin remains triton-windows implementation",
            "evidence": "official-triton-windows-minimal-reproduction.txt and environment lock",
        },
        {
            "component": "LLMLingua dependency",
            "finding": "dependency emits torch_dtype deprecation warning",
            "classification": "deprecated_but_operational",
            "fatal": False,
            "pre_fix": "compressor inference PASS",
            "fix": "none; project source has no direct torch_dtype call",
            "post_fix": "compressor inference PASS",
            "evidence": "post-probe-compressor.stderr.txt and deprecated API scan",
        },
        {
            "component": "AutoAWQ dependency",
            "finding": "dependency invokes deprecated torch.jit.script",
            "classification": "deprecated_but_operational",
            "fatal": False,
            "pre_fix": "AWQ inference PASS",
            "fix": "none; project source has no direct torch.jit.script call",
            "post_fix": "all AWQ workers exit 0",
            "evidence": "mock10/dataset worker stderr and deprecated API scan",
        },
    ]
    return comparison, matrix


def _dflash_proof() -> dict[str, Any]:
    rows = []
    for current in sorted((ROOT / "src/ccdf/dflash").glob("*.py")):
        baseline = PRIOR_DFLASH / current.name
        rows.append({
            "path": str(current.relative_to(ROOT)),
            "current_sha256": _sha256(current),
            "pre_task_tracked_source_sha256": _sha256(baseline) if baseline.is_file() else None,
            "unchanged": baseline.is_file() and current.read_bytes() == baseline.read_bytes(),
            "current_last_write_utc": datetime.fromtimestamp(
                current.stat().st_mtime, timezone.utc
            ).isoformat(),
        })
    return {
        "pass": bool(rows) and all(row["unchanged"] for row in rows),
        "baseline": str(PRIOR_DFLASH.relative_to(ROOT)),
        "interpretation": (
            "Exact byte comparison with the sealed tracked-source snapshot that predates this "
            "Windows audit. The existing device-import relocation is preserved unchanged."
        ),
        "files": rows,
        "current_git_diff": _run(["git", "diff", "--", "src/ccdf/dflash"]),
    }


def _command_summary() -> dict[str, Any]:
    records = []
    for path in sorted((ARTIFACTS / "command-logs").glob("*.json")):
        try:
            record = _json(path)
        except json.JSONDecodeError:
            continue
        records.append({"record_file": path.name, **record})
    worker_groups = {
        "canonical": _json(CANONICAL / "worker_attempts.json"),
        "mock10": _json(MOCK / "condition_worker_attempts.json"),
        "dataset_smoke": _json(DATASET / "condition_worker_attempts.json"),
    }
    workers = [
        {"group": group, **record}
        for group, group_records in worker_groups.items() for record in group_records
    ]
    return {
        "commands": records,
        "workers": workers,
        "worker_summary": {
            "count": len(workers),
            "zero_exit": sum(record["exit_code"] == 0 for record in workers),
            "nonzero_exit": sum(record["exit_code"] != 0 for record in workers),
            "native_crash": sum(record.get("native_crash_code") is not None for record in workers),
            "retry": sum(int(record.get("retry_count", 0)) for record in workers),
            "resume_enabled": sum(record.get("resume_enabled") is True for record in workers),
        },
        "parent_nonzero_exits": [
            record["label"] for record in records if record.get("exit_code") != 0
        ],
    }


def _final_report(
    config_hash: str,
    environment: dict[str, Any],
    canonical: dict[str, Any],
    mock: dict[str, Any],
    dataset: dict[str, Any],
    commands: dict[str, Any],
    dflash: dict[str, Any],
    repo_checks: dict[str, bool],
) -> str:
    mock_dflash = mock["conditions"]["dflash-r1"]
    mock_cc = mock["conditions"]["cc-dflash-r2"]
    dataset_breakdown = _json(ARTIFACTS / "diagnostics/dataset-smoke-parity-failure.json")[
        "breakdown"
    ]
    breakdown_lines = "\n".join(
        f"- {row['dataset']} / {row['pair']}: {row['pass']}/{row['total']} parity"
        for row in dataset_breakdown
    )
    return f"""# FINAL_REPORT.md

## Overall verdict: FAIL

This result is sealed as **FAIL**. The Windows environment repair and canonical regression pass, but generated-token parity fails in both mock10 and dataset smoke. No failed benchmark was retried, resumed, or tuned with another block size/SDPA policy.

## Sealed identity

- Config: `config.yml`
- Config SHA-256: `{config_hash}`
- Effective platform: `win32`
- SDPA kernel: `math`
- Mock10 and dataset fixed block size: `8`
- Canonical fixed block size: `16`
- Local-only checkpoints: enabled; offline environment enforced in workers

## Environment audit and fixes: PASS

- Pre-fix `pip check`: FAIL; post-fix: PASS.
- Windows allocator: `expandable_segments` warning reproduced, classified unsupported/non-fatal, then removed through the config-declared `win32` override (`cuda_allocator_conf: null`).
- AWQ Baseline/target: pre-fix requested BF16 but effective FP16; post-fix config and probes both report FP16.
- Compressor, Baseline AWQ, target AWQ, and drafter: all post-fix isolated load/inference probes PASS with CUDA-resident parameters, buffers, and inference tensors.
- AutoAWQ remains pinned at 0.2.9; deprecation is a non-fatal compatibility risk because inference passes.
- Official Triton has no Windows wheel. The pinned `triton-windows==3.7.1.post27` implementation plus metadata-only bridge resolves the reproduced package-metadata failure without changing the backend.

## Canonical Baseline-AR vs DFlash-R1: PASS

- Runs: 50 Baseline + 50 DFlash.
- Rendered-input parity: {canonical['rendered_input_parity_count']}/{canonical['pair_count']}.
- Generated-token parity: {canonical['generated_token_parity_count']}/{canonical['pair_count']}.
- Frozen-reference parity: {canonical['canonical_reference_parity_count']}/{canonical['pair_count']}.
- DFlash peak reserved: {canonical['max_dflash_peak_reserved_bytes'] / 1024**3:.6f} GiB (limit 6 GiB).
- Determinism, structural checks, exact quality, and process stability: PASS.

## Four-condition mock10: FAIL

- Successful conditions: {mock['condition_success']}.
- Pair parity: {mock['pair_token_parity']} (required 20/20) — FAIL.
- Exact quality: {mock['output_exact_field_quality']}.
- Metric validity: {mock['metric_validity']['valid_rows']}/{mock['metric_validity']['checked_rows']}.
- DFlash-R1 peak reserved: {mock_dflash['max_full_request_peak_reserved_bytes'] / 1024**3:.6f} GiB.
- CC-DFlash-R2 peak reserved: {mock_cc['max_full_request_peak_reserved_bytes'] / 1024**3:.6f} GiB.
- Failure: compressed pair `mock_04`, identical rendered input, divergent 20 vs 21 generated tokens.

## GSM8K n10 + QMSum n10: FAIL

- Successful runs: {dataset['counts']['successful']}/{dataset['counts']['runs']}.
- Rendered-input parity: {dataset['pair_parity']['input_token_parity_count']}/{dataset['pair_parity']['pairs']}.
- Generated-token parity: {dataset['pair_parity']['generated_token_parity_count']}/{dataset['pair_parity']['pairs']} (required 40/40) — FAIL.
- GSM8K evaluator valid: {dataset['counts']['gsm8k_valid_samples']}/10.
- QMSum evaluator valid: {dataset['counts']['qmsum_valid_samples']}/10.
- QMSum coverage: {dataset['qmsum_compression']['coverage_rate'] * 100:.1f}%; hidden truncation: {dataset['qmsum_compression']['hidden_truncated_tokens']}.
- Metric validity: {dataset['counts']['metric_valid_runs']}/{dataset['counts']['runs']}.
- DFlash-R1 peak reserved: {dataset['conditions']['dflash-r1']['peak_reserved_vram_bytes'] / 1024**3:.6f} GiB.
- CC-DFlash-R2 peak reserved: {dataset['conditions']['cc-dflash-r2']['peak_reserved_vram_bytes'] / 1024**3:.6f} GiB.

Parity breakdown:

{breakdown_lines}

## Process stability

- Condition workers: {commands['worker_summary']['zero_exit']}/{commands['worker_summary']['count']} exit 0; native crashes {commands['worker_summary']['native_crash']}; retries {commands['worker_summary']['retry']}; resumes {commands['worker_summary']['resume_enabled']}.
- Mock10 and dataset parent commands exit 1 only after sealing parity gate failures; they are not native crashes. Therefore the global zero-nonzero-exit gate across every invoked parent and worker process is FAIL.

## Protocol deviation

- Requested clean execution order: canonical regression → mock10 → dataset smoke.
- Actual clean execution order: mock10 → canonical regression → dataset smoke.
- Order gate: **FAIL**. Mock10 had already been sealed on its first attempt before the ordering issue was identified. It was not rerun because retry/rerun and policy tuning after a parity failure are prohibited.

## Repository validation

- compileall: {'PASS' if repo_checks['compileall'] else 'FAIL'}
- pytest: {'PASS' if repo_checks['pytest'] else 'FAIL'} (`69 passed`)
- pip check: {'PASS' if repo_checks['pip_check'] else 'FAIL'}
- git diff --check: {'PASS' if repo_checks['git_diff_check'] else 'FAIL'}
- Dataset artifact verifier: FAIL only because the sealed summary/gate matrix are FAIL; it verified 80 rows, 40 parity records, four worker attempts, and all chunk maps.
- D-Flash core unchanged proof: {'PASS' if dflash['pass'] else 'FAIL'}.
- No commit or push was performed.

## Warning classification

- Unsupported on Windows: `expandable_segments`; non-fatal reproduction, config-fixed.
- Deprecated but operational: AutoAWQ, dependency `torch_dtype`, dependency `torch.jit.script`.
- Package/version incompatibility: AutoAWQ `triton` distribution metadata vs native Windows; fixed with pinned platform provider and metadata bridge.
- Invalid config claim: AWQ BF16 request while effective dtype was FP16; fixed to FP16.
- Fatal runtime warnings or native crashes: none.

## Final conclusion

**FAIL** — environment repair PASS and canonical regression PASS, but required mock10 and dataset generated-token parity gates do not pass. Raw evidence is preserved without fixture, reference, evaluator, block-size, or SDPA-policy changes made to manufacture a PASS.
"""


def _verify_zip(manifest: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ccdf-windows-pack-verify-") as temporary:
        target = Path(temporary)
        with zipfile.ZipFile(ARCHIVE) as archive:
            archive.extractall(target)
            names = sorted(name for name in archive.namelist() if not name.endswith("/"))
        checks = {}
        for name, expected in manifest["members"].items():
            path = target / name
            checks[name] = {
                "exists": path.is_file(),
                "bytes_match": path.is_file() and path.stat().st_size == expected["bytes"],
                "sha256_match": path.is_file() and _sha256(path) == expected["sha256"],
            }
        return {
            "pass": all(all(value.values()) for value in checks.values()),
            "archive_members": names,
            "manifest_member_count": len(manifest["members"]),
            "checks": checks,
        }


def main() -> None:
    config = load_config(ROOT / "config.yml")
    profile = config.resolve_dataset_smoke_profile()
    config_hash = _sha256(config.path)
    canonical = _json(CANONICAL / "summary.json")
    mock = _json(MOCK / "summary.json")
    dataset = _json(DATASET / "summary.json")
    if canonical["config_sha256"] != config_hash:
        raise RuntimeError("canonical config hash mismatch")
    if mock["source_config_sha256"] != config_hash or dataset["config_sha256"] != config_hash:
        raise RuntimeError("benchmark config hash mismatch")
    if canonical["status"] != "PASS" or mock["overall_pass"] or dataset["status"] != "FAIL":
        raise RuntimeError("unexpected sealed benchmark statuses")

    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    _copy_tree(ARTIFACTS / "environment", STAGE / "environment")
    _copy_tree(ARTIFACTS / "command-logs", STAGE / "command-logs")
    _copy_tree(ARTIFACTS / "diagnostics", STAGE / "diagnostics")
    _copy_tree(CANONICAL, STAGE / "canonical-regression")
    _copy_tree(MOCK, STAGE / "mock10")
    _copy_tree(DATASET, STAGE / "dataset-smoke")
    shutil.copy2(LOCK, STAGE / "environment/environment-lock-windows.txt")
    (STAGE / "config").mkdir(parents=True, exist_ok=True)
    shutil.copy2(config.path, STAGE / "config/config.yml")

    resolved_snapshot = profile.snapshot()
    resolved_snapshot.update({
        "effective_platform": profile.require("effective_platform"),
        "effective_platform_override": profile.require("effective_platform_override"),
        "source_config_sha256_verified": config_hash,
    })
    _write_json(STAGE / "config/resolved-config-and-platform.json", resolved_snapshot)
    environment_comparison, compatibility = _environment_evidence(config_hash)
    _write_json(STAGE / "environment/environment-pre-post-comparison.json", environment_comparison)
    _write_json(STAGE / "environment/compatibility-matrix.json", compatibility)

    commands = _command_summary()
    _write_json(STAGE / "commands/commands-with-duration.json", commands)
    dflash = _dflash_proof()
    _write_json(STAGE / "repository/dflash-core-unchanged-proof.json", dflash)
    git_status = _run(["git", "status", "--short", "--branch"])
    git_diff = _run(["git", "diff", "--binary"])
    git_diff_stat = _run(["git", "diff", "--stat"])
    changed_files = _run(["git", "status", "--short"])
    _write(STAGE / "repository/git-status.txt", git_status["stdout"] + git_status["stderr"])
    _write(STAGE / "repository/git-diff.patch", git_diff["stdout"])
    _write(STAGE / "repository/git-diff-stat.txt", git_diff_stat["stdout"])
    _write(STAGE / "repository/changed-files.txt", changed_files["stdout"])

    check_labels = {
        "compileall": "compileall.json",
        "pytest": "pytest.json",
        "pip_check": "pip-check.json",
        "git_diff_check": "git-diff-check.json",
    }
    repo_checks = {
        name: _json(ARTIFACTS / "command-logs" / filename)["exit_code"] == 0
        for name, filename in check_labels.items()
    }
    requirements = {
        "overall_status": "FAIL",
        "config_sha256": config_hash,
        "environment_post_fix": environment_comparison["post_environment_status"] == "PASS",
        "canonical_regression": canonical["status"],
        "mock10": {
            "status": "PASS" if mock["overall_pass"] else "FAIL",
            "condition_success": mock["condition_success"],
            "pair_parity": mock["pair_token_parity"],
            "exact_quality": mock["output_exact_field_quality"],
        },
        "dataset_smoke": {
            "status": dataset["status"],
            "runs": f"{dataset['counts']['successful']}/{dataset['counts']['runs']}",
            "rendered_input_parity": (
                f"{dataset['pair_parity']['input_token_parity_count']}/"
                f"{dataset['pair_parity']['pairs']}"
            ),
            "generated_token_parity": (
                f"{dataset['pair_parity']['generated_token_parity_count']}/"
                f"{dataset['pair_parity']['pairs']}"
            ),
            "gsm8k_evaluator_valid": dataset["counts"]["gsm8k_valid_samples"],
            "qmsum_evaluator_valid": dataset["counts"]["qmsum_valid_samples"],
            "qmsum_coverage": dataset["qmsum_compression"]["coverage_rate"],
            "hidden_truncation": dataset["qmsum_compression"]["hidden_truncated_tokens"],
            "metric_valid_runs": dataset["counts"]["metric_valid_runs"],
        },
        "worker_processes": commands["worker_summary"],
        "execution_order": {
            "requested": ["canonical-regression", "mock10", "dataset-smoke"],
            "actual": ["mock10", "canonical-regression", "dataset-smoke"],
            "pass": False,
            "rerun_performed": False,
        },
        "repository_checks": repo_checks,
        "dflash_core_unchanged": dflash["pass"],
        "no_commit_or_push_performed": True,
    }
    _write_json(STAGE / "requirements-audit.json", requirements)
    report = _final_report(
        config_hash, environment_comparison, canonical, mock, dataset,
        commands, dflash, repo_checks,
    )
    _write(STAGE / "FINAL_REPORT.md", report)

    forbidden_suffixes = {".zip", ".tar", ".gz", ".tgz", ".7z"}
    forbidden_names = {".venv", ".git", "__pycache__", ".cache"}
    forbidden = [
        str(path.relative_to(STAGE))
        for path in STAGE.rglob("*")
        if any(part in forbidden_names for part in path.parts)
        or (path.is_file() and path.suffix.lower() in forbidden_suffixes)
        or (path.is_file() and path.name in {"model.safetensors", "pytorch_model.bin"})
    ]
    if forbidden:
        raise RuntimeError(f"forbidden review-pack members: {forbidden}")

    planned = sorted(
        str(path.relative_to(STAGE)) for path in STAGE.rglob("*") if path.is_file()
    ) + ["manifest-verification.json", "sha256-manifest.json"]
    _write(STAGE / "pack-members.txt", "\n".join(sorted(set(planned + ["pack-members.txt"]))) + "\n")
    manifest_path = STAGE / "sha256-manifest.json"
    verification_path = STAGE / "manifest-verification.json"
    hashed = sorted(
        path for path in STAGE.rglob("*")
        if path.is_file() and path not in {manifest_path, verification_path}
    )
    manifest = {
        "manifest_version": "ccdf.windows-environment-benchmark-rerun.v1",
        "self_entry_policy": (
            "sha256-manifest.json and manifest-verification.json are excluded from the hash map"
        ),
        "members": {
            str(path.relative_to(STAGE)).replace("\\", "/"): {
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in hashed
        },
    }
    _write_json(manifest_path, manifest)
    local_verification = {
        name: {
            "bytes_match": (STAGE / name).stat().st_size == expected["bytes"],
            "sha256_match": _sha256(STAGE / name) == expected["sha256"],
        }
        for name, expected in manifest["members"].items()
    }
    _write_json(verification_path, {
        "pass": all(all(value.values()) for value in local_verification.values()),
        "scope": "staging directory before ZIP creation",
        "checks": local_verification,
    })

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(STAGE)).replace("\\", "/"))
    zip_verification = _verify_zip(manifest)
    if not zip_verification["pass"]:
        raise RuntimeError("ZIP manifest verification failed")
    _write_json(ARTIFACTS / "archive-verification.json", zip_verification)
    archive_sha = _sha256(ARCHIVE)
    _write(
        ROOT / "docs/reviews/review-pack-windows-environment-benchmark-rerun.zip.sha256",
        f"{archive_sha}  {ARCHIVE.name}\n",
    )
    print(json.dumps({
        "status": "FAIL",
        "archive": str(ARCHIVE),
        "archive_bytes": ARCHIVE.stat().st_size,
        "archive_sha256": archive_sha,
        "manifest_members": len(manifest["members"]),
        "verified": zip_verification["pass"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
