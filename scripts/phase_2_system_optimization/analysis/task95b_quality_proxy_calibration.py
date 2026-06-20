from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement import (
    classify_row,
    normalize_numeric,
)


DEFAULT_LARGE = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task94_light_vs_large_compressor_controlled_comparison/runs/"
    "20260620_192758_cc_dflash_r2_large_n10.jsonl"
)
DEFAULT_LIGHT = Path(
    "results/phase_2_system_optimization/compressor_comparison/"
    "task94_light_vs_large_compressor_controlled_comparison/runs/"
    "20260620_192904_cc_dflash_r2_light_n10.jsonl"
)
DEFAULT_TASK95A_PAIRS = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95a_analysis_and_failure_row_audit/task95a_failure_row_pairs.jsonl"
)
DEFAULT_OUTPUT_DIR = Path(
    "results/phase_2_system_optimization/quality_and_latency_audits/"
    "task95b_quality_proxy_calibration"
)

ID_KEYS = ("fixture_id", "dataset_id", "sample_id", "id", "question_id")
INDEX_KEYS = ("benchmark_prompt_index", "prompt_id", "dataset_index")
EXPECTED_KEYS = ("expected_answer", "gold_answer", "reference_answer", "ground_truth_answer", "answer")
LABELS = (
    "strict_correct",
    "strict_wrong_numeric",
    "cap_limited_incomplete",
    "format_or_extraction_sensitive",
    "answer_missing",
    "proxy_uncertain",
)
FINAL_MARKER_RE = re.compile(r"(?:final\s+(?:numeric\s+)?answer|####)", re.IGNORECASE)
NUMBER_RE = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} is not a JSON object")
        rows.append(payload)
    return rows


