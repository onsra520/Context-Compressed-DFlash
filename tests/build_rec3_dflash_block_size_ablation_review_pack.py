"""Build the verified REC-3 D-Flash block-size ablation review pack."""

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
ARTIFACT_ROOT = ROOT / "docs/artifacts/rec3-dflash-block-size-ablation-mock10"
EVIDENCE = ROOT / "docs/artifacts/review-pack/rec3-dflash-block-size-ablation-mock10"
ARCHIVE = ROOT / "docs/reviews/review-pack-rec3-dflash-block-size-ablation-mock10.tar.gz"
REQUIRED_SOURCE_FILES = [
    ".gitignore", "config.yml", "pyproject.toml",
    "src/ccdf/config.py", "src/ccdf/determinism.py", "src/ccdf/device.py", "src/ccdf/schemas.py",
    "src/ccdf/models/loaders.py", "src/ccdf/runtime/engine.py",
    "src/ccdf/inference/baseline.py", "src/ccdf/inference/sampling.py",
    "src/ccdf/dflash/acceptance.py", "src/ccdf/dflash/generate.py",
    "src/ccdf/dflash/policy.py", "src/ccdf/dflash/verifier.py",
    "tests/run_rec3_four_condition_protocol.py",
    "tests/run_rec3_dflash_verifier_diagnostic.py",
    "tests/run_rec3_dflash_block_size_ablation.py",
    "tests/build_rec3_dflash_block_size_ablation_review_pack.py",
    "tests/test_rec3_protocol_helpers.py", "tests/test_dflash_integration.py", "tests/test_metrics.py",
]
ARTIFACT_FILES = [
    "docs/artifacts/rec3-dflash-block-size-ablation-mock10/ablation.json",
    "docs/artifacts/rec3-dflash-block-size-ablation-mock10/summary.json",
    "docs/artifacts/rec3-dflash-block-size-ablation-mock10/future_token_invariance_logits.pt",
    "docs/artifacts/rec3-four-condition-mock10/raw_runs.json",
    "docs/artifacts/rec3-four-condition-mock10/summary.json",
]
SOURCE_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".json"}


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


def _git_lines(command: list[str], environment: dict[str, str]) -> list[str]:
    result = _run("git-source-discovery", command, environment)
    if result["exit_code"] != 0:
        raise RuntimeError(f"Git source discovery failed: {command}: {result['stderr']}")
    return [line.strip() for line in str(result["stdout"]).splitlines() if line.strip()]


def _discover_changed_source_files(environment: dict[str, str], base_sha: str) -> list[str]:
    candidates = set()
    for command in (
        ["git", "diff", "--name-only", base_sha],
        ["git", "diff", "--cached", "--name-only", base_sha],
        ["git", "ls-files", "--others", "--exclude-standard"],
    ):
        candidates.update(_git_lines(command, environment))
    return sorted(
        name for name in candidates
        if (ROOT / name).is_file()
        and (
            Path(name).suffix in SOURCE_SUFFIXES
            or name.startswith(("src/", "scripts/", "tests/"))
        )
    )


