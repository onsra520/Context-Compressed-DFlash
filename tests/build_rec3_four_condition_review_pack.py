"""Config-driven builder for the final tracked REC-3 review pack."""

from __future__ import annotations

import hashlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any

import torch
import transformers
import yaml

from ccdf.config import Rec2Config, ResolvedProtocolProfile, load_config
from ccdf.rec3.metrics import render_final_report
from ccdf.rec3.orchestrator import ARTIFACT_FILENAMES


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yml"
REQUIRED_SOURCE_FILES = [
    ".gitignore", "config.yml", "pyproject.toml",
    "src/ccdf/config.py", "src/ccdf/determinism.py", "src/ccdf/device.py",
    "src/ccdf/schemas.py", "src/ccdf/compression/__init__.py",
    "src/ccdf/compression/llmlingua.py", "src/ccdf/compression/schemas.py",
    "src/ccdf/models/loaders.py", "src/ccdf/runtime/engine.py",
    "src/ccdf/inference/baseline.py", "src/ccdf/inference/sampling.py",
    "src/ccdf/dflash/acceptance.py", "src/ccdf/dflash/generate.py",
    "src/ccdf/dflash/policy.py", "src/ccdf/dflash/verifier.py",
    "src/ccdf/validation/environment.py", "src/ccdf/rec3/__init__.py",
    "src/ccdf/rec3/__main__.py", "src/ccdf/rec3/metrics.py",
    "src/ccdf/rec3/orchestrator.py",
    "tests/run_rec3_four_condition_protocol.py",
    "tests/build_rec3_four_condition_review_pack.py",
    "tests/test_rec3_protocol_helpers.py", "tests/test_compression_protocol.py",
    "tests/test_dflash_integration.py", "tests/test_metrics.py",
]
SOURCE_SUFFIXES = {".py", ".toml", ".yml", ".yaml", ".json"}
CANONICAL_CONFIG_SECTIONS = (
    "models", "runtime", "memory", "optimization", "benchmark", "validation", "prompts"
)


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
        "label": label,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def _git_lines(command: list[str], environment: dict[str, str]) -> list[str]:
    result = _run("git-discovery", command, environment)
    if result["exit_code"] != 0:
        raise RuntimeError(f"Git discovery failed: {command}: {result['stderr']}")
    return [line.strip() for line in str(result["stdout"]).splitlines() if line.strip()]


def _discover_git_files(environment: dict[str, str], base_sha: str) -> dict[str, list[str]]:
    changed = sorted(set(
        _git_lines(["git", "diff", "--name-only", base_sha], environment)
        + _git_lines(["git", "diff", "--cached", "--name-only", base_sha], environment)
    ))
    untracked = sorted(set(
        _git_lines(["git", "ls-files", "--others", "--exclude-standard"], environment)
    ))
    candidates = sorted(set(changed + untracked))
    source_candidates = [
        name for name in candidates
        if (ROOT / name).is_file()
        and (Path(name).suffix in SOURCE_SUFFIXES or name.startswith(("src/", "scripts/", "tests/")))
    ]
    return {"changed": changed, "untracked": untracked, "source_candidates": source_candidates}


def _distribution_version(*names: str) -> str | None:
    for name in names:
        try:
            return importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            continue
    return None


def _existing_config_values_preserved(base: Any, current: Any) -> bool:
    if isinstance(base, dict):
        return isinstance(current, dict) and all(
            key in current and _existing_config_values_preserved(value, current[key])
            for key, value in base.items()
        )
    return base == current


def _environment_evidence(environment: dict[str, str]) -> dict[str, Any]:
    gpu: dict[str, Any] = {"cuda_available": torch.cuda.is_available()}
    if torch.cuda.is_available():
        properties = torch.cuda.get_device_properties(0)
        gpu.update({
            "gpu_count": torch.cuda.device_count(),
            "gpu_name": properties.name,
            "compute_capability": [properties.major, properties.minor],
            "total_memory_bytes": properties.total_memory,
        })
    smi = _run(
        "nvidia-smi-environment",
        ["nvidia-smi", "--query-gpu=driver_version,name,compute_cap,memory.total",
         "--format=csv,noheader,nounits"],
        environment,
    )
    gpu["nvidia_smi"] = {
        "exit_code": smi["exit_code"], "stdout": smi["stdout"], "stderr": smi["stderr"]
    }
    return {
        "python": {"version": platform.python_version(), "executable": sys.executable},
        "platform": platform.platform(),
        "packages": {
            "torch": torch.__version__, "transformers": transformers.__version__,
            "llmlingua": _distribution_version("llmlingua"),
            "autoawq": _distribution_version("autoawq", "autoawq-kernels"),
            "pytest": _distribution_version("pytest"),
        },
        "cuda": {"torch_cuda_version": torch.version.cuda, **gpu},
        "project_root": str(ROOT),
    }