def _first_present(row: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _preview(text: Any, limit: int = 260) -> str:
    if not isinstance(text, str):
        return ""
    compact = " ".join(text.split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def _numbers_in_text(text: Any) -> list[str]:
    if not isinstance(text, str):
        return []
    numbers = []
    for match in NUMBER_RE.finditer(text):
        normalized = normalize_numeric(match.group(0))
        if normalized is not None:
            numbers.append(normalized)
    return numbers


def _expected_appears(expected_answer: Any, generated_text: Any) -> bool:
    expected_numeric = normalize_numeric(expected_answer)
    if expected_numeric is not None:
        return expected_numeric in _numbers_in_text(generated_text)
    return isinstance(expected_answer, str) and isinstance(generated_text, str) and expected_answer in generated_text


def _final_answer_marker_present(generated_text: Any) -> bool:
    return isinstance(generated_text, str) and bool(FINAL_MARKER_RE.search(generated_text))


def _ends_unfinished(generated_text: Any) -> bool:
    if not isinstance(generated_text, str) or not generated_text.strip():
        return False
    stripped = generated_text.rstrip()
    if re.search(r"(?:[=+\-*/÷×(]|\bthe maximum|\bsolving for|\bcalculate the|\bfrom the)$", stripped, re.IGNORECASE):
        return True
    if stripped.endswith((".", "!", "?", ")", "]", "}", '"', "'")):
        return False
    return len(stripped.split()) >= 20


def _cap_limited(row: dict[str, Any], generated_text: Any, classified: dict[str, Any]) -> bool:
    output_tokens = row.get("output_tokens", row.get("generated_token_count"))
    max_new_tokens = row.get("max_new_tokens")
    hit_token_cap = (
        isinstance(output_tokens, (int, float))
        and isinstance(max_new_tokens, (int, float))
        and output_tokens >= max_new_tokens
    )
    return bool(hit_token_cap or classified.get("truncated_or_stopped_early") or _ends_unfinished(generated_text))


def _pair_key_values(rows: list[dict[str, Any]], key: str) -> list[Any] | None:
    values = [row.get(key) for row in rows]
    if any(value in (None, "") for value in values):
        return None
    if len(set(values)) != len(values):
        return None
    return values


def _choose_pairing_key(large_rows: list[dict[str, Any]], light_rows: list[dict[str, Any]]) -> str | None:
    if len(large_rows) != len(light_rows):
        return None
    for key in (*ID_KEYS, *INDEX_KEYS):
        large_values = _pair_key_values(large_rows, key)
        light_values = _pair_key_values(light_rows, key)
        if large_values is not None and light_values is not None and set(large_values) == set(light_values):
            return key
    return None


def pair_rows(large_rows: list[dict[str, Any]], light_rows: list[dict[str, Any]]) -> dict[str, Any]:
    caveats: list[str] = []
    if len(large_rows) != len(light_rows):
        caveats.append(f"row_count_mismatch large={len(large_rows)} light={len(light_rows)}")

    key = _choose_pairing_key(large_rows, light_rows)
    pairs: list[dict[str, Any]] = []
    if key is not None:
        light_by_key = {row[key]: row for row in light_rows}
        for index, large_row in enumerate(large_rows, start=1):
            pair_id = large_row[key]
            pairs.append(
                {
                    "pair_index": index,
                    "pair_id": pair_id,
                    "pairing_key": key,
                    "large_row": large_row,
                    "light_row": light_by_key[pair_id],
                }
            )
        return {"pairing_method": key, "pairs": pairs, "caveats": caveats}

    for index in range(min(len(large_rows), len(light_rows))):
        pairs.append(
            {
                "pair_index": index + 1,
                "pair_id": index + 1,
                "pairing_key": "row_order",
                "large_row": large_rows[index],
                "light_row": light_rows[index],
            }
        )
    caveats.append("paired_by_row_order_no_shared_unique_id")
    return {"pairing_method": "row_order", "pairs": pairs, "caveats": caveats}


def calibrate_row(
    row: dict[str, Any],
    *,
    profile: str,
    row_index: int,
    pair_id: Any | None = None,
    pair_index: int | None = None,
    artifact: Path | str | None = None,
) -> dict[str, Any]:
    expected_answer = _first_present(row, EXPECTED_KEYS)
    generated_text = row.get("generated_text")
    classified = classify_row(
        row,
        row_index=row_index,
        condition=profile,
        artifact=str(artifact or row.get("output_path") or profile),
    )
    expected_numeric = classified.get("expected_numeric")
    strict_extracted_answer = classified.get("extracted_answer")
    raw_strict_correct = bool(classified.get("numeric_match"))
    exact_containment = bool(_expected_appears(expected_answer, generated_text))
    final_marker = _final_answer_marker_present(generated_text)
    cap_limited = _cap_limited(row, generated_text, classified) and not final_marker
    strict_correct = raw_strict_correct and not (cap_limited and not final_marker)
    notes: list[str] = []

    if expected_answer in (None, ""):
        label = "proxy_uncertain"
        notes.append("missing expected_answer")
    elif not isinstance(generated_text, str) or not generated_text.strip():
        label = "answer_missing"
        notes.append("missing generated_text")
    elif cap_limited and not final_marker:
        label = "cap_limited_incomplete"
        notes.append("output appears cap-limited or unfinished; strict correctness remains false")
        if raw_strict_correct:
            notes.append("historical fallback matched expected answer but no final-answer marker was present")
    elif strict_correct:
        label = "strict_correct"
        notes.append("strict numeric extraction matched expected answer")
    elif strict_extracted_answer is not None and exact_containment and not final_marker:
        label = "format_or_extraction_sensitive"
        notes.append("expected answer appears in generated text, but strict extraction selected a different number")
    elif strict_extracted_answer is not None:
        label = "strict_wrong_numeric"
        notes.append("strict numeric extraction produced a different answer")
    elif exact_containment:
        label = "format_or_extraction_sensitive"
        notes.append("expected answer appears, but no usable strict numeric answer was extracted")
    else:
        label = "answer_missing"
        notes.append("no usable numeric answer was extracted")

    if classified.get("failure_type") == "parse_ambiguous" and label != "strict_correct":
        label = "proxy_uncertain"
        notes.append("strict extractor marked the row ambiguous")

    return {
        "pair_id": pair_id if pair_id is not None else row.get("fixture_id") or row.get("dataset_id") or row_index,
        "pair_index": pair_index if pair_index is not None else row_index,
        "row_index": row_index,
        "fixture_id": row.get("fixture_id"),
        "dataset_id": row.get("dataset_id"),
        "prompt_id": row.get("prompt_id", row.get("benchmark_prompt_index")),
        "profile": profile,
        "expected_answer": "" if expected_answer is None else str(expected_answer),
        "expected_numeric": expected_numeric,
        "generated_text_preview": _preview(generated_text),
        "strict_extracted_answer": strict_extracted_answer,
        "strict_extraction_source": classified.get("extraction_source"),
        "strict_candidate_answers": classified.get("candidate_answers", []),
        "historical_task47_strict_correct": raw_strict_correct,
        "strict_correct": strict_correct,
        "calibrated_label": label,
        "cap_limited": cap_limited,
        "final_answer_marker_present": final_marker,
        "exact_containment": exact_containment,
        "output_tokens": row.get("output_tokens", row.get("generated_token_count")),
        "max_new_tokens": row.get("max_new_tokens"),
        "notes": notes,
        "source_artifact": str(artifact or row.get("output_path") or ""),
    }


def _rate(count: int, total: int) -> float:
    return round(count / total, 6) if total else 0.0


def _summarize_profile(labels: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(labels)
    label_counts = Counter(row["calibrated_label"] for row in labels)
    for label in LABELS:
        label_counts.setdefault(label, 0)
    strict_correct_count = sum(1 for row in labels if row["strict_correct"])
    historical_strict_correct_count = sum(1 for row in labels if row["historical_task47_strict_correct"])
    return {
        "rows": total,
        "historical_task47_strict_correct_count": historical_strict_correct_count,
        "historical_task47_strict_correct_rate": _rate(historical_strict_correct_count, total),
        "strict_correct_count": strict_correct_count,
        "strict_correct_rate": _rate(strict_correct_count, total),
        "calibrated_label_counts": dict(label_counts),
        "cap_limited_count": sum(1 for row in labels if row["cap_limited"]),
        "final_answer_marker_present_count": sum(1 for row in labels if row["final_answer_marker_present"]),
        "exact_containment_count": sum(1 for row in labels if row["exact_containment"]),
    }


def _policy_rows() -> list[dict[str, str]]:
    return [
        {
            "label": "strict_correct",
            "counted_as_strict_correct": "yes",
            "policy": "Task47 strict numeric extraction matches normalized expected answer.",
        },
        {
            "label": "strict_wrong_numeric",
            "counted_as_strict_correct": "no",
            "policy": "A usable strict numeric answer exists, but it differs from expected.",
        },
        {
            "label": "cap_limited_incomplete",
            "counted_as_strict_correct": "no",
            "policy": "Output appears truncated or unfinished; do not rescue with exact containment or fallback number.",
        },
        {
            "label": "format_or_extraction_sensitive",
            "counted_as_strict_correct": "no",
            "policy": "Expected answer appears plausibly in text, but strict extraction did not produce a match.",
        },
        {
            "label": "answer_missing",
            "counted_as_strict_correct": "no",
            "policy": "No generated text or no usable numeric answer.",
        },
        {
            "label": "proxy_uncertain",
            "counted_as_strict_correct": "no",
            "policy": "Insufficient deterministic evidence to classify safely.",
        },
    ]


def build_recommendation(summary: dict[str, Any]) -> dict[str, Any]:
    large = summary["profiles"]["large"]
    light = summary["profiles"]["light"]
    gap = large["strict_correct_count"] - light["strict_correct_count"]
    light_labels = light["calibrated_label_counts"]
    proxy_uncertain = light_labels.get("proxy_uncertain", 0) + large["calibrated_label_counts"].get("proxy_uncertain", 0)
    light_cap_or_wrong = light_labels.get("cap_limited_incomplete", 0) + light_labels.get("strict_wrong_numeric", 0)
    light_format = light_labels.get("format_or_extraction_sensitive", 0)

    if gap > 0 and light_cap_or_wrong > 0:
        decision = "A"
        next_task = "T95C"
        title = "Proceed to T95C Light Compressor Parameter/Tail Policy Triage"
        rationale = (
            "The strict large-vs-light quality gap remains after calibration, and light has cap-limited "
            "or wrong-numeric rows that calibration does not count as correct."
        )
    elif proxy_uncertain or light_format >= gap > 0:
        decision = "B"
        next_task = "T95C"
        title = "Re-analyze Task94 with calibrated proxy only"
        rationale = (
            "The strict proxy may be partly format-sensitive; use calibrated labels before deciding on larger runs."
        )
    else:
        decision = "C"
        next_task = "T95C"
        title = "Additional bounded sample check"
        rationale = "The bounded n=10 evidence remains too small or mixed for a larger benchmark move."

    return {
        "decision": decision,
        "next_task": next_task,
        "title": title,
        "rationale": rationale,
        "t95c_needed": True,
        "n30_recommended_now": False,
        "proxy_uncertainty_explains_gap": bool(gap > 0 and proxy_uncertain >= gap),
        "strict_quality_gap_large_minus_light": gap,
        "claim_boundary": {
            "deterministic_proxy_analysis_only": True,
            "no_model_inference": True,
            "no_benchmark_run": True,
            "no_llm_judge": True,
            "no_final_quality_claim": True,
            "no_final_speedup_claim": True,
            "no_deployment_or_8gb_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def analyze(
    large_jsonl: Path,
    light_jsonl: Path,
    task95a_pairs_jsonl: Path | None,
    output_dir: Path,
) -> dict[str, Any]:
    large_rows = load_jsonl(large_jsonl)
    light_rows = load_jsonl(light_jsonl)
    paired = pair_rows(large_rows, light_rows)
    labels: list[dict[str, Any]] = []

    for pair in paired["pairs"]:
        labels.append(
            calibrate_row(
                pair["large_row"],
                profile="large",
                row_index=pair["pair_index"],
                pair_id=pair["pair_id"],
                pair_index=pair["pair_index"],
                artifact=large_jsonl,
            )
        )
        labels.append(
            calibrate_row(
                pair["light_row"],
                profile="light",
                row_index=pair["pair_index"],
                pair_id=pair["pair_id"],
                pair_index=pair["pair_index"],
                artifact=light_jsonl,
            )
        )

    labels_by_profile = {
        "large": [row for row in labels if row["profile"] == "large"],
        "light": [row for row in labels if row["profile"] == "light"],
    }
    summary = {
        "task": "Task95B",
        "title": "Quality Proxy Calibration",
        "inputs": {
            "large_jsonl": str(large_jsonl),
            "light_jsonl": str(light_jsonl),
            "task95a_pairs_jsonl": str(task95a_pairs_jsonl) if task95a_pairs_jsonl else None,
        },
        "method": {
            "analysis_only": True,
            "extractor": "scripts.phase_1_system_build_and_evaluation.analysis.t47_quality_refinement.classify_row",
            "strict_policy": "Task47 deterministic numeric extraction remains primary.",
            "exact_containment_policy": "diagnostic_only_not_correctness",
            "pairing_method": paired["pairing_method"],
            "pairing_caveats": paired["caveats"],
            "model_loading": False,
            "benchmark_run": False,
            "llm_judge": False,
        },
        "row_count": {
            "large": len(large_rows),
            "light": len(light_rows),
            "paired": len(paired["pairs"]),
            "labels": len(labels),
        },
        "profiles": {profile: _summarize_profile(rows) for profile, rows in labels_by_profile.items()},
        "examples": {
            "cap_limited_incomplete": [
                row for row in labels if row["calibrated_label"] == "cap_limited_incomplete"
            ][:3],
            "format_or_extraction_sensitive": [
                row for row in labels if row["calibrated_label"] == "format_or_extraction_sensitive"
            ][:3],
        },
        "claim_boundary": {
            "deterministic_proxy_analysis_only": True,
            "no_model_inference": True,
            "no_benchmark_run": True,
            "no_llm_judge": True,
            "no_final_quality_claim": True,
            "no_final_speedup_claim": True,
            "no_deployment_or_8gb_claim": True,
            "no_qmsum_semantic_correctness_claim": True,
        },
    }
    recommendation = build_recommendation(summary)
    summary["recommendation"] = recommendation

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(output_dir / "task95b_calibrated_row_labels.jsonl", labels)
    _write_json(output_dir / "task95b_calibrated_quality_summary.json", summary)
    _write_csv(output_dir / "task95b_proxy_policy_table.csv", _policy_rows())
    _write_json(output_dir / "task95b_recommendation.json", recommendation)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate deterministic Task95B GSM8K quality proxy labels")
    parser.add_argument("--large-jsonl", type=Path, default=DEFAULT_LARGE)
    parser.add_argument("--light-jsonl", type=Path, default=DEFAULT_LIGHT)
    parser.add_argument("--task95a-pairs-jsonl", type=Path, default=DEFAULT_TASK95A_PAIRS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    task95a_pairs = args.task95a_pairs_jsonl if args.task95a_pairs_jsonl and args.task95a_pairs_jsonl.exists() else None
    summary = analyze(args.large_jsonl, args.light_jsonl, task95a_pairs, args.output_dir)
    recommendation = summary["recommendation"]
    large = summary["profiles"]["large"]
    light = summary["profiles"]["light"]
    print("status=PASS")
    print(f"pairing_method={summary['method']['pairing_method']}")
    print(f"strict_large={large['strict_correct_count']}/{large['rows']}")
    print(f"strict_light={light['strict_correct_count']}/{light['rows']}")
    print(f"recommendation={recommendation['next_task']} decision={recommendation['decision']}")
    print(f"wrote={args.output_dir}")


if __name__ == "__main__":
    main()