def _git_evidence(environment: dict[str, str]) -> tuple[str, str, str, str, list[str]]:
    base_result = _run("base-commit", ["git", "rev-parse", "HEAD"], environment)
    if base_result["exit_code"] != 0:
        raise RuntimeError(f"cannot resolve base commit: {base_result['stderr']}")
    base_sha = str(base_result["stdout"]).strip()
    changed_sources = _discover_changed_source_files(environment, base_sha)
    changed_commands = [
        _run("git-diff-name-status", ["git", "diff", "--name-status", base_sha], environment),
        _run("git-diff-cached-name-status", ["git", "diff", "--cached", "--name-status", base_sha], environment),
        _run("git-untracked", ["git", "ls-files", "--others", "--exclude-standard"], environment),
        _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment),
        _run(
            "git-ignored-validation-sources",
            [
                "git", "check-ignore", "-v",
                "tests/run_rec3_four_condition_protocol.py",
                "tests/run_rec3_dflash_verifier_diagnostic.py",
                "tests/run_rec3_dflash_block_size_ablation.py",
                "tests/build_rec3_dflash_block_size_ablation_review_pack.py",
                "tests/test_rec3_protocol_helpers.py",
            ],
            environment,
        ),
    ]
    changed_text = "".join(
        f"# {item['label']}\n$ {' '.join(item['command'])}\nexit={item['exit_code']}\n{item['stdout']}{item['stderr']}\n"
        for item in changed_commands
    )
    dflash_commands = [
        _run("dflash-status", ["git", "status", "--short", "--", "src/ccdf/dflash"], environment),
        _run("dflash-diff-numstat", ["git", "diff", "--numstat", base_sha, "--", "src/ccdf/dflash"], environment),
        _run("dflash-untracked", ["git", "ls-files", "--others", "--exclude-standard", "src/ccdf/dflash"], environment),
        _run("dflash-diff-check", ["git", "diff", "--check", base_sha, "--", "src/ccdf/dflash"], environment),
    ]
    dflash_text = (
        f"base_commit_sha={base_sha}\nclaim=No D-Flash core patch was applied.\n\n"
        + "".join(
            f"# {item['label']}\n$ {' '.join(item['command'])}\nexit={item['exit_code']}\n{item['stdout']}{item['stderr']}\n"
            for item in dflash_commands
        )
    )
    config_commands = [
        _run("config-diff", ["git", "diff", "--", "config.yml"], environment),
        _run("config-status", ["git", "status", "--short", "--", "config.yml"], environment),
    ]
    config_text = (
        "claim=Canonical config was not changed by the block-size ablation.\n"
        + "".join(
            f"# {item['label']}\n$ {' '.join(item['command'])}\nexit={item['exit_code']}\n{item['stdout']}{item['stderr']}\n"
            for item in config_commands
        )
    )
    return base_sha, changed_text, dflash_text, config_text, changed_sources


def _validate_ablation() -> dict[str, Any]:
    report = json.loads((ARTIFACT_ROOT / "ablation.json").read_text(encoding="utf-8"))
    summary = report["summary"]
    results = {item["block_size"]: item for item in summary["results"]}
    future_path = ARTIFACT_ROOT / "future_token_invariance_logits.pt"
    future_logits = torch.load(future_path, map_location="cpu", weights_only=True)
    original_null = all(
        item["condition_summaries"][condition]["context_reduction_rate"] is None
        for item in summary["results"] for condition in ("baseline-ar", "dflash-r1")
    )
    row_counts = all(
        item["condition_summaries"][condition]["row_count"] == 10
        for item in summary["results"] for condition in (
            "baseline-ar", "dflash-r1", "llmlingua-ar-r2", "cc-dflash-r2"
        )
    )
    future = report["future_token_invariance"]
    gates = {
        "ablation_complete": summary["ablation_complete"] is True,
        "all_block_sizes": summary["block_sizes"] == [4, 8, 12, 16],
        "all_condition_row_counts_10": row_counts,
        "block_4_gate_pass": results[4]["pair_parity"] == "20/20" and results[4]["exact_field_quality"] == "40/40",
        "block_8_gate_pass": results[8]["pair_parity"] == "20/20" and results[8]["exact_field_quality"] == "40/40",
        "block_12_gate_fail": results[12]["pair_parity"] == "19/20" and results[12]["exact_field_quality"] == "39/40",
        "block_16_gate_fail": results[16]["pair_parity"] == "19/20" and results[16]["exact_field_quality"] == "39/40",
        "selected_largest_eligible_is_8": summary["selected_block_size"] == 8,
        "canonical_config_unchanged": summary["canonical_config_changed"] is False,
        "original_context_reduction_null": original_null,
        "future_token_invariance_pass": future["causal_future_token_invariance_pass"] is True,
        "future_full_vectors_exact": all(
            future["comparisons"][name]["full_logit_vector_exact_equal"]
            and future["comparisons"][name]["max_abs_logit_diff"] == 0.0
            for name in ("shifted_future", "mask_future")
        ),
        "future_logits_hash_match": future["raw_logits"]["sha256"] == _sha256(future_path),
        "future_logits_vectors_valid": (
            set(future_logits) == {"original", "shifted_future", "mask_future"}
            and all(value.dtype == torch.float32 and value.numel() == 151936 for value in future_logits.values())
        ),
        "per_condition_metrics_present": all(
            item["condition_summaries"][condition]["weighted_dflash"] is not None
            for item in summary["results"] for condition in ("dflash-r1", "cc-dflash-r2")
        ),
    }
    return {"pass": all(gates.values()), "gates": gates, "summary": summary}