def _checkpoint_manifest(config: Rec2Config) -> dict[str, Any]:
    entries: dict[str, Any] = {}
    for label, key in {
        "baseline": "models.baseline.local_path",
        "dflash_target": "models.dflash.target.local_path",
        "dflash_drafter": "models.dflash.drafter.local_path",
        "compressor": "models.compressor.local_path",
    }.items():
        directory = config.path_for(key)
        files = []
        for item in sorted(directory.iterdir()):
            if not item.is_file():
                continue
            if item.name in {"config.json", "generation_config.json"}:
                category = "config"
            elif item.name.startswith("tokenizer") or item.name in {
                "special_tokens_map.json", "vocab.json", "merges.txt"
            }:
                category = "tokenizer"
            elif item.suffix in {".safetensors", ".bin", ".pt", ".pth"}:
                category = "weights"
            else:
                continue
            files.append({
                "filename": item.name,
                "category": category,
                "bytes": item.stat().st_size,
                "sha256": _sha256(item),
            })
        entries[label] = {"path": str(directory.relative_to(ROOT)), "files": files}
    return {
        "manifest_version": "ccdf.rec3-profile-checkpoints.v1",
        "models": entries,
        "archive_policy": "Metadata and hashes only; model files are excluded.",
    }


def _artifact_paths(profile: ResolvedProtocolProfile) -> dict[str, Path]:
    root = profile.path_for("artifact_directory")
    return {key: root / filename for key, filename in ARTIFACT_FILENAMES.items()}


def _validate_final_artifacts(
    source_config: Rec2Config,
    profile: ResolvedProtocolProfile,
    source_paths: list[Path],
) -> dict[str, Any]:
    paths = _artifact_paths(profile)
    missing = [str(path.relative_to(ROOT)) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"final artifact missing: {missing}")
    summary = json.loads(paths["summary"].read_text(encoding="utf-8"))
    raw = json.loads(paths["raw"].read_text(encoding="utf-8"))
    gate_matrix = json.loads(paths["gates"].read_text(encoding="utf-8"))
    protected = json.loads(paths["protected_hashes"].read_text(encoding="utf-8"))
    parity = json.loads(paths["parity"].read_text(encoding="utf-8"))
    config_snapshot = json.loads(paths["config_snapshot"].read_text(encoding="utf-8"))
    summary_sha = _sha256(paths["summary"])
    expected_report = render_final_report(summary, summary_sha)
    newest_source_mtime_ns = max(path.stat().st_mtime_ns for path in source_paths)
    stale_artifacts = [
        str(path.relative_to(ROOT)) for path in paths.values()
        if path.stat().st_mtime_ns < newest_source_mtime_ns
    ]
    all_runs = [run for prompt in raw["prompts"] for run in prompt["runs"].values()]
    dflash_names = {
        str(item["name"]) for item in profile.require("conditions")
        if str(item["runtime_condition"]) == "dflash"
    }
    configured_block = int(profile.config.require("optimization.block_policy.fixed_block_size"))
    actual_blocks = sorted({
        int(block)
        for prompt in raw["prompts"]
        for name, run in prompt["runs"].items()
        if name in dflash_names and run["success"]
        for block in run["result"]["dflash"]["block_sizes"]
    })
    expected_condition_rows = len(profile.require("fixtures")) * len(profile.require("conditions"))
    expected_pair_rows = len(profile.require("fixtures")) * len(profile.require("parity_pairs"))
    exact_outputs_and_ids = all(
        run.get("success") is True
        and isinstance(run["result"].get("text"), str)
        and isinstance(run["result"].get("generated_token_ids"), list)
        for run in all_runs
    )
    gates = {
        "summary_overall_pass": summary.get("overall_pass") is True,
        "hard_gates_all_pass": all(summary.get("hard_gates", {}).values()),
        "condition_rows_match_config": len(all_runs) == expected_condition_rows,
        "pair_rows_match_config": len(parity) == expected_pair_rows,
        "protected_rows_match_config": len(protected) == len(profile.require("fixtures")),
        "all_conditions_succeeded": all(run.get("success") is True for run in all_runs),
        "all_pairs_passed": all(item.get("pass") is True for item in parity),
        "all_protected_fields_passed": all(item.get("pass") is True for item in protected),
        "exact_outputs_and_generated_token_ids_present": exact_outputs_and_ids,
        "metric_validity_pass": summary.get("metric_validity_pass") is True,
        "no_oom": summary.get("oom_event_count") <= int(
            profile.require("hard_gates.max_oom_events")
        ),
        "dflash_peak_reserved_vram_gate_pass": summary.get("memory_gate_pass") is True,
        "configured_block_observed": actual_blocks == [configured_block],
        "raw_summary_exact_match": raw.get("summary") == summary,
        "final_report_exactly_rendered_from_summary": (
            paths["report"].read_text(encoding="utf-8") == expected_report
        ),
        "gate_matrix_matches_summary": (
            gate_matrix.get("overall_pass") == summary.get("overall_pass")
            and gate_matrix.get("hard_gates") == summary.get("hard_gates")
            and gate_matrix.get("memory_gate") == summary.get("memory_gate")
        ),
        "source_config_hash_matches": (
            profile.source_config_sha256 == _sha256(CONFIG_PATH)
            == summary.get("source_config_sha256")
            == config_snapshot.get("source_config_sha256")
        ),
        "active_profile_matches": (
            profile.name == summary.get("active_profile")
            == config_snapshot.get("active_profile")
        ),
        "resolved_config_snapshot_matches": (
            config_snapshot.get("resolved_config") == profile.config.data
        ),
        "canonical_block_preserved": (
            summary.get("canonical_block_size")
            == source_config.require("optimization.block_policy.fixed_block_size")
            == source_config.require("models.dflash.drafter.checkpoint_block_size")
        ),
        "final_artifacts_newer_than_source_and_config": not stale_artifacts,
    }
    return {
        "pass": all(gates.values()),
        "gates": gates,
        "summary": summary,
        "summary_sha256": summary_sha,
        "source_config_sha256": profile.source_config_sha256,
        "stale_artifacts": stale_artifacts,
        "configured_block_size": configured_block,
        "observed_block_sizes": actual_blocks,
        "expected_condition_rows": expected_condition_rows,
        "expected_pair_rows": expected_pair_rows,
    }


