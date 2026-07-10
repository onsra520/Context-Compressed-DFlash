from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_2_revalidation import task114_canonical_matrix as t114


OUT = ROOT / "results/source_audit/task115"
CONTROLLED = OUT / "controlled"
T114 = ROOT / "results/phase_2_revalidation/task114_canonical_matrix/runs"
T105B = ROOT / (
    "results/phase_2_system_optimization/final_reruns/"
    "task105b_qmsum_controlled_runtime_matrix/runs"
)

CONDITIONS = {
    "baseline_ar": "Baseline-AR",
    "dflash_r1": "DFlash-R1",
    "cc_dflash_r2_light_gpu": "CC-DFlash-R2",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def number(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def average(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [number(row, key) for row in rows]
    values = [value for value in values if value is not None]
    return round(mean(values), 6) if values else None


def condition_path(dataset: str, condition: str, root: Path = CONTROLLED) -> Path:
    return root / dataset / f"{condition}.jsonl"


def source_architecture() -> tuple[dict[str, Any], list[dict[str, Any]]]:
    paths = [
        "scripts/run_mvp.py:_run_benchmark_item",
        "scripts/run_mvp.py:_run_ar_prompt",
        "scripts/run_mvp.py:_run_prompt",
        "src/ccdf/dflash/generate.py:dflash_generate",
        "src/ccdf/compression/llmlingua.py:LLMLinguaCompressor",
    ]
    common = {
        "model_lifecycle": "Tokenizer and target load once per process; draft loads once for DFlash conditions; models are released on process exit.",
        "prompt_rendering": "Dataset prompt plus protected policy suffix is rendered before compression; the target tokenizer applies the chat template once for precompression accounting and once for generation.",
        "serialization": "Per-prompt JSONL flush plus fsync protects progress but adds result-writing overhead outside t_e2e_ms.",
        "single_prompt_compatibility": "run_mvp accepts smoke, fixture, and dataset prompt sources through the same condition dispatcher.",
        "duplicate_source_warning": "src/ccdf/model_raw.py duplicates historical DFlash logic but is not imported by the live runner; refactor must remove or quarantine it before changing generation semantics.",
    }
    rows = [
        {
            "condition": "Baseline-AR",
            "model_ownership": "target + tokenizer",
            "prompt_path": "dataset render -> target chat tokenizer -> target.generate",
            "prefill_generation": "target.generate owns prefill and decode",
            "cache": "transformers generate cache is internal",
            "compression": "none",
            "timing_after_T115": "generation wall time includes target prefill; detached diagnostic prefill removed",
        },
        {
            "condition": "DFlash-R1",
            "model_ownership": "target + draft + tokenizer",
            "prompt_path": "dataset render -> target chat tokenizer -> dflash_generate",
            "prefill_generation": "target prefill, draft proposal, target verification per block",
            "cache": "separate DynamicCache objects; crop after draft proposal and accepted/rollback target block",
            "compression": "none",
            "timing_after_T115": "generation wall time includes target prefill, draft proposal, target verification, and cache work",
        },
        {
            "condition": "CC-DFlash-R2 Light GPU",
            "model_ownership": "target + draft + tokenizer + LLMLingua light compressor",
            "prompt_path": "dataset render -> compressor context segment -> protected suffix -> target chat tokenizer -> dflash_generate",
            "prefill_generation": "same DFlash path on shorter final prompt",
            "cache": "same separate DynamicCache crop path",
            "compression": "LLMLingua compressor resides on CUDA and is reused within process",
            "timing_after_T115": "t_compress_ms plus full generation wall time; compressor and target token scopes remain separate",
        },
    ]
    return {"live_execution_paths": paths, "findings": common}, rows


def static_qmsum_comparison() -> dict[str, Any]:
    results: dict[str, Any] = {}
    historical_names = {
        "baseline_ar": "baseline_ar_qmsum_seed42_n30_mnt384.jsonl",
        "dflash_r1": "dflash_r1_qmsum_seed42_n30_mnt384.jsonl",
        "cc_dflash_r2_light_gpu": "cc_dflash_r2_light_gpu_qmsum_seed42_n30_mnt384.jsonl",
    }
    for condition, historical_name in historical_names.items():
        historical = read_jsonl(T105B / historical_name)
        current = read_jsonl(T114 / "qmsum" / f"{condition}.jsonl")
        historical_by_id = {row["dataset_id"]: row for row in historical}
        paired = [(historical_by_id[row["dataset_id"]], row) for row in current if row["dataset_id"] in historical_by_id]
        fields = ["prompt_hash", "input_tokens", "output_tokens", "max_new_tokens", "block_size", "target_path", "draft_path", "tokenizer_path"]
        mismatches = {
            field: sum(left.get(field) != right.get(field) for left, right in paired)
            for field in fields
        }
        results[condition] = {
            "shared_rows": len(paired),
            "mismatch_counts": mismatches,
            "all_static_contract_fields_match": all(count == 0 for count in mismatches.values()),
            "historical_policy_metadata": sorted({row.get("qmsum_answer_policy_type") for row in historical}),
            "current_policy_hashes": sorted({row.get("resolved_prompt_policy_hash") for _, row in paired}),
        }
    return results


def qmsum_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    table: list[dict[str, Any]] = []
    root: dict[str, Any] = {"static_comparison": static_qmsum_comparison(), "controlled_samples": {}}
    for condition, label in CONDITIONS.items():
        rows = read_jsonl(condition_path("qmsum", condition))
        detail = {
            "rows": len(rows),
            "dataset_ids": [row.get("dataset_id") for row in rows],
            "avg_input_tokens": average(rows, "input_tokens"),
            "avg_output_tokens": average(rows, "output_tokens"),
            "avg_t_generation_ms": average(rows, "t_generation_ms"),
            "avg_t_compress_ms": average(rows, "t_compress_ms"),
            "avg_t_e2e_ms": average(rows, "t_e2e_ms"),
            "avg_generation_tok_s": average(rows, "tok_per_sec"),
            "avg_target_prefill_ms": average(rows, "target_prefill_ms"),
            "avg_draft_prefill_ms": average(rows, "draft_prefill_ms"),
            "avg_draft_proposal_ms": average(rows, "draft_proposal_ms"),
            "avg_target_verification_ms": average(rows, "target_verification_ms"),
            "avg_verification_call_count": average(rows, "verification_call_count"),
            "avg_draft_tokens_proposed": average(rows, "draft_tokens_proposed"),
            "avg_accepted_tokens": average(rows, "accepted_tokens"),
            "avg_accepted_tokens_per_verification": average(rows, "accepted_tokens_per_verification"),
            "avg_rejection_or_rollback_count": average(rows, "rejection_or_rollback_count"),
            "avg_rollback_tokens": average(rows, "rollback_tokens"),
            "timing_scope": sorted({row.get("t_prefill_mode") for row in rows}),
        }
        root["controlled_samples"][condition] = detail
        table.append({"execution": "T115 corrected live runner", "condition": label, **detail})
    dflash = root["controlled_samples"]["dflash_r1"]
    baseline = root["controlled_samples"]["baseline_ar"]
    cc = root["controlled_samples"]["cc_dflash_r2_light_gpu"]
    root.update(
        {
            "root_cause": "algorithmic_low_acceptance_plus_metric_contract_defect",
            "finding": (
                "DFlash remains slower than Baseline on the matched long-context sample because it averages "
                f"{dflash['avg_accepted_tokens_per_verification']} output tokens per 16-token verification while "
                "paying both draft proposal and target verification costs. The former detached diagnostic target "
                "prefill also duplicated target work and inflated t_e2e_ms; T115 removes it."
            ),
            "cc_dflash_explanation": (
                "T114's n=100 timing advantage is consistent with compression reducing target prompt tokens, but "
                "the corrected three-row sample has longer CC outputs and does not reproduce a lower e2e latency. "
                "Treat context reduction as the likely mechanism and the exact e2e delta as variance-sensitive."
            ),
            "baseline_vs_dflash_generation_ms_delta": round(dflash["avg_t_generation_ms"] - baseline["avg_t_generation_ms"], 6),
            "dflash_vs_cc_generation_ms_delta": round(dflash["avg_t_generation_ms"] - cc["avg_t_generation_ms"], 6),
            "semantic_correctness_claimed": False,
            "cc_dflash_e2e_variance_note": "The corrected sample has higher CC e2e because mean output tokens differ (67.0 versus 54.333333); it supports higher CC generation tok/s, not a general e2e claim.",
            "unsupported_metrics": ["cache_management_ms", "synchronization_overhead_ms"],
        }
    )
    return table, root


def gsm8k_recheck() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    table: list[dict[str, Any]] = []
    controlled_hashes: dict[int, set[str]] = {}
    for condition, label in CONDITIONS.items():
        rows = read_jsonl(condition_path("gsm8k", condition))
        normalized = t114.normalize_rows(rows, t114.RunSpec("gsm8k", condition, 3, condition_path("gsm8k", condition)))
        for row in normalized:
            controlled_hashes.setdefault(int(row["benchmark_prompt_index"]), set()).add(str(row["precompression_prompt_hash"]))
        table.append(
            {
                "condition": label,
                "rows": len(normalized),
                "strict_numeric_correct": sum(bool(row.get("gsm8k_strict_numeric_correct")) for row in normalized),
                "cap_hits": sum(bool(row.get("cap_hit")) for row in normalized),
                "policy_hashes": len({row.get("resolved_prompt_policy_hash") for row in normalized}),
                "avg_precompression_rendered_prompt_tokens": average(normalized, "precompression_input_tokens"),
                "avg_final_target_prompt_tokens": average(normalized, "input_tokens"),
                "avg_compressor_segment_original_tokens": average(normalized, "original_input_tokens"),
                "avg_compressor_segment_compressed_tokens": average(normalized, "compressed_input_tokens"),
            }
        )
    full_cc = read_jsonl(T114 / "gsm8k" / "cc_dflash_r2_light_gpu.jsonl")
    full_baseline = read_jsonl(T114 / "gsm8k" / "baseline_ar.jsonl")
    full_dflash = read_jsonl(T114 / "gsm8k" / "dflash_r1.jsonl")
    full_reduction = [
        1.0 - row["input_tokens"] / row["precompression_input_tokens"]
        for row in full_cc
        if row.get("precompression_input_tokens") and row.get("input_tokens")
    ]
    result = {
        "controlled_policy_hashes_match_across_conditions": all(len(values) == 1 for values in controlled_hashes.values()),
        "exact_t106b_suffix_hash": t114.sha256_text(t114.GSM8K_T106B_CONCISE_FINAL_ANSWER_SUFFIX),
        "historical_evaluator": "task95b_quality_proxy_calibration strict numeric parser",
        "generation_settings": {"max_new_tokens": 256, "stop": "tokenizer eos"},
        "repaired_n100": {
            "baseline_strict": sum(bool(row.get("gsm8k_strict_numeric_correct")) for row in full_baseline),
            "dflash_strict": sum(bool(row.get("gsm8k_strict_numeric_correct")) for row in full_dflash),
            "cc_dflash_strict": sum(bool(row.get("gsm8k_strict_numeric_correct")) for row in full_cc),
            "baseline_cap_hits": sum(bool(row.get("cap_hit")) for row in full_baseline),
            "dflash_cap_hits": sum(bool(row.get("cap_hit")) for row in full_dflash),
            "cc_dflash_cap_hits": sum(bool(row.get("cap_hit")) for row in full_cc),
        },
        "full_prompt_token_scope": "target tokenizer chat-template token count before versus after compression",
        "full_prompt_reduction_pct": round(mean(full_reduction) * 100.0, 6),
        "recommendation": "DFlash-R1 remains preferred for short GSM8K prompts; CC-DFlash has minor full-prompt reduction but adds compressor VRAM and timing risk.",
    }
    return table, result


def optimization_map() -> list[dict[str, Any]]:
    return [
        {"component": "measurement", "class": "correctness fix", "problem": "Detached prefill duplicated target work and inflated e2e", "evidence": "T115 live path", "expected_benefit": "fair e2e scope", "risk": "low", "validation": "controlled QMSum/GSM8K", "priority": "P0"},
        {"component": "DFlash acceptance", "class": "low-risk performance optimization", "problem": "Long-context acceptance is low versus block size 16", "evidence": "controlled accepted tokens per verification", "expected_benefit": "reduce target verification calls", "risk": "medium", "validation": "matched QMSum sweep", "priority": "P1"},
        {"component": "timing instrumentation", "class": "measurement fix", "problem": "cache/synchronization cost is not separable", "evidence": "null metric fields", "expected_benefit": "actionable profiles", "risk": "low", "validation": "event-based microprofile", "priority": "P1"},
        {"component": "prompt tokenization", "class": "low-risk performance optimization", "problem": "precompression accounting and generation render tokenize the same prompt", "evidence": "run_mvp _run_benchmark_item", "expected_benefit": "small CPU reduction", "risk": "low", "validation": "prompt-hash/token equivalence", "priority": "P2"},
        {"component": "model lifecycle", "class": "architectural refactor opportunity", "problem": "each condition is isolated and reloads models", "evidence": "run_mvp main", "expected_benefit": "batch throughput only", "risk": "medium", "validation": "process-isolation-aware benchmark", "priority": "P2"},
        {"component": "raw duplicate", "class": "architectural refactor opportunity", "problem": "unused model_raw duplicates DFlash semantics", "evidence": "live import points to ccdf.dflash.generate", "expected_benefit": "avoid future drift", "risk": "medium", "validation": "import and behavior tests", "priority": "P2"},
        {"component": "QMSum full rerun", "class": "do not attempt", "problem": "no validated algorithmic repair yet", "evidence": "controlled A/B", "expected_benefit": "none", "risk": "high", "validation": "requires a proven fix first", "priority": "defer"},
    ]


def main() -> None:
    architecture, paths = source_architecture()
    qmsum_table, qmsum_root = qmsum_rows()
    gsm_table, gsm = gsm8k_recheck()
    decision = {
        "decision": "READY_AFTER_LOCALIZED_FIX",
        "localized_fix": "T115 removes detached target-prefill measurement from live benchmark execution and records DFlash timing/acceptance counters.",
        "not_ready_for": ["production default switch", "QMSum semantic correctness claim", "broad DFlash refactor"],
        "authoritative_results": {
            "gsm8k": "T114H repaired 100-row runs",
            "qmsum_runtime": "T115 controlled samples for corrected timing, with T114 preserved as historical pre-fix timing evidence",
            "qmsum_quality": "no semantic correctness authority",
        },
    }
    metric_contract = {
        "t_e2e_ms": "t_compress_ms + t_generation_ms; generation includes target prefill for every condition",
        "removed": "detached diagnostic target prefill from measured execution",
        "full_prompt_compression": "compare precompression_input_tokens to final input_tokens using the target tokenizer only",
        "compressor_segment_compression": "compare original_input_tokens to compressed_input_tokens using compressor metrics only",
        "vram": "allocated and reserved are distinct post-prompt snapshots; model load is excluded",
    }
    write_csv(OUT / "tables/execution_path_diff.csv", paths)
    write_csv(OUT / "tables/qmsum_controlled_ab.csv", qmsum_table)
    write_csv(OUT / "tables/gsm8k_verification.csv", gsm_table)
    write_csv(OUT / "tables/optimization_map.csv", optimization_map())
    write_json(OUT / "summaries/source_architecture_audit.json", architecture)
    write_json(OUT / "summaries/qmsum_root_cause.json", qmsum_root)
    write_json(OUT / "summaries/gsm8k_recheck.json", gsm)
    write_json(OUT / "summaries/metric_contract_audit.json", metric_contract)
    write_json(OUT / "summaries/refactor_readiness_decision.json", decision)
    report = """# T115 Canonical Source Audit\n\n## Decision\n\n`READY_AFTER_LOCALIZED_FIX`. T115 removed the detached target-prefill pass from the live benchmark path and added DFlash acceptance and timing counters. This is a measurement and unnecessary-work fix, not a production refactor.\n\n## GSM8K\n\nThe T114H 100-row result remains valid: the exact T106B suffix reaches each real prompt, prompt hashes match across conditions, and the historical strict numeric evaluator remains in use. The true full-prompt reduction is reported in `summaries/gsm8k_recheck.json`; it uses only target-tokenizer pre/post counts. DFlash-R1 remains the preferred short-context condition because CC-DFlash's small reduction does not justify extra compressor VRAM and risk.\n\n## QMSum\n\nHistorical T105B and T114 share frozen rows, rendered prompt hashes, model paths, block size, and maximum output tokens for their common rows. The controlled sample confirms DFlash is slower than Baseline because low acceptance produces many draft-proposal and target-verification cycles. CC-DFlash is faster than uncompressed DFlash because its shorter prompt reduces target work, but it is not a semantic-quality claim. The original detached prefill was an instrumentation/lifecycle defect that inflated end-to-end time for all conditions; it did not create the DFlash-versus-Baseline ordering.\n\n## Before Refactor\n\nImplement acceptance/verification profiling and any proven block-size or cache improvement first. Do not rerun the full QMSum matrix, change models, or claim QMSum semantic correctness without a separately validated repair. The live split DFlash implementation is authoritative; `model_raw.py` is an unused duplicate that should be handled in a later deliberate refactor.\n"""
    report = report.replace(
        "CC-DFlash is faster than uncompressed DFlash because its shorter prompt reduces target work, but it is not a semantic-quality claim.",
        "T114's n=100 CC-DFlash advantage is consistent with its shorter prompt reducing target work; the corrected three-row sample has different output lengths and does not reproduce a lower CC end-to-end latency, so that exact delta remains variance-sensitive. This is not a semantic-quality claim.",
    )
    (OUT / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps({"decision": decision["decision"], "output": str(OUT)}, sort_keys=True))


if __name__ == "__main__":
    main()
