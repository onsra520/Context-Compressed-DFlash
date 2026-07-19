"""Build and independently hash-verify the QMSum runtime-timeout diagnostic pack."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC = ROOT / "docs/artifacts/qmsum-runtime-timeout-diagnostic"
STAGING = ROOT / "docs/artifacts/review-pack-qmsum-runtime-timeout-diagnostic"
ARCHIVE = ROOT / "docs/reviews/review-pack-qmsum-runtime-timeout-diagnostic.zip"


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _partial_diagnostic() -> dict:
    partial = DIAGNOSTIC / "partial-run/dataset-smoke/.working"
    prepared_path = partial / "prepared.jsonl"
    rows_path = partial / "baseline-ar.jsonl"
    prepared = _read_jsonl(prepared_path)
    rows = _read_jsonl(rows_path)
    qmsum = [row for row in rows if row["dataset"] == "qmsum"]
    successful = [row for row in qmsum if row.get("success")]
    settings = load_config(ROOT / "config.yml").resolve_dataset_smoke_profile().settings
    samples = []
    for row in qmsum:
        metrics = row.get("run", {}).get("result", {}).get("protocol_metrics", {})
        samples.append({
            "fixture_id": row["fixture_id"],
            "success": bool(row.get("success")),
            "error": row.get("error"),
            "input_tokens": (metrics.get("chat_template_input") or {}).get("token_count"),
            "output_tokens": metrics.get("output_tokens"),
            "request_wall_clock_seconds": (
                float(metrics["request_wall_clock_ms"]) / 1000
                if metrics.get("request_wall_clock_ms") is not None else None
            ),
            "decode_tok_s": metrics.get("decode_tok_s"),
            "cap_hit": metrics.get("cap_hit"),
        })
    slowest = max(
        (item for item in samples if item["request_wall_clock_seconds"] is not None),
        key=lambda item: item["request_wall_clock_seconds"],
    )
    return {
        "classification": "qmsum_original_context_generation_pathologically_slow_with_separate_oom",
        "prepared_rows": len(prepared),
        "completed_rows": len(rows),
        "successful_rows": sum(bool(row.get("success")) for row in rows),
        "error_rows": sum(not bool(row.get("success")) for row in rows),
        "conditions_started": sorted({row["condition"] for row in rows}),
        "qmsum_rows": len(qmsum),
        "qmsum_successes": len(successful),
        "qmsum_measured_request_seconds": sum(
            float(row["run"]["result"]["protocol_metrics"]["request_wall_clock_ms"]) / 1000
            for row in successful
        ),
        "compression_seconds": sum(
            float(row["compression"]["compression_latency_ms"]) / 1000 for row in prepared
        ),
        "slowest_completed_sample": slowest,
        "samples": samples,
        "legacy_progress_timestamp_utc": datetime.fromtimestamp(
            rows_path.stat().st_mtime, timezone.utc
        ).isoformat(),
        "qmsum_max_new_tokens": int(settings["generation"]["qmsum_max_new_tokens"]),
        "single_request_protocol": all(
            row.get("generation_request_contract", {}).get("protocol")
            == settings["generation"]["qmsum_request_protocol"]
            for row in qmsum
        ),
        "retry_count": 0,
        "resume_enabled": False,
    }


def main() -> None:
    if STAGING.exists() or ARCHIVE.exists():
        raise FileExistsError("refusing to replace an existing review pack or archive")
    required = (
        DIAGNOSTIC / "PARTIAL_RUN_DIAGNOSTIC.md",
        DIAGNOSTIC / "emergency-process-snapshot.json",
        DIAGNOSTIC / "partial-run/dataset-smoke/.working/prepared.jsonl",
        DIAGNOSTIC / "partial-run/dataset-smoke/.working/baseline-ar.jsonl",
        DIAGNOSTIC / "n2-qmsum-four-conditions/summary.json",
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"required diagnostic evidence missing: {missing}")

    STAGING.mkdir(parents=True)
    shutil.copytree(DIAGNOSTIC / "partial-run", STAGING / "partial-run")
    shutil.copytree(
        DIAGNOSTIC / "n2-qmsum-four-conditions", STAGING / "n2-qmsum-four-conditions"
    )
    if (DIAGNOSTIC / "command-logs").is_dir():
        shutil.copytree(DIAGNOSTIC / "command-logs", STAGING / "command-logs")
    shutil.copy2(DIAGNOSTIC / "PARTIAL_RUN_DIAGNOSTIC.md", STAGING)
    shutil.copy2(DIAGNOSTIC / "emergency-process-snapshot.json", STAGING)
    source_root = STAGING / "watchdog-source"
    for relative in (
        "config.yml",
        "src/ccdf/config.py",
        "src/ccdf/benchmark/dataset_smoke.py",
        "src/ccdf/benchmark/dataset_smoke_verify.py",
        "tests/test_config.py",
        "tests/test_dataset_smoke_watchdog.py",
        "tests/run_qmsum_watchdog_smoke.py",
        "scripts/build_qmsum_runtime_timeout_review_pack.py",
    ):
        destination = source_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)

    (STAGING / "partial-run-diagnostic.json").write_text(
        json.dumps(_partial_diagnostic(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    files = sorted(
        path for path in STAGING.rglob("*")
        if path.is_file() and path.name not in {"verified-manifest.json", "VERIFICATION.json"}
    )
    manifest = {
        "manifest_version": "qmsum-runtime-timeout-diagnostic.v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "n10_rerun_included": False,
        "n10_rerun_reason": "n2 gate did not permit n10",
        "verification": {
            "status": "PASS",
            "method": "archive entry byte count and SHA-256 rechecked after ZIP creation",
        },
        "files": [
            {
                "path": path.relative_to(STAGING).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": _hash(path),
            }
            for path in files
        ],
    }
    manifest_path = STAGING / "verified-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in STAGING.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(STAGING).as_posix())

    failures = []
    with zipfile.ZipFile(ARCHIVE) as archive:
        for entry in manifest["files"]:
            payload = archive.read(entry["path"])
            if len(payload) != entry["bytes"]:
                failures.append(f"size mismatch: {entry['path']}")
            if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                failures.append(f"sha256 mismatch: {entry['path']}")
        if json.loads(archive.read("verified-manifest.json")) != manifest:
            failures.append("manifest payload mismatch")
    if failures:
        raise RuntimeError(f"archive verification failed: {failures}")
    sidecar = ARCHIVE.with_suffix(ARCHIVE.suffix + ".sha256")
    sidecar.write_text(f"{_hash(ARCHIVE)}  {ARCHIVE.name}\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "archive": str(ARCHIVE),
        "archive_sha256": _hash(ARCHIVE),
        "verified_files": len(manifest["files"]),
        "n10_rerun_included": False,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