def main() -> None:
    environment = os.environ.copy()
    environment["PROJECT_ROOT"] = str(ROOT)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    commands = [
        _run(
            "rec3-four-condition-protocol",
            [str(ROOT / ".venv/bin/python"), "tests/run_rec3_four_condition_protocol.py"],
            environment,
        ),
        _run(
            "rec3-dflash-block-size-ablation",
            [str(ROOT / ".venv/bin/python"), "tests/run_rec3_dflash_block_size_ablation.py"],
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

    base_sha, changed_text, dflash_proof, config_proof, changed_sources = _git_evidence(environment)
    _write(EVIDENCE / "base-commit.txt", base_sha + "\n")
    _write(EVIDENCE / "changed-files.txt", changed_text)
    _write(EVIDENCE / "dflash-core-diff-proof.txt", dflash_proof)
    _write(EVIDENCE / "canonical-config-proof.txt", config_proof)
    _write(EVIDENCE / "auto-discovered-changed-source-files.txt", "\n".join(changed_sources) + "\n")
    status = _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment)
    diff = _run("git-diff", ["git", "diff", "--no-ext-diff"], environment)
    _write(EVIDENCE / "git-status.txt", str(status["stdout"]))
    _write(EVIDENCE / "git-diff.patch", str(diff["stdout"]))

    ablation_validation = _validate_ablation()
    report = json.loads((ARTIFACT_ROOT / "ablation.json").read_text(encoding="utf-8"))
    _write(EVIDENCE / "environment.json", json.dumps(report["environment"], indent=2, sort_keys=True) + "\n")
    gates = {
        "protocol_expected_blocker_exit": commands[0]["exit_code"] == 1,
        "fresh_ablation_pass": commands[1]["exit_code"] == 0,
        "ablation_contract_pass": ablation_validation["pass"],
        "all_changed_untracked_sources_exist": all((ROOT / name).is_file() for name in changed_sources),
        "compileall_pass": commands[2]["exit_code"] == 0,
        "pytest_pass": commands[3]["exit_code"] == 0,
        "git_diff_check_pass": commands[4]["exit_code"] == 0,
    }
    validation = {"pass": all(gates.values()), "gates": gates, "ablation": ablation_validation}
    _write(EVIDENCE / "validation-summary.json", json.dumps(validation, indent=2, sort_keys=True) + "\n")

    source_names = sorted(set(REQUIRED_SOURCE_FILES + changed_sources))
    required = [ROOT / name for name in source_names + ARTIFACT_FILES]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing review-pack inputs: {missing}")
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
    if not set(changed_sources).issubset(relative):
        raise RuntimeError("review pack omitted an auto-discovered changed/untracked source")
    planned = sorted({*relative, str(pack_members_path.relative_to(ROOT)), str(manifest_path.relative_to(ROOT))})
    _write(pack_members_path, "\n".join(planned) + "\n")
    members.append(pack_members_path)
    manifest = {
        "manifest_version": "ccdf.rec3-dflash-block-size-ablation-review-pack.v1",
        "base_commit_sha": base_sha,
        "auto_discovered_changed_source_files": changed_sources,
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

    with tempfile.TemporaryDirectory(prefix="ccdf-rec3-block-ablation-pack-") as temporary:
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            archived = [item.name for item in archive.getmembers() if item.isfile()]
            if any(name.startswith(forbidden_prefixes) or name.endswith(".tar.gz") for name in archived):
                raise RuntimeError("sealed archive violates exclusion policy")
            archive.extractall(temporary, filter="data")
        extracted = Path(temporary)
        sealed = json.loads((extracted / manifest_path.relative_to(ROOT)).read_text(encoding="utf-8"))
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
        "pass": all(gates.values()), "selected_block_size": 8,
        "canonical_config_changed": False,
        "archive": str(ARCHIVE), "archive_sha256": _sha256(ARCHIVE),
        "member_count": len(archived),
        "manifest_hashes_verified": f"{sum(verified.values())}/{len(verified)}",
        "auto_discovered_changed_source_files": changed_sources,
        "gates": gates,
    }
    print(json.dumps(result, sort_keys=True))
    if not result["pass"]:
        raise SystemExit("REC-3 D-Flash block-size ablation review pack failed")


if __name__ == "__main__":
    main()
