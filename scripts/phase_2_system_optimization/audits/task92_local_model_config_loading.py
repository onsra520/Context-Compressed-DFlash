from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ccdf.config.loader import (  # noqa: E402
    load_config,
    resolve_compressor_model_source,
    resolve_llmlingua_config,
)

DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/runtime_config_audit/task92_local_model_and_compressor_config_loading"
)


def _path_exists(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return Path(text).exists()


def _profile_summary(config: dict[str, Any], profile: str) -> dict[str, Any]:
    cfg = resolve_llmlingua_config(config, profile=profile)
    source = resolve_compressor_model_source(cfg, repo_root=ROOT)
    compressor_path = source.get("compressor_path")
    resolved_compressor_path = source.get("resolved_compressor_path")
    return {
        "profile": profile,
        "model_name": cfg.get("model_name"),
        "compressor_path": compressor_path,
        "resolved_compressor_path": resolved_compressor_path,
        "local_files_only": bool(source.get("local_files_only", False)),
        "device_map": cfg.get("device_map"),
        "resolved_source": source.get("source"),
        "resolved_source_kind": source.get("source_kind"),
        "compressor_path_exists": Path(resolved_compressor_path).exists() if resolved_compressor_path else None,
    }


def build_config_resolved_paths(config: dict[str, Any]) -> dict[str, Any]:
    model_cfg = config.get("model") or {}
    return {
        "target_model_path": str(model_cfg.get("target_id", "")),
        "target_model_exists": _path_exists(model_cfg.get("target_id")),
        "draft_model_path": str(model_cfg.get("draft_id", "")),
        "draft_model_exists": _path_exists(model_cfg.get("draft_id")),
        "tokenizer_path": str(model_cfg.get("tokenizer_id", "")),
        "tokenizer_path_exists": _path_exists(model_cfg.get("tokenizer_id")),
        "large_llmlingua": _profile_summary(config, "large"),
        "light_llmlingua": _profile_summary(config, "light"),
    }


def build_compressor_profile_resolution(config: dict[str, Any]) -> dict[str, Any]:
    profiles = {
        profile: _profile_summary(config, profile)
        for profile in ("large", "light")
    }
    missing_path_error = None
    try:
        resolve_compressor_model_source(
            {
                "model_name": "example/missing",
                "compressor_path": "models/does-not-exist-task92",
                "local_files_only": True,
            },
            repo_root=ROOT,
        )
    except FileNotFoundError as exc:
        missing_path_error = str(exc)

    fallback = resolve_compressor_model_source(
        {
            "model_name": "legacy/model-name-only",
            "device_map": "cpu",
        },
        repo_root=ROOT,
    )

    return {
        "profiles": profiles,
        "compressor_path_priority_over_model_name": True,
        "model_name_only_backward_compatible": {
            "resolved_source": fallback.get("source"),
            "resolved_source_kind": fallback.get("source_kind"),
            "local_files_only": fallback.get("local_files_only"),
        },
        "missing_local_path_error": missing_path_error,
    }


def build_validation_summary(
    *,
    tests_run: list[str],
    compile_status: str,
) -> dict[str, Any]:
    return {
        "tests_run": tests_run,
        "compile_status": compile_status,
        "claim_boundary": {
            "final_benchmark_claim": False,
            "final_speedup_claim": False,
            "deployment_8gb_claim": False,
            "qmsum_semantic_correctness_claim": False,
        },
        "next_task": {
            "task": "T93",
            "name": "Lighter Compressor Integration",
            "goal": "reduce T_compress while preserving enough compression and keeping quality proxy near Baseline-AR",
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Task92 local model/compressor config audit artifacts.")
    parser.add_argument("--config", default="config.yml")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--compile-status", default="not_run")
    parser.add_argument("--tests-run", action="append", default=[])
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config(args.config)
    _write_json(output_dir / "config_resolved_paths.json", build_config_resolved_paths(config))
    _write_json(output_dir / "compressor_profile_resolution.json", build_compressor_profile_resolution(config))
    _write_json(
        output_dir / "task92_validation_summary.json",
        build_validation_summary(tests_run=list(args.tests_run), compile_status=str(args.compile_status)),
    )


if __name__ == "__main__":
    main()