def _git_evidence(
    environment: dict[str, str], source_config: Rec2Config
) -> tuple[str, dict[str, list[str]], list[dict[str, Any]], dict[str, Any]]:
    base = _run("base-commit", ["git", "rev-parse", "HEAD"], environment)
    if base["exit_code"] != 0:
        raise RuntimeError(f"cannot resolve base commit: {base['stderr']}")
    base_sha = str(base["stdout"]).strip()
    discovered = _discover_git_files(environment, base_sha)
    commands = [
        _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment),
        _run("git-diff-name-status", ["git", "diff", "--name-status", base_sha], environment),
        _run("git-diff-cached-name-status", ["git", "diff", "--cached", "--name-status", base_sha], environment),
        _run("git-untracked", ["git", "ls-files", "--others", "--exclude-standard"], environment),
        _run("git-ignored-validation-files", [
            "git", "check-ignore", "-v",
            *[name for name in REQUIRED_SOURCE_FILES if name.startswith("tests/")],
        ], environment),
        _run("dflash-core-status", ["git", "status", "--short", "--", "src/ccdf/dflash"], environment),
        _run("dflash-core-numstat", ["git", "diff", "--numstat", base_sha, "--", "src/ccdf/dflash"], environment),
        _run("dflash-core-untracked", ["git", "ls-files", "--others", "--exclude-standard", "src/ccdf/dflash"], environment),
        _run("canonical-config-diff", ["git", "diff", "--", "config.yml"], environment),
    ]
    base_config_result = _run("base-config", ["git", "show", f"{base_sha}:config.yml"], environment)
    if base_config_result["exit_code"] != 0:
        raise RuntimeError(f"cannot read base config: {base_config_result['stderr']}")
    base_raw = yaml.safe_load(str(base_config_result["stdout"]))
    current_raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    section_checks = {
        section: _existing_config_values_preserved(
            base_raw.get(section), current_raw.get(section)
        )
        for section in CANONICAL_CONFIG_SECTIONS
    }
    canonical_proof = {
        "base_commit_sha": base_sha,
        "canonical_sections": list(CANONICAL_CONFIG_SECTIONS),
        "section_checks": section_checks,
        "canonical_fixed_block_size": source_config.require(
            "optimization.block_policy.fixed_block_size"
        ),
        "checkpoint_block_size": source_config.require(
            "models.dflash.drafter.checkpoint_block_size"
        ),
        "new_profile_is_outside_canonical_sections": "protocol_profiles" not in base_raw,
        "pass": (
            all(section_checks.values())
            and source_config.require("optimization.block_policy.fixed_block_size")
            == source_config.require("models.dflash.drafter.checkpoint_block_size")
        ),
    }
    return base_sha, discovered, commands, canonical_proof


