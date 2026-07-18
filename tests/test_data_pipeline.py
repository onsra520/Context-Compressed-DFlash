import json
import io
from pathlib import Path

import pytest

from ccdf.data import DatasetBuildConfig, build_datasets, fetch_sources


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _raw_fixture(root: Path) -> None:
    _write_jsonl(root / "raw/gsm8k/gsm8k_test.jsonl", [
        {"question": "What is 1+1?", "answer": "Add them. #### 2"},
        {"question": "What is 3+4?", "answer": "Add them. #### 7"},
    ])
    _write_jsonl(root / "raw/qmsum/qmsum_test.jsonl", [{
        "meeting_id": "m1", "meeting_transcripts": [{"speaker": "A", "content": "Ada owns the report."}],
        "specific_query_list": [{"query": "Who owns the report?", "answer": "Ada."}],
        "general_query_list": [{"query": "What was discussed?", "answer": "Report ownership."}],
    }])


def test_builds_gsm8k_and_qmsum_with_stable_ids_and_hash_manifest(tmp_path: Path):
    raw = tmp_path / "raw-source"
    _raw_fixture(raw)
    first = build_datasets(DatasetBuildConfig(raw, tmp_path / "out-a", seed=9, sample_size=1, enforce_source_lock=False))
    second = build_datasets(DatasetBuildConfig(raw, tmp_path / "out-b", seed=9, sample_size=1, enforce_source_lock=False))
    assert first == second
    assert first["schema_version"] == "ccdf.data.v2"
    assert first["datasets"]["gsm8k"]["processed_row_count"] == 2
    assert first["datasets"]["qmsum"]["processed_row_count"] == 1
    assert first["datasets"]["gsm8k"]["sample_row_ids"] == second["datasets"]["gsm8k"]["sample_row_ids"]
    row = json.loads((tmp_path / "out-a/processed/qmsum/qmsum_processed.jsonl").read_text().splitlines()[0])
    assert row["split"] == "test"
    assert row["reference_answer"]
    assert row["lineage"]["meeting_id"] == "m1"
    assert row["truncation"] == {
        "boundary": "none",
        "caveat": "",
        "original_words": 4,
        "retained_words": 4,
        "strategy": "full_transcript",
        "truncated": False,
    }
    gsm = json.loads((tmp_path / "out-a/processed/gsm8k/gsm8k_processed.jsonl").read_text().splitlines()[0])
    assert gsm["prompt_parts"]["context"] == ""
    assert "Short-context" not in gsm["prompt"]
    assert len(first["datasets"]["qmsum"]["processed_sha256"]) == 64


def test_fetch_rejects_source_drift(monkeypatch, tmp_path: Path):
    class Response(io.BytesIO):
        headers = {"ETag": '"test"'}

    monkeypatch.setattr(
        "ccdf.data.pipeline.urllib.request.urlopen",
        lambda *args, **kwargs: Response(b"drifted bytes\n"),
    )
    with pytest.raises(ValueError, match="source drift"):
        fetch_sources(tmp_path)
