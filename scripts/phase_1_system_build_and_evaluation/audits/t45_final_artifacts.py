from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_task31_answer_quality import ScorerCategory, score_row


FINAL_ARTIFACTS = {
    "Baseline-AR": Path("results/task45_final_baseline_ar_n100.jsonl"),
    "DFlash-R1": Path("results/task45_final_dflash_r1_n100.jsonl"),
    "LLMLingua-AR-R2": Path("results/task45_final_llmlingua_ar_r2_n100.jsonl"),
    "CC-LLM-R2": Path("results/task45_final_cc_llm_r2_n100.jsonl"),
}

FINAL_LOGS = {
    "LLMLingua-AR-R2": Path("logs/task45_final_llmlingua_ar_r2_n100_2026-06-06_10-21-49.log"),
    "CC-LLM-R2": Path("logs/task45_final_cc_llm_r2_n100_2026-06-06_11-02-41.log"),
}

SUPERSEDED_FAILED_LOG = Path("logs/task45_final_llmlingua_ar_r2_n100_2026-06-06_00-46-05.log")

AR_CONDITIONS = {"Baseline-AR", "LLMLingua-AR-R2"}
SPECULATIVE_CONDITIONS = {"DFlash-R1", "CC-LLM-R2"}
COMPRESSED_CONDITIONS = {"LLMLingua-AR-R2", "CC-LLM-R2"}
PROTOCOL_CONDITIONS = {"LLMLingua-AR-R2", "CC-LLM-R2"}
LEGACY_ACCEPTED_CONDITIONS = {"Baseline-AR", "DFlash-R1"}
BAD_LOG_NEEDLES = [
    "sequence length is longer",
    "traceback",
    "runtimeerror",
    "indexerror",
    "out of memory",
]


@dataclass
class ArtifactAudit:
    condition: str
    path: Path
    rows: list[dict[str, Any]] = field(default_factory=list)
    schema_issues: list[str] = field(default_factory=list)
    schema_warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    protocol: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        return "FAIL" if self.schema_issues else "PASS"


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    if not path.exists():
        return rows, [f"missing artifact: {path}"]
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"line {line_number}: invalid JSON ({exc})")
            continue
        if not isinstance(row, dict):
            issues.append(f"line {line_number}: row is not a JSON object")
            continue
        rows.append(row)
    return rows, issues