def _is_forbidden_member(name: str) -> bool:
    path = Path(name)
    parts = set(path.parts)
    return (
        name.endswith((".tar", ".tar.gz", ".tgz"))
        or bool(parts & {
            ".git", ".venv", ".worktrees", "__pycache__", ".pytest_cache", ".ruff_cache"
        })
        or name.startswith(("models/", "data/raw/", "data/processed/"))
    )


def main() -> None:
    source_config = load_config(CONFIG_PATH)
    profile = source_config.resolve_active_protocol_profile()
    artifact_root = profile.path_for("artifact_directory")
    archive_path = profile.path_for("review_archive")
    evidence = artifact_root.parent / "review-pack" / f"{artifact_root.name}-tracked-final"
    environment = os.environ.copy()
    environment["PROJECT_ROOT"] = str(ROOT)
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True, exist_ok=True)
    if archive_path.exists():
        archive_path.unlink()

    commands = [
        _run(
            "rec3-active-profile",
            [str(ROOT / ".venv/bin/python"), "-m", "ccdf.rec3", "--config", str(CONFIG_PATH)],
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
    _write(evidence / "commands.json", json.dumps(commands, indent=2, sort_keys=True) + "\n")
    _write(evidence / "test-results.txt", "".join(
        f"$ {' '.join(entry['command'])}\nexit={entry['exit_code']}\n"
        f"duration_seconds={entry['duration_seconds']}\n--- stdout ---\n{entry['stdout']}"
        f"--- stderr ---\n{entry['stderr']}\n"
        for entry in commands
    ))
    failed_commands = [entry["label"] for entry in commands if entry["exit_code"] != 0]
    if failed_commands:
        raise SystemExit(f"refusing to seal review pack; command gates failed: {failed_commands}")

    # Reload after the run so every builder check uses the same current config bytes.
    source_config = load_config(CONFIG_PATH)
    profile = source_config.resolve_active_protocol_profile()
    base_sha, discovered, git_commands, canonical_proof = _git_evidence(
        environment, source_config
    )
    git_status = next(item for item in git_commands if item["label"] == "git-status")
    _write(evidence / "base-commit.txt", base_sha + "\n")
    _write(evidence / "git-status.txt", str(git_status["stdout"]))
    diff = _run("git-diff", ["git", "diff", "--no-ext-diff", base_sha], environment)
    if diff["exit_code"] != 0:
        raise RuntimeError(f"git diff failed: {diff['stderr']}")
    _write(evidence / "git-diff.patch", str(diff["stdout"]))
    _write(evidence / "git-evidence.json", json.dumps(git_commands, indent=2, sort_keys=True) + "\n")
    _write(evidence / "changed-files.txt", (
        "# tracked changed\n" + "\n".join(discovered["changed"])
        + "\n\n# untracked (excluding ignored files)\n" + "\n".join(discovered["untracked"])
        + "\n\n# ignored validation files included explicitly\n"
        + "\n".join(name for name in REQUIRED_SOURCE_FILES if name.startswith("tests/")) + "\n"
    ))
    dflash_unchanged = all(
        not str(item["stdout"]).strip() and item["exit_code"] == 0
        for item in git_commands if item["label"] in {
            "dflash-core-status", "dflash-core-numstat", "dflash-core-untracked"
        }
    )
    _write(evidence / "dflash-core-unchanged-proof.json", json.dumps({
        "base_commit_sha": base_sha,
        "pass": dflash_unchanged,
        "commands": [
            item for item in git_commands if item["label"].startswith("dflash-core-")
        ],
    }, indent=2, sort_keys=True) + "\n")
    _write(evidence / "canonical-benchmark-config-proof.json", json.dumps(
        canonical_proof, indent=2, sort_keys=True
    ) + "\n")
    if not dflash_unchanged or not canonical_proof["pass"]:
        raise SystemExit("refusing to seal; D-Flash core or canonical benchmark profile changed")

    required_sources = [ROOT / name for name in REQUIRED_SOURCE_FILES]
    dynamic_sources = [ROOT / name for name in discovered["source_candidates"]]
    source_paths = sorted(set(required_sources + dynamic_sources))
    missing_sources = [str(path.relative_to(ROOT)) for path in source_paths if not path.is_file()]
    if missing_sources:
        raise FileNotFoundError(f"required source missing: {missing_sources}")
    validation = _validate_final_artifacts(source_config, profile, source_paths)
    _write(evidence / "validation-summary.json", json.dumps(
        validation, indent=2, sort_keys=True
    ) + "\n")
    if not validation["pass"]:
        raise SystemExit(f"refusing to seal; final artifact gates failed: {validation['gates']}")

    _write(evidence / "environment.json", json.dumps(
        _environment_evidence(environment), indent=2, sort_keys=True
    ) + "\n")
    _write(evidence / "checkpoint-manifest.json", json.dumps(
        _checkpoint_manifest(profile.config), indent=2, sort_keys=True
    ) + "\n")
    artifact_paths = list(_artifact_paths(profile).values())
    manifest_path = evidence / "archive-manifest.json"
    pack_members_path = evidence / "pack-members.txt"
    members = sorted(set(
        source_paths + artifact_paths
        + [path for path in evidence.rglob("*") if path.is_file()
           and path not in {manifest_path, pack_members_path}]
    ))
    relative_members = [str(path.relative_to(ROOT)) for path in members]
    forbidden = [name for name in relative_members if _is_forbidden_member(name)]
    if forbidden:
        raise RuntimeError(f"review pack member violates exclusion policy: {forbidden}")
    planned_members = sorted(set(relative_members + [
        str(pack_members_path.relative_to(ROOT)), str(manifest_path.relative_to(ROOT))
    ]))
    _write(pack_members_path, "\n".join(planned_members) + "\n")
    members.append(pack_members_path)
    manifest = {
        "manifest_version": "ccdf.rec3-tracked-profile-final.v1",
        "base_commit_sha": base_sha,
        "active_profile": profile.name,
        "source_config_sha256": profile.source_config_sha256,
        "summary_sha256": validation["summary_sha256"],
        "resolved_verification_block_size": validation["configured_block_size"],
        "self_entry_policy": (
            "archive-manifest.json is omitted from its own hash map to avoid recursive hashing"
        ),
        "members": {
            str(path.relative_to(ROOT)): {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in sorted(set(members))
        },
    }
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    archive_members = sorted(set(members + [manifest_path]))
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in archive_members:
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)

    with tempfile.TemporaryDirectory(prefix="ccdf-rec3-tracked-final-check-") as temporary:
        with tarfile.open(archive_path, "r:gz") as archive:
            archived_names = [entry.name for entry in archive.getmembers() if entry.isfile()]
            if any(_is_forbidden_member(name) for name in archived_names):
                raise RuntimeError("sealed archive violates exclusion policy")
            archive.extractall(temporary, filter="data")
        temporary_root = Path(temporary)
        sealed_manifest = json.loads(
            (temporary_root / manifest_path.relative_to(ROOT)).read_text(encoding="utf-8")
        )
        expected_names = sorted([*sealed_manifest["members"], str(manifest_path.relative_to(ROOT))])
        if sorted(archived_names) != expected_names:
            raise RuntimeError("sealed archive members differ from archive-manifest.json")
        recorded_members = (
            temporary_root / pack_members_path.relative_to(ROOT)
        ).read_text(encoding="utf-8").splitlines()
        if sorted(recorded_members) != expected_names:
            raise RuntimeError("pack-members.txt differs from sealed archive membership")
        verified = {
            name: {
                "bytes": (temporary_root / name).stat().st_size,
                "sha256": _sha256(temporary_root / name),
            } == expected
            for name, expected in sealed_manifest["members"].items()
        }
        if not all(verified.values()):
            failed = [name for name, passed in verified.items() if not passed]
            raise RuntimeError(f"sealed archive SHA-256 verification failed: {failed}")

    print(json.dumps({
        "pass": True,
        "archive": str(archive_path),
        "archive_sha256": _sha256(archive_path),
        "active_profile": profile.name,
        "source_config_sha256": profile.source_config_sha256,
        "summary_sha256": validation["summary_sha256"],
        "resolved_verification_block_size": validation["configured_block_size"],
        "member_count": len(archived_names),
        "manifest_hashes_verified": f"{sum(verified.values())}/{len(verified)}",
        "command_gates": {entry["label"]: entry["exit_code"] == 0 for entry in commands},
        "artifact_gates": validation["gates"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
