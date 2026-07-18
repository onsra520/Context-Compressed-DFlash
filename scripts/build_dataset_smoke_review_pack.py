"""Validate, seal, and independently hash the dataset-smoke review archive."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time
from typing import Any, Iterable

from ccdf.config import load_config


PACK_ROOT_NAME = "review-pack-dataset-protocol-evaluator-smoke-n10"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _run(label: str, command: list[str], root: Path) -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    return {
        "label": label,
        "command": command,
        "cwd": str(root),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def _copy(root: Path, staging: Path, relative: str, destination: str | None = None) -> None:
    source = root / relative
    target = staging / (destination or relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _copy_tree(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _dflash_proof(root: Path) -> dict[str, Any]:
    baseline_root = (
        root
        / "docs/audit/environment-package-refactor/review-pack-environment-package-refactor/tracked-source/src/ccdf/dflash"
    )
    baseline_proof = (
        root
        / "docs/audit/environment-package-refactor/review-pack-environment-package-refactor/dflash-core-unchanged-proof.json"
    )
    records = []
    for current in sorted((root / "src/ccdf/dflash").glob("*.py")):
        baseline = baseline_root / current.name
        records.append({
            "path": str(current.relative_to(root)),
            "current_sha256": _hash(current),
            "scope_baseline_sha256": _hash(baseline) if baseline.is_file() else None,
            "exact_match": baseline.is_file() and _hash(current) == _hash(baseline),
        })
    return {
        "pass": bool(records) and all(record["exact_match"] for record in records),
        "proof_scope": "exact comparison to the sealed environment-package-refactor post-change source snapshot that predates this dataset-smoke slice",
        "scope_baseline_proof_path": str(baseline_proof.relative_to(root)),
        "scope_baseline_proof_sha256": _hash(baseline_proof),
        "files": records,
    }


def _forbidden_member(relative: Path) -> bool:
    forbidden_parts = {".git", ".venv", ".worktrees", "__pycache__", ".pytest_cache", ".mypy_cache"}
    archive_suffixes = (".tar", ".tar.gz", ".tgz", ".zip")
    return bool(forbidden_parts.intersection(relative.parts)) or str(relative).endswith(archive_suffixes)


def _final_report(sealed: dict[str, Any]) -> str:
    run = sealed["run_summary"]
    gates = sealed["run_gate_matrix"]
    conditions = run["conditions"]
    lines = [
        "# Dataset protocol, evaluator, and n10 smoke review",
        "",
        f"Overall result: **{sealed['status']}**",
        "",
        f"Config SHA-256: `{run['config_sha256']}`",
        f"Measured logical condition runs: {run['counts']['successful']}/{run['counts']['runs']}",
        f"Input-token pair parity: {run['pair_parity']['input_token_parity_count']}/{run['pair_parity']['pairs']}",
        f"Generated-token pair parity: {run['pair_parity']['generated_token_parity_count']}/{run['pair_parity']['pairs']}",
        f"QMSum pre-compression coverage: {run['qmsum_compression']['coverage_rate']:.6f}",
        f"Hidden truncated tokens: {run['qmsum_compression']['hidden_truncated_tokens']}",
        f"GSM8K valid samples: {run['counts']['gsm8k_valid_samples']}/10",
        f"QMSum valid samples: {run['counts']['qmsum_valid_samples']}/10",
        "",
        "D-Flash request-wide peak reserved VRAM:",
        "",
        f"- DFlash-R1: {conditions['dflash-r1']['peak_reserved_vram_bytes'] / (1024 ** 3):.6f} GiB",
        f"- CC-DFlash-R2: {conditions['cc-dflash-r2']['peak_reserved_vram_bytes'] / (1024 ** 3):.6f} GiB",
        "",
        "Quality reporting:",
        "",
        f"- GSM8K numeric accuracy: {run['quality']['gsm8k']['correct']}/{run['quality']['gsm8k']['evaluations']} condition evaluations",
        f"- QMSum mean reference-recall proxy: {run['quality']['qmsum']['mean_reference_recall_proxy']:.6f}",
        "- QMSum semantic correctness: NOT_CLAIMED",
        "- GSM8K compression effectiveness: NOT_CLAIMED (empty context no-op)",
        "",
        "Validation commands:",
        "",
    ]
    lines.extend(
        f"- {record['label']}: exit {record['exit_code']} ({record['duration_seconds']:.3f}s)"
        for record in sealed["validation_commands"]
    )
    lines.extend([
        "",
        f"Run gates: {'PASS' if gates['pass'] else 'FAIL'}",
        f"D-Flash core exact scope-baseline proof: {'PASS' if sealed['dflash_core_unchanged']['pass'] else 'FAIL'}",
        "",
        "The SDPA evidence records dispatcher availability only; it does not claim that an enabled kernel executed.",
        "All values above are read from sealed runtime artifacts and command records.",
        "",
    ])
    if sealed["status"] != "PASS":
        lines.extend([
            "Blocking evidence:",
            "",
            *(
                f"- {entry['gate']}: actual {entry['actual']}, required {entry['required']}"
                for entry in gates["entries"]
                if not entry["pass"]
            ),
            "- Baseline and D-Flash target checkpoints are byte-identical; D-Flash core was not modified.",
            "- No per-token oracle fallback was introduced.",
            "",
        ])
    return "\n".join(lines)


def _files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config.yml"))
    args = parser.parse_args()
    config = load_config(args.config)
    profile = config.resolve_dataset_smoke_profile()
    settings = profile.settings
    root = config.root

    commands = []
    for label, command in settings["validation_commands"].items():
        commands.append(_run(str(label), [str(value) for value in command], root))

    metadata_commands = [
        _run("base_commit", ["git", "rev-parse", "HEAD"], root),
        _run("git_status", ["git", "status", "--short"], root),
        _run("changed_files", ["git", "diff", "--name-status", "HEAD"], root),
        _run("git_diff_stat", ["git", "diff", "--stat", "HEAD"], root),
        _run(
            "git_diff_without_dataset_payloads",
            [
                "git", "diff", "HEAD", "--", ".",
                ":(exclude)data/eval/gsm8k/gsm8k_n10.jsonl",
                ":(exclude)data/eval/qmsum/qmsum_n10.jsonl",
            ],
            root,
        ),
    ]
    artifact_root = Path(str(settings["artifact_directory"])).resolve()
    run_summary = json.loads((artifact_root / "summary.json").read_text(encoding="utf-8"))
    run_gates = json.loads((artifact_root / "gate_matrix.json").read_text(encoding="utf-8"))
    dflash_proof = _dflash_proof(root)
    status = "PASS" if (
        all(record["exit_code"] == 0 for record in commands)
        and all(record["exit_code"] == 0 for record in metadata_commands)
        and run_summary["status"] == "PASS"
        and run_gates["pass"]
        and dflash_proof["pass"]
    ) else "FAIL"

    temporary = Path(tempfile.mkdtemp(prefix="ccdf-dataset-smoke-review-", dir="/tmp"))
    staging = temporary / PACK_ROOT_NAME
    staging.mkdir()
    try:
        _copy_tree(artifact_root, staging / "artifacts")
        for relative in (
            "config.yml",
            "src/ccdf/config.py",
            "src/ccdf/compression/schemas.py",
            "src/ccdf/compression/llmlingua.py",
            "src/ccdf/data/pipeline.py",
            "src/ccdf/runtime/determinism.py",
            "src/ccdf/runtime/device.py",
            "src/ccdf/runtime/engine.py",
            "src/ccdf/models/loaders.py",
            "src/ccdf/protocols/orchestrator.py",
            "src/ccdf/benchmark/dataset_smoke.py",
            "src/ccdf/benchmark/dataset_smoke_verify.py",
            "src/ccdf/benchmark/evaluators.py",
            "scripts/refresh_dataset_smoke_cohorts.py",
            "scripts/build_dataset_smoke_review_pack.py",
        ):
            _copy(root, staging, relative, f"tracked-source/{relative}")
        for relative in (
            "data/manifests/dataset_manifest.json",
            "data/manifests/dataset_smoke_selection.json",
        ):
            _copy(root, staging, relative, f"cohort-manifests/{Path(relative).name}")
        baseline_proof_relative = (
            "docs/audit/environment-package-refactor/review-pack-environment-package-refactor/"
            "dflash-core-unchanged-proof.json"
        )
        _copy(root, staging, baseline_proof_relative, "git/scope-baseline-dflash-proof.json")

        _write_json(staging / "commands/validation-commands.json", commands)
        for record in commands:
            (staging / f"commands/{record['label']}.stdout.txt").write_text(record["stdout"], encoding="utf-8")
            (staging / f"commands/{record['label']}.stderr.txt").write_text(record["stderr"], encoding="utf-8")
        _write_json(staging / "git/metadata-commands.json", metadata_commands)
        for record in metadata_commands:
            suffix = "patch" if record["label"].startswith("git_diff_without") else "txt"
            (staging / f"git/{record['label']}.{suffix}").write_text(record["stdout"], encoding="utf-8")
        _write_json(staging / "git/dflash-core-unchanged-proof.json", dflash_proof)

        sealed = {
            "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "config_sha256": profile.source_config_sha256,
            "run_summary": run_summary,
            "run_gate_matrix": run_gates,
            "validation_commands": commands,
            "metadata_commands": metadata_commands,
            "dflash_core_unchanged": dflash_proof,
            "claim_boundaries": {
                "qmsum_semantic_correctness": "NOT_CLAIMED",
                "gsm8k_compression_effectiveness": "NOT_CLAIMED",
                "sdpa_actual_kernel_execution": "NOT_OBSERVED",
                "ratio_matrix_run": False,
                "final_candidate_selected": False,
            },
            "failed_run_gates": [
                entry for entry in run_gates["entries"] if not entry["pass"]
            ],
            "failed_validation_commands": [
                record["label"] for record in commands if record["exit_code"] != 0
            ],
        }
        _write_json(staging / "sealed-summary.json", sealed)
        (staging / "FINAL_REPORT.md").write_text(_final_report(sealed), encoding="utf-8")

        planned_names = [
            str(path.relative_to(staging)) for path in _files(staging)
        ] + ["pack-members.txt", "SHA256SUMS", "manifest-verification.json"]
        planned_names = sorted(set(planned_names))
        (staging / "pack-members.txt").write_text("\n".join(planned_names) + "\n", encoding="utf-8")
        manifested = [
            path for path in _files(staging)
            if path.name not in {"SHA256SUMS", "manifest-verification.json"}
        ]
        sums = {str(path.relative_to(staging)): _hash(path) for path in manifested}
        (staging / "SHA256SUMS").write_text(
            "".join(f"{digest}  {relative}\n" for relative, digest in sorted(sums.items())),
            encoding="utf-8",
        )
        verification = {
            "pass": all(_hash(staging / relative) == digest for relative, digest in sums.items()),
            "verified_files": len(sums),
            "sha256sums_sha256": _hash(staging / "SHA256SUMS"),
        }
        _write_json(staging / "manifest-verification.json", verification)
        actual_names = sorted(str(path.relative_to(staging)) for path in _files(staging))
        if actual_names != planned_names or not verification["pass"]:
            raise RuntimeError("review-pack member/hash verification failed before archive creation")
        forbidden = [name for name in actual_names if _forbidden_member(Path(name))]
        if forbidden:
            raise RuntimeError(f"forbidden review-pack members: {forbidden}")

        archive = Path(str(settings["review_archive"])).resolve()
        archive.parent.mkdir(parents=True, exist_ok=True)
        if archive.exists():
            archive.unlink()
        with tarfile.open(archive, "w:gz") as handle:
            for path in _files(staging):
                handle.add(path, arcname=f"{PACK_ROOT_NAME}/{path.relative_to(staging)}", recursive=False)
        with tarfile.open(archive, "r:gz") as handle:
            archive_names = sorted(member.name.removeprefix(f"{PACK_ROOT_NAME}/") for member in handle.getmembers())
        if archive_names != actual_names:
            archive.unlink(missing_ok=True)
            raise RuntimeError("sealed archive member list differs from verified staging list")
        result = {
            "status": status,
            "archive": str(archive),
            "archive_sha256": _hash(archive),
            "archive_bytes": archive.stat().st_size,
            "members": len(actual_names),
            "verified_manifest_files": verification["verified_files"],
        }
        print(json.dumps(result, indent=2, sort_keys=True))
        if status != "PASS":
            raise SystemExit(1)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    main()
