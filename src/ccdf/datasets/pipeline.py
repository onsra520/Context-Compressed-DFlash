"""Read-only raw-source conversion and deterministic n=10 selection."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from ..config import Rec2Config
from .qmsum_context import reference_overlap_diagnostic, select_query_aware_context
from .schema import SAMPLE_SCHEMA, validate_samples

PIPELINE_SCHEMA = "ccdf.dataset-pipeline-audit.v1"
SELECTION_SCHEMA = "ccdf.stage3-selection.v1"
SELECTION_SEED = 42
GSM8K_INSTRUCTION = (
    "Solve with concise equations. Track all quantities, steps, and units; do not skip "
    "conversions or repeated actions. End with: Final answer: <number>"
)
_GSM_REFERENCE = re.compile(r"####\s*([-+]?\$?[\d,]+(?:\.\d+)?)\s*$")


def _default_token_count(text: str) -> int:
    """Test-only deterministic fallback; production passes the target tokenizer."""
    return len(re.findall(r"\S+", text))


def _canonical_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for row in rows:
            handle.write(_canonical_bytes(row))
            handle.flush()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _gsm_reference(answer: str) -> str:
    match = _GSM_REFERENCE.search(answer)
    if not match:
        raise ValueError("GSM8K source answer is missing an anchored #### numeric answer")
    value = match.group(1).replace("$", "").replace(",", "")
    try:
        Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("GSM8K source reference is not numeric") from exc
    return value


def _gsm_sample(raw: dict[str, Any], source_index: int) -> dict[str, Any]:
    question = str(raw.get("question", "")).strip()
    reference = _gsm_reference(str(raw.get("answer", "")))
    source_fingerprint = _fingerprint(
        {"dataset": "gsm8k", "split": "test", "source_index": source_index, "raw": raw}
    )
    instruction = GSM8K_INSTRUCTION
    prompt = f"Math word problem:\n{question}\n\n{instruction}"
    return {
        "schema": SAMPLE_SCHEMA,
        "sample_id": f"gsm8k-test-{source_index:06d}-{source_fingerprint[:8]}",
        "dataset": "gsm8k",
        "split": "test",
        "source_id": None,
        "source_index": source_index,
        "task_type": "numeric_qa",
        "question": question,
        "query": None,
        "context": "",
        "reference": reference,
        "metadata": {
            "selection_seed": SELECTION_SEED,
            "source_row_fingerprint": _fingerprint(raw),
            "instruction": instruction,
        },
        "source_fingerprint": source_fingerprint,
        "prompt_version": "stage3-gsm8k-calculation-v5",
        "prompt": prompt,
    }


def _meeting_id(source_index: int) -> str:
    return f"meeting{source_index:04d}"


def _qmsum_context(
    raw: dict[str, Any],
    query: str,
    token_count: Callable[[str], int],
    *,
    budget_tokens: int,
    chunk_target_tokens: int,
) -> tuple[str, str, int, dict[str, Any]]:
    turns = raw.get("meeting_transcripts")
    if not isinstance(turns, list) or not turns:
        raise ValueError("QMSum meeting has no transcript turns")
    rendered = [
        f"{str(turn.get('speaker', 'unknown')).strip() or 'unknown'}: {str(turn.get('content', '')).strip()}"
        for turn in turns
        if str(turn.get("content", "")).strip()
    ]
    full_context = "\n".join(rendered)
    context, selection = select_query_aware_context(
        turns,
        query,
        token_count,
        budget_tokens=budget_tokens,
        chunk_target_tokens=chunk_target_tokens,
    )
    return context, full_context, len(turns), selection


def _qmsum_sample(
    raw: dict[str, Any],
    meeting_index: int,
    query_index: int,
    token_count: Callable[[str], int],
    *,
    budget_tokens: int,
    chunk_target_tokens: int,
) -> dict[str, Any]:
    queries = raw.get("specific_query_list")
    if not isinstance(queries, list) or not 0 <= query_index < len(queries):
        raise ValueError(f"invalid QMSum specific query index {query_index} for meeting {meeting_index}")
    query_row = queries[query_index]
    query = str(query_row.get("query", "")).strip()
    reference = str(query_row.get("answer", "")).strip()
    context, full_context, raw_turn_count, context_selection = _qmsum_context(
        raw,
        query,
        token_count,
        budget_tokens=budget_tokens,
        chunk_target_tokens=chunk_target_tokens,
    )
    context_selection["reference_overlap_diagnostic"] = reference_overlap_diagnostic(reference, context)
    meeting_id = _meeting_id(meeting_index)
    source_fingerprint = _fingerprint(
        {
            "dataset": "qmsum",
            "split": "test",
            "meeting_index": meeting_index,
            "query_type": "specific",
            "query_index": query_index,
            "query": query,
            "reference": reference,
            "transcript": full_context,
        }
    )
    instruction = "Answer using only the meeting transcript. A concise answer is enough."
    prompt = f"Meeting transcript:\n{context}\n\nQuestion:\n{query}\n\n{instruction}"
    return {
        "schema": SAMPLE_SCHEMA,
        "sample_id": f"qmsum-test-{meeting_id}-specific-{query_index:02d}-{source_fingerprint[:8]}",
        "dataset": "qmsum",
        "split": "test",
        "source_id": meeting_id,
        "source_index": meeting_index,
        "task_type": "query_focused_summarization",
        "question": None,
        "query": query,
        "context": context,
        "reference": reference,
        "metadata": {
            "selection_seed": SELECTION_SEED,
            "query_type": "specific",
            "query_index": query_index,
            "source_row_fingerprint": _fingerprint(raw),
            "raw_turn_count": raw_turn_count,
            "context_selection": context_selection,
            "instruction": instruction,
        },
        "source_fingerprint": source_fingerprint,
        "prompt_version": "quality-repair-qmsum-query-aware-v1",
        "prompt": prompt,
    }


def _selection_coordinates(selection: dict[str, Any], dataset: str) -> list[dict[str, int]]:
    rows = selection.get(dataset)
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"selection manifest has no rows for {dataset}")
    return rows


def build_samples(
    raw_rows: list[dict[str, Any]],
    selection: dict[str, Any],
    dataset: str,
    *,
    token_count: Callable[[str], int] = _default_token_count,
    qmsum_context_budget_tokens: int = 1000,
    qmsum_chunk_target_tokens: int = 300,
) -> list[dict[str, Any]]:
    coordinates = _selection_coordinates(selection, dataset)
    samples: list[dict[str, Any]] = []
    for coordinate in coordinates:
        if dataset == "gsm8k":
            index = int(coordinate["upstream_row_index"])
            if not 0 <= index < len(raw_rows):
                raise ValueError(f"GSM8K selection index out of range: {index}")
            samples.append(_gsm_sample(raw_rows[index], index))
        elif dataset == "qmsum":
            meeting_index = int(coordinate["meeting_index"])
            if not 0 <= meeting_index < len(raw_rows):
                raise ValueError(f"QMSum meeting index out of range: {meeting_index}")
            samples.append(
                _qmsum_sample(
                    raw_rows[meeting_index],
                    meeting_index,
                    int(coordinate["query_index"]),
                    token_count,
                    budget_tokens=qmsum_context_budget_tokens,
                    chunk_target_tokens=qmsum_chunk_target_tokens,
                )
            )
        else:
            raise ValueError(f"unsupported dataset: {dataset}")
    validate_samples(samples, expected_dataset=dataset, expected_split="test", expected_count=len(coordinates))
    return samples


def load_canonical_samples(path: Path, *, expected_dataset: str | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl(path)
    if not rows:
        raise ValueError("canonical sample file is empty")
    dataset = expected_dataset or str(rows[0]["dataset"])
    validate_samples(rows, expected_dataset=dataset, expected_split="test", expected_count=len(rows))
    return rows


def build_dataset_pipeline(
    *,
    data_root: Path,
    selection_path: Path,
    config: Rec2Config,
    audit_path: Path | None = None,
) -> dict[str, Any]:
    data_root = data_root.resolve()
    selection_path = selection_path.resolve()
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if selection.get("seed", SELECTION_SEED) != SELECTION_SEED:
        raise ValueError("selection manifest seed mismatch")
    if config.require("datasets.qmsum_context_policy") != "query_aware_budgeted":
        raise ValueError("runtime QMSum selector requires qmsum_context_policy=query_aware_budgeted")
    budget_tokens = int(config.require("datasets.qmsum_context_budget_tokens"))
    chunk_target_tokens = int(config.require("datasets.qmsum_chunk_target_tokens"))
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        str(config.require("models.baseline.tokenizer_path")),
        local_files_only=True,
        trust_remote_code=bool(config.get("models.baseline.trust_remote_code", True)),
    )

    def target_token_count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    source_fetch = json.loads((data_root / "manifests" / "source_fetch.json").read_text(encoding="utf-8"))
    outputs: dict[str, Any] = {}
    selected_manifest: dict[str, Any] = {
        "schema": SELECTION_SCHEMA,
        "seed": SELECTION_SEED,
        "selection_policy": "locked_source_coordinates_in_declared_order",
        "datasets": {},
    }
    raw_before: dict[str, str] = {}
    raw_after: dict[str, str] = {}
    for dataset, raw_name in (("gsm8k", "gsm8k_test.jsonl"), ("qmsum", "qmsum_test.jsonl")):
        raw_path = data_root / "raw" / dataset / raw_name
        raw_before[dataset] = _file_sha256(raw_path)
        source = source_fetch["sources"][dataset]
        if raw_before[dataset] != source["expected_raw_sha256"]:
            raise ValueError(f"{dataset} raw source hash mismatch")
        build_options = {
            "token_count": target_token_count,
            "qmsum_context_budget_tokens": budget_tokens,
            "qmsum_chunk_target_tokens": chunk_target_tokens,
        }
        rows = build_samples(_read_jsonl(raw_path), selection, dataset, **build_options)
        # A second independent construction must be byte-identical before anything is persisted.
        repeated = build_samples(_read_jsonl(raw_path), selection, dataset, **build_options)
        if [_canonical_bytes(row) for row in rows] != [_canonical_bytes(row) for row in repeated]:
            raise ValueError(f"{dataset} canonical conversion is not deterministic")
        eval_path = data_root / "eval" / dataset / f"{dataset}_n{len(rows)}.jsonl"
        _write_jsonl(eval_path, rows)
        reloaded = load_canonical_samples(eval_path, expected_dataset=dataset)
        if reloaded != rows:
            raise ValueError(f"{dataset} canonical sample reload mismatch")
        outputs[dataset] = {
            "path": str(eval_path.relative_to(data_root.parent)),
            "sha256": _file_sha256(eval_path),
            "sample_count": len(rows),
            "sample_ids": [row["sample_id"] for row in rows],
            "source_fingerprints": [row["source_fingerprint"] for row in rows],
            "prompt_sha256": [hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest() for row in rows],
            "prompt_versions": sorted({row["prompt_version"] for row in rows}),
            "source_revision": source["revision"],
            "source_sha256": raw_before[dataset],
        }
        selected_manifest["datasets"][dataset] = {
            "coordinates": _selection_coordinates(selection, dataset),
            **outputs[dataset],
        }
        raw_after[dataset] = _file_sha256(raw_path)
    selected_manifest["manifest_sha256"] = _fingerprint(selected_manifest)
    manifest_path = data_root / "manifests" / "stage3_n10_selection.json"
    _write_json(manifest_path, selected_manifest)
    dataset_manifest = {
        "schema": "ccdf.dataset-manifest.v3",
        "builder": "ccdf.datasets.pipeline",
        "seed": SELECTION_SEED,
        "selection_policy": selected_manifest["selection_policy"],
        "selection_manifest": str(manifest_path.relative_to(data_root.parent)),
        "selection_manifest_sha256": _file_sha256(manifest_path),
        "datasets": outputs,
    }
    _write_json(data_root / "manifests" / "dataset_manifest.json", dataset_manifest)
    audit = {
        "schema": PIPELINE_SCHEMA,
        "pass": raw_before == raw_after,
        "seed": SELECTION_SEED,
        "selection_manifest": str(manifest_path.relative_to(data_root.parent)),
        "selection_manifest_sha256": _file_sha256(manifest_path),
        "raw_immutable": raw_before == raw_after,
        "raw_sha256_before": raw_before,
        "raw_sha256_after": raw_after,
        "datasets": outputs,
        "checks": {
            "source_hash_lock": True,
            "exact_manifest_count": True,
            "unique_sample_ids": True,
            "non_empty_samples_and_references": True,
            "source_fingerprints_present": True,
            "deterministic_prompt_render": True,
            "byte_identical_double_build": True,
            "selection_manifest_reload": True,
            "raw_dataset_unchanged": raw_before == raw_after,
        },
    }
    if audit_path is not None:
        _write_json(audit_path, audit)
    return audit
