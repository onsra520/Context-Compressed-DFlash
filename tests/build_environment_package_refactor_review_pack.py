"""Build and independently verify the environment/package-refactor review pack."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yml"
AUDIT_ROOT = ROOT / "docs/audit/environment-package-refactor"
PRE_ROOT = AUDIT_ROOT / "pre-refactor-artifacts"
PRE_PACK = AUDIT_ROOT / "pre-refactor-sealed-review-pack.tar.gz"
STAGE = AUDIT_ROOT / "review-pack-environment-package-refactor"
ARCHIVE = ROOT / "docs/reviews/review-pack-environment-package-refactor.tar.gz"
FINAL_ARTIFACT_NAMES = (
    "FINAL_REPORT.md",
    "gate_matrix.json",
    "mock_fixtures.json",
    "pair_parity.json",
    "protected_field_hashes.json",
    "raw_runs.json",
    "resolved_config_snapshot.json",
    "summary.json",
)
ENVIRONMENT_FIELDS = (
    "PATH",
    "VIRTUAL_ENV",
    "CONDA_PREFIX",
    "PYTHONPATH",
    "PROJECT_ROOT",
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "PYTHONHASHSEED",
    "CUBLAS_WORKSPACE_CONFIG",
    "TORCH_DISABLE_NATIVE_JIT",
    "TRITON_CACHE_DIR",
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


def _capture_caller_environment_raw() -> dict[str, Any]:
    """Capture the inherited shell without altering or masking any requested field."""
    inherited = os.environ.copy()
    which_python = shutil.which("python", path=inherited.get("PATH"))
    caller_probe: dict[str, Any]
    if which_python is None:
        caller_probe = {"pass": False, "error": "python is not present on inherited PATH"}
    else:
        result = subprocess.run(
            [
                which_python,
                "-c",
                (
                    "import json,sys; print(json.dumps({"
                    "'sys_executable':sys.executable,'sys_prefix':sys.prefix,'sys_path':sys.path}))"
                ),
            ],
            cwd=ROOT,
            env=inherited,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        caller_probe = {
            "pass": result.returncode == 0,
            "command": [which_python, "-c", "capture sys.executable, sys.prefix, and sys.path"],
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "resolved": json.loads(result.stdout) if result.returncode == 0 else None,
        }
    return {
        "capture_order": "captured before execution-environment resolution",
        "environment_variables": {
            name: inherited.get(name) for name in ENVIRONMENT_FIELDS
        },
        "which_python": which_python,
        "caller_python_probe": caller_probe,
        "audit_builder_explicit_interpreter": {
            "sys_executable": sys.executable,
            "sys_prefix": sys.prefix,
            "note": (
                "the builder was explicitly launched with .venv/bin/python; this does not "
                "reclassify the inherited caller shell"
            ),
        },
    }


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update({
        "PATH": f"{ROOT / '.venv/bin'}:{environment.get('PATH', '')}",
        "VIRTUAL_ENV": str(ROOT / ".venv"),
        "PROJECT_ROOT": str(ROOT),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "PYTHONHASHSEED": "42",
        "CUBLAS_WORKSPACE_CONFIG": ":4096:8",
    })
    environment.pop("CONDA_PREFIX", None)
    return environment


def _execution_environment_resolved(
    environment: dict[str, str], environment_audit: dict[str, Any]
) -> dict[str, Any]:
    return {
        "resolution_policy": (
            "subprocesses use the explicit project .venv interpreter and a copied environment; "
            "caller_environment_raw is preserved separately"
        ),
        "environment_variables": {
            name: environment.get(name) for name in ENVIRONMENT_FIELDS
        },
        "which_python": shutil.which("python", path=environment.get("PATH")),
        "explicit_execution_interpreter": str(ROOT / ".venv/bin/python"),
        "sys_executable": environment_audit["sys_executable"],
        "sys_prefix": environment_audit["sys_prefix"],
        "sys_path": environment_audit["sys_path"],
        "import_paths": environment_audit["import_paths"],
    }


def _run(label: str, command: list[str], environment: dict[str, str]) -> dict[str, Any]:
    started = time.perf_counter()
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "label": label,
        "command": command,
        "cwd": str(ROOT),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_seconds": time.perf_counter() - started,
    }


def _copy(source: Path, relative: str) -> Path:
    destination = STAGE / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def _pre_source_tree() -> list[str]:
    with tarfile.open(PRE_PACK, "r:gz") as archive:
        return sorted(
            name for name in archive.getnames()
            if name.startswith("src/ccdf/") and name.endswith(".py")
        )


def _current_source_tree() -> list[str]:
    return sorted(str(path.relative_to(ROOT)) for path in (ROOT / "src/ccdf").rglob("*.py"))


def _config_snapshot(config: Config) -> dict[str, Any]:
    profile = config.resolve_active_protocol_profile()
    return {
        "source_config_path": str(config.path),
        "source_config_sha256": _sha256(config.path),
        "canonical_fixed_block_size": config.require(
            "optimization.block_policy.fixed_block_size"
        ),
        "checkpoint_block_size": config.require(
            "models.dflash.drafter.checkpoint_block_size"
        ),
        "active_profile": profile.name,
        "active_profile_fixed_block_size": profile.config.require(
            "optimization.block_policy.fixed_block_size"
        ),
        "memory_residency": {
            "compressor_stage": config.require("memory.compressor_residency_mode"),
            "generation_stage": config.require("memory.generation_residency_mode"),
            "compressor_budget_gib": config.require(
                "models.compressor.reserved_budget_gib"
            ),
            "dflash_limit_gib": config.require("memory.dflash_peak_reserved_limit_gib"),
            "device_capacity_gib": config.require("memory.device_capacity_gib"),
        },
        "resolved": profile.snapshot(),
    }


def _production_phase_name_scan() -> dict[str, Any]:
    pattern = re.compile(r"\b(?:rec|phase|task)[ _-]?\d+\b", re.IGNORECASE)
    files = sorted((ROOT / "src/ccdf").rglob("*.py"))
    path_matches: list[dict[str, Any]] = []
    content_matches: list[dict[str, Any]] = []
    scanned = []
    for path in files:
        relative = str(path.relative_to(ROOT))
        text = path.read_text(encoding="utf-8")
        scanned.append({"path": relative, "sha256": _sha256(path)})
        for match in pattern.finditer(relative):
            path_matches.append({"path": relative, "match": match.group(0)})
        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in pattern.finditer(line):
                content_matches.append({
                    "path": relative,
                    "line": line_number,
                    "match": match.group(0),
                })
    return {
        "pass": not path_matches and not content_matches,
        "pattern": pattern.pattern,
        "scope": "all Python production paths and file content under src/ccdf",
        "path_matches": path_matches,
        "content_matches": content_matches,
        "scanned_files": scanned,
    }


def _import_origin_audit(environment_audit: dict[str, Any]) -> dict[str, Any]:
    origins = environment_audit["import_paths"]
    venv = (ROOT / ".venv").resolve()
    project_source = (ROOT / "src/ccdf").resolve()
    third_party = ("torch", "transformers", "llmlingua", "awq")
    gates = {
        "ccdf_from_project_editable_source": Path(origins["ccdf"]).resolve().is_relative_to(
            project_source
        ),
        "third_party_imports_from_project_venv": all(
            Path(origins[name]).resolve().is_relative_to(venv) for name in third_party
        ),
        "no_external_site_packages_on_execution_sys_path": not environment_audit[
            "external_site_packages"
        ],
    }
    return {
        "pass": all(gates.values()),
        "gates": gates,
        "origins": origins,
        "interpretation": (
            "ccdf resolves to the editable project source; all installed third-party modules "
            "resolve inside the project .venv"
        ),
    }


def _memory_config_audit(config: Config, final_root: Path) -> dict[str, Any]:
    compressor_mode = str(config.require("memory.compressor_residency_mode"))
    generation_mode = str(config.require("memory.generation_residency_mode"))
    compressor_budget = float(config.require("models.compressor.reserved_budget_gib"))
    dflash_limit = float(config.require("memory.dflash_peak_reserved_limit_gib"))
    capacity = float(config.require("memory.device_capacity_gib"))
    staged_warnings = config.validate(False)
    simultaneous_data = copy.deepcopy(config.data)
    simultaneous_data["memory"]["compressor_residency_mode"] = "simultaneous"
    simultaneous_data["memory"]["generation_residency_mode"] = "simultaneous"
    simultaneous_config = type(config)(
        path=config.path, root=config.root, data=simultaneous_data
    )
    simultaneous_warnings = simultaneous_config.validate(False)
    raw = _json(final_root / "raw_runs.json")
    summary = _json(final_root / "summary.json")
    events = [entry["event"] for entry in raw["lifecycle"]]
    compressor_closed_index = events.index("compressor_closed")
    first_generation_load_index = events.index("before_load")
    memory_gate = summary["memory_gate"]
    gates = {
        "configured_staged_residency": (
            compressor_mode == "staged" and generation_mode == "staged"
        ),
        "staged_config_does_not_warn_about_combined_budget": not any(
            "simultaneous" in warning for warning in staged_warnings
        ),
        "simultaneous_config_warns_when_combined_budget_exceeds_capacity": (
            compressor_budget + dflash_limit > capacity
            and any("simultaneous" in warning for warning in simultaneous_warnings)
        ),
        "compressor_closed_before_generation_load": (
            compressor_closed_index < first_generation_load_index
        ),
        "runtime_reports_no_stage_overlap": (
            memory_gate["compressor_and_generation_overlap"] is False
        ),
        "runtime_does_not_add_compressor_budget_to_dflash_limit": (
            memory_gate["compressor_budget_added_to_dflash_limit"] is False
            and memory_gate["peak_reserved_limit_gib"] == dflash_limit
        ),
    }
    return {
        "pass": all(gates.values()),
        "gates": gates,
        "configured": {
            "compressor_residency_mode": compressor_mode,
            "generation_residency_mode": generation_mode,
            "compressor_budget_gib": compressor_budget,
            "dflash_limit_gib": dflash_limit,
            "device_capacity_gib": capacity,
        },
        "staged_validation_warnings": staged_warnings,
        "simultaneous_validation_warnings": simultaneous_warnings,
        "lifecycle_indices": {
            "compressor_closed": compressor_closed_index,
            "first_generation_before_load": first_generation_load_index,
        },
        "runtime_memory_gate": memory_gate,
    }


def _metric_key(result: dict[str, Any]) -> str:
    if "protocol_metrics" in result:
        return "protocol_metrics"
    return "rec3_metrics"


def _mock_comparison(
    pre_root: Path, final_root: Path, config: Config
) -> dict[str, Any]:
    pre_raw = _json(pre_root / "raw_runs.json")
    post_raw = _json(final_root / "raw_runs.json")
    post_summary = _json(final_root / "summary.json")
    post_parity = _json(final_root / "pair_parity.json")
    post_protected = _json(final_root / "protected_field_hashes.json")
    row_checks: list[dict[str, Any]] = []
    output_hash_rows: list[dict[str, Any]] = []
    prompt_hash_rows: list[dict[str, Any]] = []
    for index, (pre_prompt, post_prompt) in enumerate(
        zip(pre_raw["prompts"], post_raw["prompts"], strict=True), start=1
    ):
        for condition in pre_prompt["runs"]:
            pre_run = pre_prompt["runs"][condition]
            post_run = post_prompt["runs"][condition]
            pre_result = pre_run["result"]
            post_result = post_run["result"]
            pre_metrics = pre_result[_metric_key(pre_result)]
            post_metrics = post_result[_metric_key(post_result)]
            pre_token_hash = hashlib.sha256(
                json.dumps(pre_result["generated_token_ids"], separators=(",", ":")).encode()
            ).hexdigest()
            post_token_hash = hashlib.sha256(
                json.dumps(post_result["generated_token_ids"], separators=(",", ":")).encode()
            ).hexdigest()
            tokens_equal = pre_result["generated_token_ids"] == post_result["generated_token_ids"]
            raw_prompt_hash_equal = (
                pre_metrics["raw_rendered_prompt_sha256"]
                == post_metrics["raw_rendered_prompt_sha256"]
            )
            chat_prompt_hash_equal = (
                pre_metrics["chat_template_input"]["token_ids_sha256"]
                == post_metrics["chat_template_input"]["token_ids_sha256"]
            )
            row_checks.append({
                "fixture_index": index,
                "condition": condition,
                "success": post_run["success"] is True,
                "output_token_ids_equal": tokens_equal,
                "raw_prompt_hash_equal": raw_prompt_hash_equal,
                "chat_template_token_hash_equal": chat_prompt_hash_equal,
            })
            output_hash_rows.append({
                "fixture_index": index,
                "condition": condition,
                "pre_sha256": pre_token_hash,
                "post_sha256": post_token_hash,
                "equal": pre_token_hash == post_token_hash and tokens_equal,
            })
            prompt_hash_rows.append({
                "fixture_index": index,
                "condition": condition,
                "pre_raw_prompt_sha256": pre_metrics["raw_rendered_prompt_sha256"],
                "post_raw_prompt_sha256": post_metrics["raw_rendered_prompt_sha256"],
                "pre_chat_token_ids_sha256": pre_metrics["chat_template_input"][
                    "token_ids_sha256"
                ],
                "post_chat_token_ids_sha256": post_metrics["chat_template_input"][
                    "token_ids_sha256"
                ],
                "equal": raw_prompt_hash_equal and chat_prompt_hash_equal,
            })

    pre_summary = _json(pre_root / "summary.json")
    timing_fields = (
        "p50_compression_latency_ms",
        "p50_prefill_latency_ms",
        "p50_decode_latency_ms",
        "p50_generation_latency_ms",
        "p50_stage_sum_warm_e2e_ms",
        "p50_decode_tok_s",
    )
    metric_deltas = {
        condition: {
            field: (
                float(post_summary["conditions"][condition][field])
                - float(pre_summary["conditions"][condition][field])
            )
            for field in timing_fields
        }
        for condition in post_summary["conditions"]
    }
    exact_quality = sum(
        quality["exact_field_match"]
        for prompt in post_raw["prompts"]
        for quality in prompt["output_quality"].values()
    )
    gates = {
        "condition_success_40_of_40": sum(row["success"] for row in row_checks) == 40,
        "generated_token_pair_parity_20_of_20": (
            len(post_parity) == 20 and all(row["pass"] for row in post_parity)
        ),
        "exact_quality_40_of_40": exact_quality == 40,
        "protected_fields_10_of_10": (
            len(post_protected) == 10 and all(row["pass"] for row in post_protected)
        ),
        "pre_post_output_token_ids_40_of_40": all(
            row["output_token_ids_equal"] for row in row_checks
        ),
        "pre_post_prompt_hashes_40_of_40": all(
            row["raw_prompt_hash_equal"] and row["chat_template_token_hash_equal"]
            for row in row_checks
        ),
        "memory_gate_matches_config_and_passes": (
            post_summary["memory_gate"]["peak_reserved_limit_gib"]
            == float(config.require("memory.dflash_peak_reserved_limit_gib"))
            and post_summary["memory_gate_pass"] is True
        ),
        "overall_pass": post_summary["overall_pass"] is True,
    }
    return {
        "pass": all(gates.values()),
        "gates": gates,
        "row_checks": row_checks,
        "output_token_hashes": output_hash_rows,
        "prompt_hashes": prompt_hash_rows,
        "timing_deltas_post_minus_pre": metric_deltas,
        "timing_delta_policy": "reported only; exact timing parity is not required",
    }


def _device_audit(final_root: Path, environment_audit: dict[str, Any]) -> dict[str, Any]:
    raw = _json(final_root / "raw_runs.json")
    model_audits: list[dict[str, Any]] = []
    inference_audits: list[dict[str, Any]] = []
    attention_audits: list[dict[str, Any]] = []
    determinism_audits: list[dict[str, Any]] = []
    local_only: list[bool] = []
    for prompt in raw["prompts"]:
        for condition, run in prompt["runs"].items():
            result = run["result"]
            model = result["model"]
            if result["condition"] == "baseline":
                model_audits.append(model["device_audit"])
                attention_audits.append(model["attention"])
            else:
                model_audits.extend((model["target_device_audit"], model["drafter_device_audit"]))
                attention_audits.extend((model["target_attention"], model["drafter_attention"]))
            inference_audits.append(result["runtime"]["inference_tensor_audit"])
            determinism_audits.append(result["runtime"]["determinism"])
            local_only.append(model["local_files_only"] is True)
    compressor = raw["compressor"]
    gates = {
        "python_executable_is_project_venv": environment_audit["sys_executable_is_project_venv"],
        "python_prefix_is_project_venv": environment_audit["sys_prefix_is_project_venv"],
        "resolved_execution_has_no_external_or_conda_site_packages": (
            not environment_audit["external_site_packages"]
            and environment_audit["conda_prefix"] is None
        ),
        "all_model_parameters_and_buffers_cuda": all(
            audit["all_tensors_cuda"] and not audit["cpu_or_disk_offload"]
            for audit in model_audits
        ),
        "all_inference_inputs_cuda": all(
            audit["input_ids_cuda"] and not audit["cpu_or_disk_offload"]
            for audit in inference_audits
        ),
        "compressor_parameters_and_buffers_cuda": (
            compressor["device_audit"]["all_tensors_cuda"]
            and not compressor["device_audit"]["cpu_offload"]
        ),
        "local_files_only_all_loads": (
            all(local_only)
            and compressor["model_contract"]["local_files_only"] is True
            and environment_audit["local_only"]["config_local_files_only"] is True
            and environment_audit["local_only"]["hf_hub_offline"] == "1"
            and environment_audit["local_only"]["transformers_offline"] == "1"
        ),
        "effective_runtime_sdpa_math_only": all(
            audit["attn_implementation"] == "sdpa"
            and audit["math_sdp_enabled"] is True
            and audit["flash_sdp_enabled"] is False
            and audit["mem_efficient_sdp_enabled"] is False
            for audit in attention_audits
        ),
        "effective_runtime_tf32_disabled": all(
            audit["allow_tf32_effective"] is False
            and audit["flash_sdp_enabled"] is False
            and audit["mem_efficient_sdp_enabled"] is False
            and audit["math_sdp_enabled"] is True
            for audit in determinism_audits
        ),
    }
    return {
        "pass": all(gates.values()),
        "gates": gates,
        "unique_model_audits": list({json.dumps(item, sort_keys=True): item for item in model_audits}.values()),
        "unique_inference_tensor_audits": list(
            {json.dumps(item, sort_keys=True): item for item in inference_audits}.values()
        ),
        "compressor_device_audit": compressor["device_audit"],
        "effective_runtime_sdpa_state": {
            "attention_states": list(
                {json.dumps(item, sort_keys=True): item for item in attention_audits}.values()
            ),
            "determinism_states": list(
                {json.dumps(item, sort_keys=True): item for item in determinism_audits}.values()
            ),
            "hard_gate": {
                "math": True,
                "flash": False,
                "memory_efficient": False,
                "tf32": False,
            },
        },
    }


def _checkpoint_manifest(config: Config) -> dict[str, Any]:
    model_keys = {
        "baseline": "models.baseline.local_path",
        "dflash_target": "models.dflash.target.local_path",
        "dflash_drafter": "models.dflash.drafter.local_path",
        "compressor": "models.compressor.local_path",
    }
    hash_cache: dict[tuple[int, int, int], str] = {}
    models: dict[str, Any] = {}
    for label, key in model_keys.items():
        directory = config.path_for(key)
        files = []
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            if path.name in {"config.json", "generation_config.json", "dflash.py", "modeling_dflash.py", "utils.py"}:
                category = "config_or_remote_source"
            elif path.name.startswith("tokenizer") or path.name in {
                "special_tokens_map.json", "vocab.json", "merges.txt", "sentencepiece.bpe.model"
            }:
                category = "tokenizer"
            elif path.suffix in {".safetensors", ".bin", ".pt", ".pth"}:
                category = "weights"
            else:
                continue
            stat = path.stat()
            cache_key = (stat.st_dev, stat.st_ino, stat.st_size)
            digest = hash_cache.setdefault(cache_key, _sha256(path))
            files.append({
                "filename": path.name,
                "category": category,
                "bytes": stat.st_size,
                "sha256": digest,
            })
        names = {item["filename"] for item in files}
        has_weights = any(item["category"] == "weights" and item["bytes"] > 0 for item in files)
        has_tokenizer = any(item["category"] == "tokenizer" for item in files)
        complete = "config.json" in names and has_weights and (
            label == "dflash_drafter" or has_tokenizer
        )
        if label == "dflash_drafter":
            complete = complete and "dflash.py" in names
        models[label] = {
            "path": str(directory.relative_to(ROOT)),
            "complete": complete,
            "files": files,
        }
    cache_dirs = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "models").glob("**/.cache/huggingface/download")
    )
    return {
        "models": models,
        "all_checkpoints_complete": all(item["complete"] for item in models.values()),
        "download_cache_directories_after_cleanup": cache_dirs,
        "download_caches_removed": not cache_dirs,
        "cache_ignore_rule_present": "models/**/.cache/" in (ROOT / ".gitignore").read_text(),
    }


def _weights_match_pre_seal(current: dict[str, Any]) -> dict[str, Any]:
    with tarfile.open(PRE_PACK, "r:gz") as archive:
        member = next(item for item in archive.getmembers() if item.name.endswith("checkpoint-manifest.json"))
        extracted = archive.extractfile(member)
        if extracted is None:
            raise RuntimeError("sealed pre-refactor checkpoint manifest is unreadable")
        previous = json.loads(extracted.read().decode("utf-8"))
    rows = []
    for label, old_model in previous["models"].items():
        current_files = {
            item["filename"]: item for item in current["models"][label]["files"]
        }
        for old_file in old_model["files"]:
            new_file = current_files.get(old_file["filename"])
            rows.append({
                "model": label,
                "filename": old_file["filename"],
                "present": new_file is not None,
                "bytes_equal": new_file is not None and new_file["bytes"] == old_file["bytes"],
                "sha256_equal": new_file is not None and new_file["sha256"] == old_file["sha256"],
            })
    return {"pass": all(row["present"] and row["bytes_equal"] and row["sha256_equal"] for row in rows), "files": rows}


def _normalized_body_sha(source: str) -> str:
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))]
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()


def _dflash_core_proof(environment: dict[str, str]) -> dict[str, Any]:
    files = sorted((ROOT / "src/ccdf/dflash").glob("*.py"))
    rows = []
    for path in files:
        relative = str(path.relative_to(ROOT))
        base = _run("git-show-dflash", ["git", "show", f"HEAD:{relative}"], environment)
        if base["exit_code"] != 0:
            raise RuntimeError(f"cannot load base D-Flash source: {relative}")
        current_text = path.read_text(encoding="utf-8")
        rows.append({
            "path": relative,
            "exact_sha256_equal": hashlib.sha256(base["stdout"].encode()).hexdigest()
            == hashlib.sha256(current_text.encode()).hexdigest(),
            "import_normalized_ast_sha256_before": _normalized_body_sha(base["stdout"]),
            "import_normalized_ast_sha256_after": _normalized_body_sha(current_text),
            "implementation_body_unchanged": (
                _normalized_body_sha(base["stdout"]) == _normalized_body_sha(current_text)
            ),
        })
    diff = _run(
        "dflash-core-diff", ["git", "diff", "HEAD", "--", "src/ccdf/dflash"], environment
    )
    return {
        "pass": all(row["implementation_body_unchanged"] for row in rows),
        "proof_scope": (
            "AST after removing module import statements; the device-module relocation is the "
            "only permitted D-Flash package change"
        ),
        "files": rows,
        "git_diff": diff,
    }


def _package_gates(phase_scan: dict[str, Any], config: Config) -> dict[str, Any]:
    from ccdf.data.pipeline import BUILDER_VERSION, COHORT_VERSION, SCHEMA_VERSION

    root_files = sorted(
        path.name for path in (ROOT / "src/ccdf").iterdir() if path.is_file() and path.suffix == ".py"
    )
    expected_root = ["__init__.py", "__main__.py", "cli.py", "config.py", "errors.py", "schemas.py"]
    moved = {
        "src/ccdf/benchmark.py": "src/ccdf/benchmark/runner.py",
        "src/ccdf/rec3/metrics.py": "src/ccdf/benchmark/metrics.py",
        "metric aggregation": "src/ccdf/benchmark/aggregation.py",
        "src/ccdf/device.py": "src/ccdf/runtime/device.py",
        "src/ccdf/determinism.py": "src/ccdf/runtime/determinism.py",
        "four-condition definitions": "src/ccdf/protocols/conditions.py",
        "four-condition orchestration": "src/ccdf/protocols/orchestrator.py",
    }
    required = [destination for destination in moved.values() if destination.startswith("src/")]
    gates = {
        "package_root_exact": root_files == expected_root,
        "phase_namespace_removed": not (ROOT / "src/ccdf/rec3").exists(),
        "all_required_destinations_exist": all((ROOT / path).is_file() for path in required),
        "no_phase_or_task_names_in_production_paths_or_content": phase_scan["pass"],
        "neutral_data_versions": {
            "schema": SCHEMA_VERSION,
            "builder": BUILDER_VERSION,
            "cohort": COHORT_VERSION,
        } == {
            "schema": "ccdf.data.v1",
            "builder": "ccdf.data-builder.v1",
            "cohort": "real-sources-seeded-v1",
        },
        "canonical_block_16": config.require(
            "optimization.block_policy.fixed_block_size"
        ) == 16,
        "four_condition_profile_block_8": config.resolve_active_protocol_profile().config.require(
            "optimization.block_policy.fixed_block_size"
        ) == 8,
        "scripts_only_system_runtime": sorted(
            str(path.relative_to(ROOT)) for path in (ROOT / "scripts").glob("*.py")
        ) == ["scripts/prepare_models.py"],
    }
    return {"pass": all(gates.values()), "gates": gates, "moved_files": moved, "root_files": root_files}


def _copy_sources() -> list[str]:
    sources = sorted((ROOT / "src/ccdf").rglob("*.py"))
    sources.extend(
        ROOT / name for name in (
            ".gitignore", "README.md", "config.yml", "pyproject.toml",
            "tests/conftest.py", "tests/build_environment_package_refactor_review_pack.py",
        )
    )
    copied = []
    for source in sources:
        relative = str(source.relative_to(ROOT))
        _copy(source, f"tracked-source/{relative}")
        copied.append(relative)
    return copied


def _seal_archive(summary: dict[str, Any]) -> dict[str, Any]:
    pack_members = STAGE / "pack-members.txt"
    manifest_path = STAGE / "sha256-manifest.json"
    verification_path = STAGE / "manifest-verification.json"
    existing = sorted(path for path in STAGE.rglob("*") if path.is_file())
    planned = sorted(
        [str(path.relative_to(STAGE)) for path in existing]
        + ["pack-members.txt", "sha256-manifest.json", "manifest-verification.json"]
    )
    _write(pack_members, "\n".join(planned) + "\n")
    hashed_paths = sorted(path for path in STAGE.rglob("*") if path.is_file() and path != manifest_path)
    manifest = {
        "manifest_version": "ccdf.environment-package-refactor.v1",
        "self_entry_policy": "sha256-manifest.json is excluded from its own hash map",
        "summary": summary,
        "members": {
            str(path.relative_to(STAGE)): {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in hashed_paths
        },
    }
    _write_json(manifest_path, manifest)
    verification = {
        name: {
            "bytes_match": (STAGE / name).stat().st_size == expected["bytes"],
            "sha256_match": _sha256(STAGE / name) == expected["sha256"],
        }
        for name, expected in manifest["members"].items()
    }
    _write_json(verification_path, {
        "pass": all(item["bytes_match"] and item["sha256_match"] for item in verification.values()),
        "verified": verification,
    })
    # Refresh entries whose content necessarily precedes the verification report.
    manifest["members"] = {
        str(path.relative_to(STAGE)): {"bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in sorted(path for path in STAGE.rglob("*") if path.is_file() and path != manifest_path)
    }
    _write_json(manifest_path, manifest)
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with tarfile.open(ARCHIVE, "w:gz") as archive:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                archive.add(path, arcname=str(path.relative_to(STAGE)), recursive=False)
    with tempfile.TemporaryDirectory(prefix="ccdf-package-refactor-pack-") as temporary:
        target = Path(temporary)
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            names = sorted(member.name for member in archive.getmembers() if member.isfile())
            archive.extractall(target, filter="data")
        extracted_manifest = _json(target / "sha256-manifest.json")
        verified = {
            name: (
                (target / name).stat().st_size == expected["bytes"]
                and _sha256(target / name) == expected["sha256"]
            )
            for name, expected in extracted_manifest["members"].items()
        }
        recorded_names = (target / "pack-members.txt").read_text().splitlines()
        forbidden = [
            name for name in names
            if name.endswith((".tar", ".tar.gz", ".tgz"))
            or any(part in {".git", ".venv", ".worktrees"} for part in Path(name).parts)
            or Path(name).parts[0] == "models"
        ]
        result = {
            "pass": all(verified.values()) and names == recorded_names and not forbidden,
            "archive": str(ARCHIVE),
            "archive_sha256": _sha256(ARCHIVE),
            "member_count": len(names),
            "verified_hashes": f"{sum(verified.values())}/{len(verified)}",
            "pack_members_exact": names == recorded_names,
            "forbidden_members": forbidden,
        }
    if not result["pass"]:
        raise RuntimeError(f"sealed review pack verification failed: {result}")
    return result


def main() -> None:
    caller_environment_raw = _capture_caller_environment_raw()
    # No inherited variable is changed or hidden before the caller capture above.
    from ccdf.config import load_config

    config = load_config(CONFIG_PATH)
    profile = config.resolve_active_protocol_profile()
    final_root = profile.path_for("artifact_directory")
    environment = _environment()
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)

    commands = [
        _run("validate-config", [str(ROOT / ".venv/bin/python"), "-m", "ccdf", "validate-config", "--config", str(CONFIG_PATH)], environment),
        _run("installed-cli-help", [str(ROOT / ".venv/bin/ccdf"), "--help"], environment),
        _run("validate-environment", [str(ROOT / ".venv/bin/python"), "-m", "ccdf", "validate-env", "--config", str(CONFIG_PATH)], environment),
        _run("pip-check", [str(ROOT / ".venv/bin/python"), "-m", "pip", "check"], environment),
        _run("pip-list", [str(ROOT / ".venv/bin/python"), "-m", "pip", "list", "--format=json"], environment),
        _run("pip-freeze-all", [str(ROOT / ".venv/bin/python"), "-m", "pip", "freeze", "--all"], environment),
        _run("nvidia-smi", ["nvidia-smi", "--query-gpu=name,uuid,driver_version,memory.total,memory.used,compute_cap", "--format=csv,noheader"], environment),
        _run(
            "production-source-content-phase-grep",
            [
                "rg", "--line-number", "--ignore-case",
                r"\b(?:rec|phase|task)[ _-]?[0-9]+\b", "src/ccdf", "--glob", "*.py",
            ],
            environment,
        ),
        _run(
            "production-source-path-phase-grep",
            [
                "bash", "--noprofile", "--norc", "-c",
                (
                    "set -o pipefail; rg --files src/ccdf --glob '*.py' | "
                    "rg --ignore-case '\\b(?:rec|phase|task)[ _-]?[0-9]+\\b'"
                ),
            ],
            environment,
        ),
        _run("offline-mock10", [str(ROOT / ".venv/bin/python"), "-m", "ccdf", "protocol", "--config", str(CONFIG_PATH)], environment),
        _run("compileall", [str(ROOT / ".venv/bin/python"), "-m", "compileall", "-q", "src", "scripts", "tests"], environment),
        _run("pytest", [str(ROOT / ".venv/bin/pytest"), "-q"], environment),
        _run("git-diff-check", ["git", "diff", "--check"], environment),
    ]
    no_match_labels = {
        "production-source-content-phase-grep",
        "production-source-path-phase-grep",
    }
    for item in commands:
        item["expected_exit_code"] = 1 if item["label"] in no_match_labels else 0
        item["pass"] = item["exit_code"] == item["expected_exit_code"]
    command_pass = all(item["pass"] for item in commands)
    _write_json(STAGE / "commands.json", commands)
    _write(STAGE / "commands.txt", "".join(
        f"$ {' '.join(item['command'])}\nexit={item['exit_code']}\n"
        f"duration_seconds={item['duration_seconds']}\n--- stdout ---\n{item['stdout']}"
        f"--- stderr ---\n{item['stderr']}\n\n"
        for item in commands
    ))
    if not command_pass:
        raise SystemExit(
            f"command gate failed: {[item['label'] for item in commands if not item['pass']]}"
        )

    environment_audit = json.loads(next(item for item in commands if item["label"] == "validate-environment")["stdout"])
    execution_environment_resolved = _execution_environment_resolved(
        environment, environment_audit
    )
    phase_scan = _production_phase_name_scan()
    package = _package_gates(phase_scan, config)
    comparison = _mock_comparison(PRE_ROOT, final_root, config)
    device = _device_audit(final_root, environment_audit)
    import_origins = _import_origin_audit(environment_audit)
    memory_config = _memory_config_audit(config, final_root)
    freeze_command = next(item for item in commands if item["label"] == "pip-freeze-all")
    environment_lock = freeze_command["stdout"]
    environment_lock_gate = (
        freeze_command["exit_code"] == 0
        and "torch==" in environment_lock
        and "transformers==" in environment_lock
        and "autoawq==" in environment_lock.lower()
        and "llmlingua==" in environment_lock.lower()
    )
    mock_command = next(item for item in commands if item["label"] == "offline-mock10")
    autoawq_risk = {
        "component": "AutoAWQ",
        "compatibility_risk": "upstream package emits a deprecation warning",
        "deprecation_warning_observed": "AutoAWQ is officially deprecated" in mock_command["stderr"],
        "batch_gate": False,
        "mock10_exit_code": mock_command["exit_code"],
        "warning_did_not_fail_batch": mock_command["exit_code"] == 0,
    }
    autoawq_risk["pass"] = (
        autoawq_risk["deprecation_warning_observed"]
        and autoawq_risk["warning_did_not_fail_batch"]
    )
    checkpoints = _checkpoint_manifest(config)
    weight_comparison = _weights_match_pre_seal(checkpoints)
    dflash = _dflash_core_proof(environment)
    config_snapshot = _config_snapshot(config)
    base_commit = _run("base-commit", ["git", "rev-parse", "HEAD"], environment)
    git_status = _run("git-status", ["git", "status", "--short", "--untracked-files=all"], environment)
    git_diff = _run("git-diff", ["git", "diff", "--no-ext-diff", "HEAD"], environment)
    changed = _run("changed-files", ["git", "status", "--short", "--untracked-files=all"], environment)

    _write(STAGE / "tree-before.txt", "\n".join(_pre_source_tree()) + "\n")
    _write(STAGE / "tree-after.txt", "\n".join(_current_source_tree()) + "\n")
    _write_json(STAGE / "caller_environment_raw.json", caller_environment_raw)
    _write_json(
        STAGE / "execution_environment_resolved.json", execution_environment_resolved
    )
    _write_json(STAGE / "environment-audit.json", {
        "caller_environment_raw": caller_environment_raw,
        "execution_environment_resolved": execution_environment_resolved,
        "runtime_preflight": environment_audit,
        "import_origin_audit": import_origins,
    })
    _write_json(
        STAGE / "process-default-sdpa-state.json",
        environment_audit["process_default_sdpa_state"],
    )
    _write_json(
        STAGE / "effective-runtime-sdpa-state.json",
        device["effective_runtime_sdpa_state"],
    )
    _write_json(STAGE / "import-origin-audit.json", import_origins)
    _write(STAGE / "environment-lock.txt", environment_lock)
    _write_json(STAGE / "environment-lock-metadata.json", {
        "pass": environment_lock_gate,
        "source_interpreter": str(ROOT / ".venv/bin/python"),
        "command": freeze_command["command"],
        "sha256": hashlib.sha256(environment_lock.encode()).hexdigest(),
        "package_upgrade_or_downgrade_commands": [],
        "policy": "captured from the working .venv without package mutation",
    })
    _write_json(STAGE / "autoawq-compatibility-risk.json", autoawq_risk)
    _write_json(STAGE / "resolved-config-snapshot.json", config_snapshot)
    _write_json(STAGE / "config-memory-validation.json", memory_config)
    _write_json(STAGE / "moved-files-map.json", package["moved_files"])
    _write_json(STAGE / "package-refactor-gates.json", package)
    _write_json(STAGE / "production-source-phase-name-scan.json", phase_scan)
    _write_json(STAGE / "device-residency-and-local-only-audit.json", device)
    _write_json(STAGE / "checkpoint-manifest.json", checkpoints)
    _write_json(STAGE / "pre-post-checkpoint-hash-comparison.json", weight_comparison)
    _write_json(STAGE / "model-cache-audit.json", {
        "checkpoints_complete_before_cleanup": checkpoints["all_checkpoints_complete"],
        "download_cache_directories_after_cleanup": checkpoints[
            "download_cache_directories_after_cleanup"
        ],
        "download_caches_removed": checkpoints["download_caches_removed"],
        "cache_ignore_rule_present": checkpoints["cache_ignore_rule_present"],
        "weights_and_tokenizers_preserved": weight_comparison["pass"],
    })
    _write_json(STAGE / "mock10-comparison.json", comparison)
    _write_json(STAGE / "pre-post-output-token-hash-comparison.json", comparison["output_token_hashes"])
    _write_json(STAGE / "pre-post-prompt-hash-comparison.json", comparison["prompt_hashes"])
    _write_json(STAGE / "timing-deltas.json", comparison["timing_deltas_post_minus_pre"])
    _write_json(STAGE / "dflash-core-unchanged-proof.json", dflash)
    _write(STAGE / "base-commit.txt", base_commit["stdout"])
    _write(STAGE / "git-status.txt", git_status["stdout"])
    _write(STAGE / "git-diff.patch", git_diff["stdout"])
    _write(STAGE / "changed-files.txt", changed["stdout"] + (
        "\n# ignored audit files explicitly included\n"
        "tests/conftest.py\n"
        "tests/build_environment_package_refactor_review_pack.py\n"
    ))
    copied_sources = _copy_sources()
    _write_json(STAGE / "tracked-source-files.json", copied_sources)
    for name in FINAL_ARTIFACT_NAMES:
        _copy(PRE_ROOT / name, f"mock10/pre-refactor/{name}")
        _copy(final_root / name, f"mock10/post-refactor/{name}")

    overall = {
        "command_gates_pass": command_pass,
        "package_refactor_pass": package["pass"],
        "mock10_comparison_pass": comparison["pass"],
        "environment_and_device_audit_pass": device["pass"],
        "caller_environment_captured_before_resolution": (
            caller_environment_raw["capture_order"]
            == "captured before execution-environment resolution"
            and caller_environment_raw["caller_python_probe"]["pass"]
        ),
        "import_origin_audit_pass": import_origins["pass"],
        "effective_runtime_sdpa_gate_pass": (
            device["gates"]["effective_runtime_sdpa_math_only"]
            and device["gates"]["effective_runtime_tf32_disabled"]
        ),
        "memory_config_validation_pass": memory_config["pass"],
        "exact_environment_lock_pass": environment_lock_gate,
        "autoawq_compatibility_risk_recorded": autoawq_risk["pass"],
        "checkpoint_completeness_pass": checkpoints["all_checkpoints_complete"],
        "pre_post_checkpoint_hashes_pass": weight_comparison["pass"],
        "model_cache_cleanup_pass": (
            checkpoints["download_caches_removed"] and checkpoints["cache_ignore_rule_present"]
        ),
        "dflash_core_implementation_unchanged": dflash["pass"],
    }
    overall["pass"] = all(overall.values())
    _write_json(STAGE / "FINAL-VALIDATION-SUMMARY.json", overall)
    if not overall["pass"]:
        raise SystemExit(f"refusing to seal failing review pack: {overall}")
    sealed = _seal_archive(overall)
    print(json.dumps({**overall, **sealed}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
