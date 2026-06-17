from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_task31_answer_quality import (
    extract_final_numeric_answer,
    load_jsonl,
    score_row,
)


DEFAULT_ARTIFACTS = [
    Path("results/phase_1_system_build_and_evaluation/early_experiments/task43_dflash_r1_sample_n5.jsonl"),
    Path("results/phase_1_system_build_and_evaluation/early_experiments/task43_llmlingua_ar_r2_sample_n5.jsonl"),
    Path("results/phase_1_system_build_and_evaluation/early_experiments/task43_cc_llm_r2_sample_n5.jsonl"),
]


def _mean(values: list[float]) -> float | None:
    return statistics.mean(values) if values else None


def _snippet(text: str, limit: int = 220) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 3] + "..."


def _looks_like_reasoning(text: str) -> bool:
    lowered = text.lower()
    markers = [
        "step",
        "let's",
        "to solve",
        "calculate",
        "first",
        "therefore",
        "we need",
    ]
    return any(marker in lowered for marker in markers)


def inspect_artifact(path: Path) -> dict[str, Any]:
    rows = load_jsonl(path)
    row_summaries: list[dict[str, Any]] = []
    generated_lengths: list[float] = []
    generated_token_counts: list[float] = []
    truncated_count = 0
    containment_count = 0
    extracted_match_count = 0
    final_answer_anywhere_count = 0
    reasoning_without_answer_count = 0

    for index, row in enumerate(rows, start=1):
        generated_text = row.get("generated_text") if isinstance(row.get("generated_text"), str) else ""
        score = score_row(row)
        max_new_tokens = int(row.get("max_new_tokens", 0) or 0)
        output_tokens = int(row.get("output_tokens", 0) or 0)
        generated_token_count = int(row.get("generated_token_count", output_tokens) or 0)
        appears_truncated = max_new_tokens > 0 and output_tokens >= max_new_tokens
        has_containment = score.exact_match or score.normalized_match
        final_answer_anywhere = has_containment or score.extracted_answer_match
        reasoning_without_answer = bool(generated_text) and _looks_like_reasoning(generated_text) and not final_answer_anywhere

        generated_lengths.append(float(len(generated_text)))
        generated_token_counts.append(float(generated_token_count))
        truncated_count += int(appears_truncated)
        containment_count += int(has_containment)
        extracted_match_count += int(score.extracted_answer_match)
        final_answer_anywhere_count += int(final_answer_anywhere)
        reasoning_without_answer_count += int(reasoning_without_answer)

        row_summaries.append(
            {
                "row_index": index,
                "condition": row.get("condition"),
                "prompt_id": row.get("prompt_id"),
                "fixture_id": row.get("fixture_id"),
                "expected_answer": row.get("expected_answer"),
                "output_tokens": output_tokens,
                "max_new_tokens": max_new_tokens,
                "generated_text_chars": len(generated_text),
                "generated_token_count": generated_token_count,
                "appears_truncated": appears_truncated,
                "containment_match": has_containment,
                "extracted_answer": score.extracted_answer,
                "expected_extracted_answer": score.expected_extracted_answer,
                "extracted_answer_match": score.extracted_answer_match,
                "final_answer_anywhere": final_answer_anywhere,
                "reasoning_without_answer": reasoning_without_answer,
                "snippet": _snippet(generated_text),
            }
        )

    return {
        "artifact": str(path),
        "rows": len(rows),
        "condition": rows[0].get("condition") if rows else None,
        "avg_generated_text_chars": _mean(generated_lengths),
        "avg_generated_token_count": _mean(generated_token_counts),
        "truncated_count": truncated_count,
        "containment_match_count": containment_count,
        "extracted_answer_match_count": extracted_match_count,
        "final_answer_anywhere_count": final_answer_anywhere_count,
        "reasoning_without_answer_count": reasoning_without_answer_count,
        "row_summaries": row_summaries,
    }


def inspect_artifacts(paths: list[Path]) -> dict[str, Any]:
    artifacts = [inspect_artifact(path) for path in paths]
    return {
        "inspection_policy": {
            "appears_truncated": "output_tokens >= max_new_tokens",
            "containment_match": "expected answer appears in generated text exactly or after normalization",
            "extracted_answer_match": "numeric final answer extractor matches expected numeric answer",
            "reasoning_without_answer": "reasoning markers are present but no containment or extracted-answer match was found",
        },
        "artifacts": artifacts,
    }


def write_summary(summary: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def print_summary(summary: dict[str, Any]) -> None:
    for artifact in summary["artifacts"]:
        print(
            f"{artifact['condition']}: rows={artifact['rows']} "
            f"truncated={artifact['truncated_count']} "
            f"containment={artifact['containment_match_count']} "
            f"extracted={artifact['extracted_answer_match_count']} "
            f"final_anywhere={artifact['final_answer_anywhere_count']} "
            f"reasoning_without_answer={artifact['reasoning_without_answer_count']} "
            f"avg_chars={artifact['avg_generated_text_chars']:.1f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Task 43 generated-text outputs")
    parser.add_argument("artifacts", nargs="*", help="JSONL artifacts to inspect")
    parser.add_argument("--output", default=None, help="Optional JSON summary output path")
    args = parser.parse_args()

    paths = [Path(path) for path in args.artifacts] if args.artifacts else DEFAULT_ARTIFACTS
    summary = inspect_artifacts(paths)
    if args.output:
        write_summary(summary, Path(args.output))
    print_summary(summary)
    if args.output:
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
