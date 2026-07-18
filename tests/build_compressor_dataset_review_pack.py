"""Build the local compressor/dataset validation review pack."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/artifacts/review-pack/compressor-dataset-validation"
ARCHIVE = ROOT / "docs/reviews/compressor-dataset-validation-review-pack.tar.gz"

RUNTIME_FILES = [
    "scripts/create_example_dataset.py",
    "scripts/prepare_models.py",
]
SOURCE_FILES = [
    ".gitignore", "config.yml", "pyproject.toml",
    "src/ccdf/compression/__init__.py", "src/ccdf/compression/llmlingua.py", "src/ccdf/compression/schemas.py",
    "src/ccdf/data/__init__.py", "src/ccdf/data/__main__.py", "src/ccdf/data/pipeline.py",
    *RUNTIME_FILES,
    "tests/run_short_prompt_smoke.py", "tests/run_256token_audit.py",
    "tests/run_compressor_validation.py", "tests/run_dataset_validation.py",
    "tests/legacy_preprocess_adapter.py",
    "tests/build_compressor_dataset_review_pack.py", "tests/test_compression_protocol.py",
    "tests/test_data_pipeline.py", "tests/test_benchmark_consistency.py",
]
COMPARISON_INPUTS = [
    ".worktrees/source-main/src/ccdf/datasets/schemas.py", ".worktrees/source-main/src/ccdf/datasets/gsm8k.py",
    ".worktrees/source-main/src/ccdf/datasets/qmsum.py", ".worktrees/source-main/src/ccdf/datasets/validation.py",
]
ARTIFACT_FILES = [
    "docs/artifacts/compression/compressor_validation.json",
    "docs/artifacts/data/dataset_validation.json", "docs/artifacts/data/source_comparison.json",
    "docs/artifacts/data/dataset_manifest.json", "docs/artifacts/data/source_fetch_manifest.json",
    "docs/artifacts/models/checkpoint_manifest.json",
    "data/manifests/dataset_manifest.json", "data/manifests/source_fetch.json",
    "data/eval/gsm8k/gsm8k_n10.jsonl", "data/eval/qmsum/qmsum_n10.jsonl",
]
GENERATED_CHANGED_FILES = [
    *ARTIFACT_FILES,
    "data/raw/gsm8k/gsm8k_test.jsonl", "data/raw/qmsum/qmsum_test.jsonl",
    "data/processed/gsm8k/gsm8k_processed.jsonl",
    "data/processed/qmsum/qmsum_processed.jsonl",
]


def _run(label: str, command: list[str], environment: dict[str, str] | None = None) -> dict[str, object]:
    started = time.perf_counter()
    completed = subprocess.run(
        command, cwd=ROOT, env=environment, text=True, capture_output=True, check=False
    )
    return {
        "label": label, "command": command, "exit_code": completed.returncode,
        "stdout": completed.stdout, "stderr": completed.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _checkpoint_manifest() -> dict[str, object]:
    from ccdf.config import load_config

    config = load_config(ROOT / "config.yml")
    roots = {
        "baseline": config.path_for("models.baseline.local_path"),
        "dflash_target": config.path_for("models.dflash.target.local_path"),
        "dflash_drafter": config.path_for("models.dflash.drafter.local_path"),
        "compressor": config.path_for("models.compressor.local_path"),
    }
    models: dict[str, object] = {}
    for label, root in roots.items():
        files = []
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            if path.name in {"config.json", "generation_config.json"}:
                category = "config"
            elif path.name.startswith("tokenizer") or path.name in {
                "special_tokens_map.json", "vocab.json", "merges.txt"
            }:
                category = "tokenizer"
            elif path.suffix in {".safetensors", ".bin", ".pt", ".pth"}:
                category = "weights"
            else:
                continue
            files.append({
                "filename": path.name,
                "category": category,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
        entry: dict[str, object] = {
            "path": str(root.relative_to(ROOT)),
            "files": files,
            "categories_present": sorted({item["category"] for item in files}),
        }
        if label == "dflash_drafter" and "tokenizer" not in entry["categories_present"]:
            entry["tokenizer_inherited_from"] = "dflash_target"
        models[label] = entry
    return {
        "manifest_version": "ccdf.checkpoint-manifest.v1",
        "models": models,
        "archive_policy": "Manifest contains metadata and hashes only; checkpoint files are excluded from the review pack.",
    }


def main() -> None:
    environment = os.environ.copy()
    environment["PROJECT_ROOT"] = str(ROOT)
    validation_commands = []
    for label, command in (
        ("compressor-validation", [str(ROOT / ".venv/bin/python"), "tests/run_compressor_validation.py"]),
        ("dataset-validation", [str(ROOT / ".venv/bin/python"), "tests/run_dataset_validation.py"]),
    ):
        record = _run(label, command, environment)
        validation_commands.append(record)
        if record["exit_code"] != 0:
            _write(EVIDENCE / "commands.json", json.dumps({"validation_commands": validation_commands}, indent=2) + "\n")
            raise RuntimeError(f"{label} failed; refusing to package stale artifacts")
    commands = [
        _run("compileall", [str(ROOT / ".venv/bin/python"), "-m", "compileall", "-q", "src", "scripts", "tests"], environment),
        _run("pytest", [str(ROOT / ".venv/bin/pytest"), "-q"], environment),
        _run("git-diff-check", ["git", "diff", "--check"], environment),
    ]
    compressor = json.loads((ROOT / ARTIFACT_FILES[0]).read_text(encoding="utf-8"))
    dataset = json.loads((ROOT / ARTIFACT_FILES[1]).read_text(encoding="utf-8"))
    gates = {
        "compressor_validation_pass": compressor["pass"],
        "compressor_mock_pass": f"{compressor['mock_prompt_pass_count']}/{compressor['mock_prompt_count']}",
        "dataset_validation_pass": dataset["pass"],
        "dataset_manifest_byte_match": dataset["manifest_byte_match"],
        "dataset_fetch_drift_rejected": dataset["fetch_drift_probe"]["pass"],
        "old_new_preprocessing_match": all(
            result["full_fixture_match"]
            for result in dataset["source_comparison"]["preprocessing"].values()
        ),
        "compressor_reserved_budget_pass": compressor["reserved_vram_budget"]["pass"],
        "fresh_compressor_validation_pass": validation_commands[0]["exit_code"] == 0,
        "fresh_dataset_validation_pass": validation_commands[1]["exit_code"] == 0,
        "compileall_pass": commands[0]["exit_code"] == 0,
        "pytest_pass": commands[1]["exit_code"] == 0,
        "git_diff_check_pass": commands[2]["exit_code"] == 0,
    }
    _write(EVIDENCE / "commands.json", json.dumps({
        "validation_commands": validation_commands, "final_commands": commands,
    }, indent=2) + "\n")
    _write(EVIDENCE / "test-results.txt", "".join(
        f"$ {' '.join(record['command'])}\nexit={record['exit_code']}\n{record['stdout']}{record['stderr']}\n"
        for record in [*validation_commands, *commands]
    ))
    status = _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment)
    diff = _run("git-diff", ["git", "diff", "--no-ext-diff"], environment)
    _write(EVIDENCE / "git-status.txt", str(status["stdout"]))
    _write(EVIDENCE / "git-diff.patch", str(diff["stdout"]))
    _write(EVIDENCE / "changed-files.txt", "\n".join(SOURCE_FILES + GENERATED_CHANGED_FILES) + "\n")
    _write(
        EVIDENCE / "comparison-inputs.txt",
        "\n".join(COMPARISON_INPUTS) + "\n",
    )
    _write(
        ROOT / "docs/artifacts/models/checkpoint_manifest.json",
        json.dumps(_checkpoint_manifest(), indent=2, sort_keys=True) + "\n",
    )
    _write(EVIDENCE / "validation-summary.json", json.dumps({"pass": all(value is True or value == "10/10" for value in gates.values()), "gates": gates}, indent=2) + "\n")

    manifest_path = EVIDENCE / "archive-manifest.json"
    members = [ROOT / relative for relative in SOURCE_FILES + COMPARISON_INPUTS + ARTIFACT_FILES]
    members.extend(sorted(path for path in EVIDENCE.rglob("*") if path.is_file() and path != manifest_path))
    missing = [str(path) for path in members if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"review pack inputs missing: {missing}")
    forbidden = ("models/", "data/raw/", "data/processed/", ".venv/", ".git/", "__pycache__/")
    relative_members = [str(path.relative_to(ROOT)) for path in members]
    if any(name.startswith(forbidden) or name.endswith(".tar.gz") for name in relative_members):
        raise RuntimeError("review pack member violates exclusion policy")

    recorded_members = {
        name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        for name, path in sorted(zip(relative_members, members))
    }
    manifest = {
        "manifest_version": "ccdf.compressor-dataset-review-pack.v2",
        "self_entry_policy": "archive-manifest.json is intentionally omitted to avoid recursive self-hashing",
        "members": recorded_members,
    }
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    members.append(manifest_path)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(ARCHIVE, "w:gz") as handle:
        for path in sorted(set(members)):
            handle.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)

    with tempfile.TemporaryDirectory(prefix="ccdf-review-pack-check-") as temporary:
        with tarfile.open(ARCHIVE, "r:gz") as handle:
            archived = [member.name for member in handle.getmembers() if member.isfile()]
            if any(name.startswith(forbidden) or name.endswith(".tar.gz") for name in archived):
                raise RuntimeError("sealed review pack violates exclusion policy")
            handle.extractall(temporary, filter="data")
        extracted_root = Path(temporary)
        extracted_manifest_path = extracted_root / manifest_path.relative_to(ROOT)
        sealed_manifest = json.loads(extracted_manifest_path.read_text(encoding="utf-8"))
        if str(manifest_path.relative_to(ROOT)) in sealed_manifest["members"]:
            raise RuntimeError("archive manifest incorrectly records a recursive self-hash")
        expected_archived = sorted([*sealed_manifest["members"], str(manifest_path.relative_to(ROOT))])
        if sorted(archived) != expected_archived:
            raise RuntimeError("sealed archive member set does not match manifest")
        verified = {}
        for name, expected in sealed_manifest["members"].items():
            extracted = extracted_root / name
            actual = {"bytes": extracted.stat().st_size, "sha256": _sha256(extracted)}
            verified[name] = actual == expected
        if not all(verified.values()):
            failed = [name for name, passed in verified.items() if not passed]
            raise RuntimeError(f"sealed archive hash verification failed: {failed}")
    manifest_verification = {
        "pass": True, "recorded_hashes": len(verified),
        "verified_hashes": sum(verified.values()), "self_hash_omitted": True,
    }
    print(json.dumps({"pass": all(value is True or value == "10/10" for value in gates.values()), "archive": str(ARCHIVE), "archive_sha256": _sha256(ARCHIVE), "member_count": len(archived), "manifest_verification": manifest_verification, "gates": gates}, sort_keys=True))
    if not all(value is True or value == "10/10" for value in gates.values()):
        raise SystemExit("review pack contains failing gates")


if __name__ == "__main__":
    main()
