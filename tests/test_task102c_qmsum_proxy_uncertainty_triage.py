from __future__ import annotations

import inspect
import json
from pathlib import Path

from scripts.phase_2_system_optimization.analysis import task102c_qmsum_proxy_uncertainty_triage as t102c


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _qmsum_row(fixture_id: str, *, generated_text: str, expected_answer: str) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "expected_answer": expected_answer,
        "generated_text": generated_text,
        "final_prompt_tail_preview": "Summarize why the team chose the design. Answer only the question using the meeting context.",
        "compressed_prompt_preview": "team chose design because colour battery microphone evidence",
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
    low_reference_overlap: bool = True,
    proxy_uncertain: bool = True,
    output_tokens: int = 80,
) -> dict[str, object]:
    return {
        "fixture_id": fixture_id,
        "dataset_id": fixture_id,
        "labels": {
            "low_reference_overlap": low_reference_overlap,
            "proxy_uncertain": proxy_uncertain,
            "source_reference_mismatch_possible": low_reference_overlap,
            "possible_evidence_miss": False,
            "too_short_or_generic": False,
        },
        "metrics": {
            "reference_unigram_recall": reference_recall,
            "reference_bigram_recall": 0.02,
            "output_source_keyword_overlap": source_overlap,
            "output_token_count": output_tokens,
            "t_compress_ms": 120.0,
            "e2e_time_s": 5.0,
            "tokens_per_second": 20.0,
            "tau_mean": 2.0,
        },
        "previews": {
            "question": "why did the team choose the design",
            "expected_answer": "reference answer",
            "generated_text": "generated answer",
            "generated_tail": "generated answer",
        },
    }


def test_analyzer_handles_fixture_and_writes_expected_outputs(tmp_path: Path) -> None:
    qmsum = tmp_path / "qmsum.jsonl"
    labels = tmp_path / "labels.jsonl"
    low = tmp_path / "low.jsonl"
    q_rows = [
        _qmsum_row("a", generated_text="The team chose red and yellow because they matched branding.", expected_answer="The colours matched the company branding."),
        _qmsum_row("b", generated_text="The team discussed the general meeting agenda.", expected_answer="The team chose solar battery power for remote users."),
        _qmsum_row("c", generated_text="A brief answer.", expected_answer="The group needed detailed pricing and touchscreen constraints."),
    ]
    l_rows = [
        _label_row("a", reference_recall=0.18, source_overlap=0.20),
        _label_row("b", reference_recall=0.02, source_overlap=0.03),
        _label_row("c", reference_recall=0.10, source_overlap=0.12, output_tokens=3),
    ]
    _write_jsonl(qmsum, q_rows)
    _write_jsonl(labels, l_rows)
    _write_jsonl(low, l_rows)

    result = t102c.analyze(qmsum_jsonl=qmsum, row_labels=labels, low_proxy_rows=low, output_dir=tmp_path / "out")

    assert result["decision"] == "PASS_WITH_CAVEAT"
    assert result["summary"]["uncertain_rows_analyzed"] == 3
    assert result["summary"]["bucket_counts"]["proxy_false_negative"] == 1
    assert result["summary"]["bucket_counts"]["evidence_miss_likely"] == 1
    assert result["summary"]["bucket_counts"]["generic_or_under_specific"] == 1
    for relative in t102c.OUTPUT_RELATIVE_PATHS:
        assert (tmp_path / "out" / relative).exists()


def test_bucket_classifier_covers_required_categories() -> None:
    proxy_false_negative = t102c.triage_row(
        _qmsum_row("p", generated_text="The professor disliked lapel microphones because they captured breath.", expected_answer="Lapel microphones captured breath and non-voice sounds."),
        _label_row("p", reference_recall=0.16, source_overlap=0.22),
    )
    evidence_miss = t102c.triage_row(
        _qmsum_row("e", generated_text="The answer discusses a different agenda.", expected_answer="Solar power helps remote users recharge."),
        _label_row("e", reference_recall=0.02, source_overlap=0.02),
    )
    generic = t102c.triage_row(
        _qmsum_row("g", generated_text="They discussed the meeting topic.", expected_answer="They chose red because it attracted customers."),
        _label_row("g", reference_recall=0.09, source_overlap=0.10, output_tokens=5),
    )
    acceptable = t102c.triage_row(
        _qmsum_row("a", generated_text="The team picked yellow and red for brand identity and customer appeal.", expected_answer="Yellow was company colour and red attracted customers."),
        _label_row("a", reference_recall=0.28, source_overlap=0.18, low_reference_overlap=False),
    )
    unresolved = t102c.triage_row(
        _qmsum_row("u", generated_text="The team made a decision.", expected_answer=""),
        _label_row("u", reference_recall=0.0, source_overlap=0.0),
    )

    assert proxy_false_negative["primary_bucket"] == "proxy_false_negative"
    assert evidence_miss["primary_bucket"] == "evidence_miss_likely"
    assert generic["primary_bucket"] == "generic_or_under_specific"
    assert acceptable["primary_bucket"] == "acceptable_after_proxy_review"
    assert unresolved["primary_bucket"] == "unresolved_proxy_limitation"


def test_claim_update_preserves_blocked_semantic_correctness() -> None:
    summary = {
        "total_rows": 30,
        "uncertain_rows_analyzed": 18,
        "bucket_counts": {
            "proxy_false_negative": 8,
            "source_reference_mismatch_possible": 4,
            "acceptable_after_proxy_review": 3,
            "evidence_miss_likely": 2,
            "generic_or_under_specific": 1,
            "unresolved_proxy_limitation": 0,
        },
        "hard_risk_rows": 3,
        "unresolved_rows": 0,
    }

    claim = t102c.build_claim_update(summary)

    assert claim["QMSum claim"]["status"] == "SCOPED_WITH_TRIAGED_RISK"
    assert "QMSum semantic correctness is proven." in claim["QMSum claim"]["blocked_wording"]
    assert "QMSum quality is fully solved." in claim["QMSum claim"]["blocked_wording"]


def test_next_task_is_t103_when_triage_is_usable() -> None:
    summary = {
        "total_rows": 30,
        "uncertain_rows_analyzed": 18,
        "hard_risk_rows": 6,
        "unresolved_rows": 4,
    }

    decision = t102c.build_next_task_decision(summary)

    assert decision["next_task"] == "T103 — Reference Alignment for Speed Claim"


def test_next_task_can_be_t102a_for_severe_issue() -> None:
    summary = {
        "total_rows": 30,
        "uncertain_rows_analyzed": 18,
        "hard_risk_rows": 18,
        "unresolved_rows": 10,
    }

    decision = t102c.build_next_task_decision(summary)

    assert decision["next_task"] == "T102A — QMSum Failure Audit / Fix"


def test_no_model_loading_in_task102c_analyzer() -> None:
    source = inspect.getsource(t102c)

    assert "transformers" not in source
    assert "import torch" not in source
    assert "from torch" not in source
    assert "AutoModel" not in source
