from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102d_qmsum_evaluator_proxy_improvement as t102d


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _qmsum_row(
    fixture_id: str,
    *,
    generated_text: str,
    expected_answer: str,
    source: str = "brand colour battery microphone evidence design decision",
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "generated_text": generated_text,
        "expected_answer": expected_answer,
        "compressed_prompt_preview": source,
        "original_prompt_preview": source,
        "final_prompt_tail_preview": "Why did the team choose the design? Answer only the question using the meeting context.",
        "t_compress_ms": 120.0,
        "generation_time_s": 5.0,
        "tokens_per_second": 20.0,
        "tau_mean": 2.0,
        "output_tokens": len(generated_text.split()),
    }


def _label_row(
    fixture_id: str,
    *,
    reference_recall: float,
    source_overlap: float,
    question: str = "why did the team choose the design",
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "labels": {
            "completed_answer": True,
            "empty_or_malformed": False,
            "cap_limited_or_incomplete": False,
            "low_reference_overlap": True,
            "proxy_uncertain": True,
            "source_reference_mismatch_possible": True,
            "possible_evidence_miss": False,
            "too_short_or_generic": False,
        },
        "metrics": {
            "reference_unigram_recall": reference_recall,
            "reference_bigram_recall": 0.0,
            "output_source_keyword_overlap": source_overlap,
            "output_token_count": 80.0,
            "t_compress_ms": 120.0,
            "e2e_time_s": 5.0,
            "tokens_per_second": 20.0,
            "tau_mean": 2.0,
        },
        "previews": {
            "question": question,
            "expected_answer": "reference answer",
            "generated_text": "generated answer",
            "generated_tail": "generated answer",
        },
    }


def test_normalized_content_overlap_handles_case_punctuation_and_simple_suffixes() -> None:
    score = t102d.content_recall(
        "The designers discussed batteries, branded colours, and cheaper manufacturing.",
        "A designer discusses battery color and manufacturing cost.",
    )

    assert score >= 0.60


def test_analyzer_reassesses_rows_and_writes_expected_outputs(tmp_path: Path) -> None:
    qmsum = tmp_path / "qmsum.jsonl"
    labels = tmp_path / "labels.jsonl"
    t102c = tmp_path / "t102c.jsonl"
    out = tmp_path / "out"
    q_rows = [
        _qmsum_row(
            "source",
            generated_text="The team chose the branded controller design because the meeting evidence supported it.",
            expected_answer="The reference emphasized manufacturing cost and retail packaging.",
            source="team chose branded colour design evidence",
        ),
        _qmsum_row(
            "hard",
            generated_text="The team discussed an unrelated agenda and lunch plan.",
            expected_answer="The battery solved remote charging constraints.",
            source="battery solved remote charging constraints",
        ),
        _qmsum_row(
            "unresolved",
            generated_text="The team made a decision.",
            expected_answer="A detailed reference is unavailable.",
            source="",
        ),
    ]
    l_rows = [
        _label_row("source", reference_recall=0.12, source_overlap=0.18),
        _label_row("hard", reference_recall=0.02, source_overlap=0.02),
        _label_row("unresolved", reference_recall=0.08, source_overlap=0.0),
    ]
    c_rows = [
        {"fixture_id": "source", "primary_bucket": "source_reference_mismatch_possible"},
        {"fixture_id": "hard", "primary_bucket": "evidence_miss_likely"},
        {"fixture_id": "unresolved", "primary_bucket": "unresolved_proxy_limitation"},
    ]
    _write_jsonl(qmsum, q_rows)
    _write_jsonl(labels, l_rows)
    _write_jsonl(t102c, c_rows)

    result = t102d.analyze(qmsum_jsonl=qmsum, row_labels=labels, t102c_triage=t102c, output_dir=out)

    assert result["summary"]["before"]["proxy_uncertain_rows"] == 3
    assert result["summary"]["after"]["remaining_unexplained_uncertain_rows"] == 1
    assert result["summary"]["after"]["hard_risk_rows"] == 1
    assert result["summary"]["after"]["confidence_band_counts"]["source_grounded_reference_mismatch"] == 1
    for relative in t102d.OUTPUT_RELATIVE_PATHS:
        assert (out / relative).exists()


def test_decision_escalates_when_uncertainty_remains_near_original() -> None:
    summary = {
        "before": {"proxy_uncertain_rows": 18},
        "after": {
            "remaining_unexplained_uncertain_rows": 16,
            "hard_risk_rows": 3,
            "unresolved_rows": 4,
            "materially_reduced": False,
        },
    }

    decision = t102d.build_next_task_decision(summary)

    assert decision["next_task"] == "T102E — QMSum Manual Reference Alignment / Proxy Escalation"
    assert decision["decision"] == "ESCALATE_TO_T102E"


def test_claim_update_preserves_no_semantic_correctness_claim() -> None:
    summary = {
        "before": {"proxy_uncertain_rows": 18},
        "after": {
            "remaining_unexplained_uncertain_rows": 4,
            "hard_risk_rows": 5,
            "unresolved_rows": 0,
            "materially_reduced": True,
        },
    }

    claim = t102d.build_claim_update(summary)

    assert claim["QMSum claim"]["status"] == "SCOPED_WITH_IMPROVED_PROXY_CAVEAT"
    assert "QMSum semantic correctness is proven." in claim["QMSum claim"]["blocked_wording"]
    assert "No LLM judge or human semantic scoring was used." in claim["QMSum claim"]["limitations"]


def test_no_model_loading_in_task102d_analyzer() -> None:
    source = inspect.getsource(t102d)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