def _number(row: dict[str, Any], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _numeric_values(rows: list[dict[str, Any]], *names: str) -> list[float]:
    values = []
    for row in rows:
        value = _number(row, *names)
        if value is not None:
            values.append(value)
    return values


def _avg(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _require_field(audit: ArtifactAudit, row: dict[str, Any], row_index: int, field_name: str) -> None:
    if field_name not in row:
        audit.schema_issues.append(f"row {row_index}: missing `{field_name}`")


def _require_numeric(
    audit: ArtifactAudit,
    row: dict[str, Any],
    row_index: int,
    field_name: str,
    *,
    alias: str | None = None,
    minimum: float | None = None,
    strict: bool = False,
) -> None:
    names = (field_name, alias) if alias else (field_name,)
    value = _number(row, *[name for name in names if name])
    if value is None:
        label = f"`{field_name}`" + (f" or `{alias}`" if alias else "")
        audit.schema_issues.append(f"row {row_index}: missing numeric {label}")
        return
    if minimum is None:
        return
    if strict and value <= minimum:
        audit.schema_issues.append(f"row {row_index}: `{field_name}` must be > {minimum:g}")
    elif not strict and value < minimum:
        audit.schema_issues.append(f"row {row_index}: `{field_name}` must be >= {minimum:g}")


def _validate_common(audit: ArtifactAudit) -> None:
    if len(audit.rows) != 100:
        audit.schema_issues.append(f"expected 100 rows, found {len(audit.rows)}")

    for row_index, row in enumerate(audit.rows, start=1):
        if row.get("condition") != audit.condition:
            audit.schema_issues.append(
                f"row {row_index}: condition {row.get('condition')!r} != {audit.condition!r}"
            )
        for field_name in ["condition", "input_tokens", "output_tokens", "generation_time_s", "tau_mean", "t_prefill_ms"]:
            _require_field(audit, row, row_index, field_name)
        _require_numeric(audit, row, row_index, "input_tokens", minimum=0, strict=True)
        _require_numeric(audit, row, row_index, "output_tokens", minimum=0)
        _require_numeric(audit, row, row_index, "generation_time_s", minimum=0)
        _require_numeric(audit, row, row_index, "tokens_per_second", alias="tok_per_sec", minimum=0)
        _require_numeric(audit, row, row_index, "tau_mean", minimum=0)
        _require_numeric(audit, row, row_index, "t_prefill_ms", minimum=0)

        if "generated_text" not in row or not isinstance(row.get("generated_text"), str):
            audit.schema_issues.append(f"row {row_index}: missing string `generated_text`")
        if not isinstance(row.get("acceptance_lengths"), list):
            audit.schema_issues.append(f"row {row_index}: `acceptance_lengths` must be a list")


def _validate_condition(audit: ArtifactAudit) -> None:
    for row_index, row in enumerate(audit.rows, start=1):
        acceptance_lengths = row.get("acceptance_lengths")
        tau_mean = _number(row, "tau_mean")
        output_tokens = _number(row, "output_tokens") or 0.0

        if audit.condition in AR_CONDITIONS:
            if acceptance_lengths != []:
                audit.schema_issues.append(f"row {row_index}: AR condition must have empty acceptance_lengths")
            if tau_mean != 0.0:
                audit.schema_issues.append(f"row {row_index}: AR condition must have tau_mean == 0.0")

        if audit.condition in SPECULATIVE_CONDITIONS:
            if output_tokens > 0 and not acceptance_lengths:
                audit.schema_issues.append(
                    f"row {row_index}: speculative condition with output tokens must have non-empty acceptance_lengths"
                )
            if tau_mean is not None and tau_mean <= 0:
                audit.schema_issues.append(f"row {row_index}: speculative condition must have tau_mean > 0")

        if audit.condition in COMPRESSED_CONDITIONS:
            for field_name in [
                "compression",
                "t_compress_ms",
                "compressor_chunking_mode",
                "compressor_chunk_token_budget",
                "compressor_chunk_max_observed_tokens",
                "compressor_chunk_encoder_max_length",
            ]:
                _require_field(audit, row, row_index, field_name)
            _require_numeric(audit, row, row_index, "t_compress_ms", minimum=0)
            _require_numeric(audit, row, row_index, "R_actual", alias="r_actual", minimum=1)
            for field_name in [
                "compressor_chunk_token_budget",
                "compressor_chunk_max_observed_tokens",
                "compressor_chunk_encoder_max_length",
            ]:
                _require_numeric(audit, row, row_index, field_name, minimum=0, strict=True)


def _validate_protocol(audit: ArtifactAudit) -> None:
    if audit.condition in LEGACY_ACCEPTED_CONDITIONS:
        if any("benchmark_protocol_version" in row for row in audit.rows):
            audit.schema_warnings.append("legacy artifact unexpectedly contains some protocol metadata")
        else:
            audit.schema_warnings.append(
                "legacy final artifact schema accepted because generated before runner protocol fix"
            )
        audit.protocol = {
            "status": "LEGACY_ACCEPTED",
            "expected_protocol": None,
            "note": "Generated before per-prompt JSONL protocol fix; missing protocol metadata is not a failure.",
        }
        return

    indexes: list[int] = []
    for row_index, row in enumerate(audit.rows, start=1):
        if row.get("benchmark_protocol_version") != "per_prompt_jsonl_v1":
            audit.schema_issues.append(f"row {row_index}: benchmark_protocol_version must be per_prompt_jsonl_v1")
        if row.get("is_warmup") is not False:
            audit.schema_issues.append(f"row {row_index}: is_warmup must be false")
        if row.get("warmup_prompts") != 1:
            audit.schema_issues.append(f"row {row_index}: warmup_prompts must be 1")
        index = row.get("benchmark_prompt_index")
        if isinstance(index, int) and not isinstance(index, bool):
            indexes.append(index)
        else:
            audit.schema_issues.append(f"row {row_index}: benchmark_prompt_index must be an integer")

    expected = list(range(1, 101))
    if sorted(indexes) != expected:
        audit.schema_issues.append("benchmark_prompt_index must cover 1..100 without duplicates")

    audit.protocol = {
        "status": "PASS" if not audit.schema_issues else "FAIL",
        "expected_protocol": "per_prompt_jsonl_v1",
        "index_min": min(indexes) if indexes else None,
        "index_max": max(indexes) if indexes else None,
        "unique_indexes": len(set(indexes)),
        "warmup_prompts": sorted({row.get("warmup_prompts") for row in audit.rows}),
    }


def _summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tok_s = _numeric_values(rows, "tokens_per_second", "tok_per_sec")
    tau = _numeric_values(rows, "tau_mean")
    t_prefill = _numeric_values(rows, "t_prefill_ms")
    t_compress = _numeric_values(rows, "t_compress_ms")
    r_actual = _numeric_values(rows, "R_actual", "r_actual")
    input_tokens = _numeric_values(rows, "input_tokens")
    output_tokens = _numeric_values(rows, "output_tokens")
    vram_allocated = _numeric_values(rows, "vram_allocated_gib")
    vram_reserved = _numeric_values(rows, "vram_reserved_gib")

    return {
        "rows": len(rows),
        "avg_tokens_per_second": _avg(tok_s),
        "median_tokens_per_second": _median(tok_s),
        "avg_tau_mean": _avg(tau),
        "median_tau_mean": _median(tau),
        "avg_t_prefill_ms": _avg(t_prefill),
        "avg_t_compress_ms": _avg(t_compress),
        "avg_R_actual": _avg(r_actual),
        "max_vram_allocated_gib": _max(vram_allocated),
        "max_vram_reserved_gib": _max(vram_reserved),
        "avg_input_tokens": _avg(input_tokens),
        "avg_output_tokens": _avg(output_tokens),
    }


def _summarize_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [score_row(row) for row in rows]
    generated_text_present = sum(score.generated_text_present for score in scores)
    exact = sum(score.category is ScorerCategory.EXACT_CONTAINMENT for score in scores)
    normalized = sum(score.category is ScorerCategory.NORMALIZED_CONTAINMENT for score in scores)
    no_containment = sum(score.category is ScorerCategory.NO_CONTAINMENT for score in scores)
    not_evaluable = sum(score.category is ScorerCategory.NOT_EVALUABLE for score in scores)
    extracted = sum(score.extracted_answer_match for score in scores)
    denominator = len(rows) or 1
    return {
        "generated_text_present": generated_text_present,
        "exact_containment_count": exact,
        "normalized_containment_count": normalized,
        "no_containment_count": no_containment,
        "not_evaluable_count": not_evaluable,
        "extracted_answer_match_count": extracted,
        "exact_containment_rate": exact / denominator,
        "normalized_containment_rate": (exact + normalized) / denominator,
        "extracted_answer_match_rate": extracted / denominator,
        "policy": "Extraction-aware numeric answer match is diagnostic for this audit; final correctness claims require the dedicated Task 46 analysis/report.",
    }


def audit_artifact(condition: str, path: Path) -> ArtifactAudit:
    rows, parse_issues = _load_jsonl(path)
    audit = ArtifactAudit(condition=condition, path=path, rows=rows)
    audit.schema_issues.extend(parse_issues)
    if parse_issues:
        return audit
    _validate_common(audit)
    _validate_condition(audit)
    _validate_protocol(audit)
    audit.metrics = _summarize_metrics(rows)
    audit.quality = _summarize_quality(rows)
    return audit


def audit_logs() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for condition, path in FINAL_LOGS.items():
        issues = []
        if not path.exists():
            issues.append(f"missing log: {path}")
            text = ""
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            if "Final status: PASS" not in text:
                issues.append("missing `Final status: PASS`")
            lower_text = text.lower()
            for needle in BAD_LOG_NEEDLES:
                if needle in lower_text:
                    issues.append(f"log contains `{needle}`")
        results[condition] = {
            "path": str(path),
            "status": "FAIL" if issues else "PASS",
            "issues": issues,
        }

    old_log_note = {
        "path": str(SUPERSEDED_FAILED_LOG),
        "exists": SUPERSEDED_FAILED_LOG.exists(),
        "classification": "SUPERSEDED_FAILED_ATTEMPT",
        "note": "Historical LLMLingua n=100 failed attempt; superseded by later PASS log.",
    }
    if SUPERSEDED_FAILED_LOG.exists():
        old_text = SUPERSEDED_FAILED_LOG.read_text(encoding="utf-8", errors="replace").lower()
        old_log_note["contains_sequence_length_warning"] = "sequence length is longer" in old_text
    results["superseded_failed_llmlingua_log"] = old_log_note
    return results


def run_audit() -> dict[str, Any]:
    artifacts = {
        condition: audit_artifact(condition, path)
        for condition, path in FINAL_ARTIFACTS.items()
    }
    log_results = audit_logs()
    artifact_summaries = {
        condition: {
            "path": str(audit.path),
            "status": audit.status,
            "row_count": len(audit.rows),
            "schema_issues": audit.schema_issues,
            "schema_warnings": audit.schema_warnings,
            "protocol": audit.protocol,
            "metrics": audit.metrics,
            "quality": audit.quality,
        }
        for condition, audit in artifacts.items()
    }
    all_artifact_pass = all(audit.status == "PASS" for audit in artifacts.values())
    all_logs_pass = all(
        result.get("status") == "PASS"
        for key, result in log_results.items()
        if key != "superseded_failed_llmlingua_log"
    )
    status = "PASS" if all_artifact_pass and all_logs_pass else "FAIL"
    return {
        "task": "45-final-artifact-audit",
        "status": status,
        "artifact_paths": {condition: str(path) for condition, path in FINAL_ARTIFACTS.items()},
        "total_rows": sum(len(audit.rows) for audit in artifacts.values()),
        "artifacts": artifact_summaries,
        "logs": log_results,
        "notes": [
            "Baseline-AR and DFlash-R1 use a legacy final artifact schema and are accepted because they were generated before the runner protocol fix.",
            "LLMLingua-AR-R2 and CC-LLM-R2 use per_prompt_jsonl_v1 protocol metadata.",
            "The older LLMLingua sequence-length warning log is historical and superseded by the later PASS log.",
            "Metrics are audited Task 45 measurements, not deployment or final paper claims.",
        ],
    }


def write_summary(summary: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    print(f"status: {summary['status']}")
    print(f"total_rows: {summary['total_rows']}")
    for condition, artifact in summary["artifacts"].items():
        metrics = artifact["metrics"]
        quality = artifact["quality"]
        print(
            f"{condition}: status={artifact['status']} rows={artifact['row_count']} "
            f"avg_tok_s={metrics.get('avg_tokens_per_second'):.2f} "
            f"median_tok_s={metrics.get('median_tokens_per_second'):.2f} "
            f"avg_tau={metrics.get('avg_tau_mean'):.2f} "
            f"avg_prefill_ms={metrics.get('avg_t_prefill_ms'):.2f} "
            f"exact={quality.get('exact_containment_count')} "
            f"extracted={quality.get('extracted_answer_match_count')}"
        )
        for issue in artifact["schema_issues"]:
            print(f"  FAIL: {issue}")
        for warning in artifact["schema_warnings"]:
            print(f"  WARN: {warning}")
    for condition, log_result in summary["logs"].items():
        if condition == "superseded_failed_llmlingua_log":
            print(f"{condition}: {log_result['classification']} exists={log_result['exists']}")
            continue
        print(f"{condition} log: {log_result['status']}")
        for issue in log_result["issues"]:
            print(f"  FAIL: {issue}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Task 45 final n=100 artifacts and logs")
    parser.add_argument(
        "--output",
        default="results/task45_final_artifact_audit_summary.json",
        help="Summary JSON output path",
    )
    args = parser.parse_args()

    summary = run_audit()
    write_summary(summary, Path(args.output))
    print_summary(summary)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
