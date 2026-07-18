"""Dataset-only fetch, preprocessing, and deterministic sampling pipeline."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "ccdf.data.v1"
BUILDER_VERSION = "ccdf.data-builder.v1"
COHORT_VERSION = "real-sources-seeded-v1"
SOURCE_SPECS = {
    "gsm8k": {
        "repository": "https://github.com/openai/grade-school-math",
        "revision": "3101c7d5072418e28b9008a6636bde82a006892c",
        "relative_path": "grade_school_math/data/test.jsonl",
        "expected_raw_sha256": "3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14",
    },
    "qmsum": {
        "repository": "https://github.com/Yale-LILY/QMSum",
        "revision": "83d7768c1f2b4dfeb091385d3dc7e239b8e5bb7e",
        "relative_path": "data/ALL/jsonl/test.jsonl",
        "expected_raw_sha256": "6bcd428211260ad2efae3af76cbaf6a7f5ae4bb5e1e59c45a4b8e89539cb9208",
    },
}
SOURCE_URLS = {
    dataset: f"https://raw.githubusercontent.com/{spec['repository'].rsplit('/', 2)[-2]}/{spec['repository'].rsplit('/', 1)[-1]}/{spec['revision']}/{spec['relative_path']}"
    for dataset, spec in SOURCE_SPECS.items()
}
RAW_FILENAMES = {"gsm8k": "gsm8k_test.jsonl", "qmsum": "qmsum_test.jsonl"}
REQUIRED_FIELDS = {
    "fixture_id", "dataset", "split", "content_hash", "source_row_hash",
    "question", "reference_answer", "prompt_parts", "prompt", "lineage",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number} must be a JSON object")
                rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_canonical(row) + "\n" for row in rows), encoding="utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_canonical(value) + "\n", encoding="utf-8")


def fetch_sources(destination: Path, *, timeout_seconds: float = 60.0) -> dict[str, Path]:
    """Download the real test splits and record their exact content hashes."""
    destination = destination.resolve()
    paths: dict[str, Path] = {}
    sources: dict[str, Any] = {}
    for dataset, url in SOURCE_URLS.items():
        spec = SOURCE_SPECS[dataset]
        target = destination / "raw" / dataset / RAW_FILENAMES[dataset]
        target.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "ccdf-rework-data/2"})
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
                temporary_path = Path(handle.name)
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                    shutil.copyfileobj(response, handle)
                    etag = response.headers.get("ETag")
            actual_sha256 = _file_hash(temporary_path)
            if actual_sha256 != spec["expected_raw_sha256"]:
                raise ValueError(
                    f"source drift for {dataset} at {spec['revision']}: "
                    f"{actual_sha256} != {spec['expected_raw_sha256']}"
                )
            temporary_path.replace(target)
            temporary_path = None
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
        paths[dataset] = target
        sources[dataset] = {
            "repository": spec["repository"], "revision": spec["revision"],
            "url": url, "path": str(target.relative_to(destination)),
            "expected_raw_sha256": spec["expected_raw_sha256"], "sha256": _file_hash(target),
            "hash_lock_pass": _file_hash(target) == spec["expected_raw_sha256"],
            "bytes": target.stat().st_size, "etag": etag,
        }
    _write_json(
        destination / "manifests/source_fetch.json",
        {
            "manifest_version": "ccdf.source-fetch.v1",
            "cohort_version": COHORT_VERSION,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "sources": sources,
        },
    )
    return paths


def _validate_fixture(row: dict[str, Any]) -> None:
    missing = REQUIRED_FIELDS.difference(row)
    if missing:
        raise ValueError(f"fixture missing fields: {sorted(missing)}")
    if row["content_hash"][:8] not in row["fixture_id"]:
        raise ValueError(f"fixture ID does not contain content hash: {row['fixture_id']}")
    if row["prompt_parts"]["question"] != row["question"] or not row["reference_answer"]:
        raise ValueError(f"invalid protected fields: {row['fixture_id']}")


def _gsm8k(raw: dict[str, Any], index: int, raw_sha256: str, source_revision: str) -> dict[str, Any]:
    question, answer = str(raw.get("question", "")).strip(), str(raw.get("answer", "")).strip()
    if not question or "####" not in answer:
        raise ValueError("GSM8K row requires question and an answer with #### final marker")
    reference = answer.rsplit("####", 1)[1].strip().replace("$", "").replace(",", "")
    identity = {
        "dataset": "gsm8k", "split": "test", "upstream_row_index": index,
        "question": question, "reference_answer": reference,
    }
    content_hash = _hash(identity)
    instruction = "End with exactly one line: Final answer: <number>"
    prompt = f"Short-context numeric QA. Solve the math word problem.\n\nQuestion: {question}\n\n{instruction}"
    fixture = {
        "fixture_id": f"gsm8k_test_{index:06d}_{content_hash[:8]}",
        "dataset": "gsm8k", "split": "test", "content_hash": content_hash,
        "source_row_hash": _hash(raw), "question": question, "reference_answer": reference,
        "prompt_parts": {"context": "Short-context numeric QA.", "question": question, "instruction": instruction, "system": None},
        "prompt": prompt,
        "lineage": {
            "source_identity": "openai/gsm8k:test", "source_revision": source_revision,
            "source_raw_sha256": raw_sha256, "upstream_row_index": index,
        },
        "evaluation": {"policy": "numeric_final_answer_exact_match", "answer_extraction": "GSM8K #### marker"},
    }
    _validate_fixture(fixture)
    return fixture


def _truncate_turns(turns: list[dict[str, str]], max_context_words: int) -> tuple[list[dict[str, str]], dict[str, Any]]:
    original_words = sum(len(turn["content"].split()) for turn in turns)
    if original_words <= max_context_words:
        return turns, {"truncated": False, "original_words": original_words, "retained_words": original_words, "boundary": "none", "strategy": "none", "caveat": ""}
    retained: list[dict[str, str]] = []
    retained_words = 0
    for turn in turns:
        words = turn["content"].split()
        if retained_words + len(words) > max_context_words:
            break
        retained.append(turn)
        retained_words += len(words)
    if not retained:
        retained = [{"speaker": turns[0]["speaker"], "content": " ".join(turns[0]["content"].split()[:max_context_words])}]
        retained_words = len(retained[0]["content"].split())
        boundary = "word"
    else:
        boundary = "utterance"
    return retained, {
        "truncated": True, "original_words": original_words, "retained_words": retained_words,
        "boundary": boundary, "strategy": "prefix_preserve_turn_boundaries",
        "caveat": "Reference evidence may fall outside retained context.",
    }


def _qmsum_rows(
    raw: dict[str, Any], meeting_index: int, raw_sha256: str,
    source_revision: str, max_context_words: int,
) -> list[dict[str, Any]]:
    meeting_id = str(raw.get("meeting_id") or raw.get("id") or raw.get("meeting") or f"meeting{meeting_index:04d}")
    source_turns = raw.get("meeting_transcripts")
    if not isinstance(source_turns, list) or not source_turns:
        raise ValueError("QMSum row requires non-empty meeting_transcripts")
    turns = [
        {"speaker": str(turn.get("speaker", "unknown")).strip() or "unknown", "content": str(turn.get("content", "")).strip()}
        for turn in source_turns if str(turn.get("content", "")).strip()
    ]
    selected_turns, truncation = _truncate_turns(turns, max_context_words)
    context = "\n".join(f"{turn['speaker']}: {turn['content']}" for turn in selected_turns)
    rows: list[dict[str, Any]] = []
    for query_index, query in enumerate(raw.get("specific_query_list") or []):
        question, reference = str(query.get("query", "")).strip(), str(query.get("answer", "")).strip()
        if not question or not reference:
            raise ValueError("QMSum query requires query and answer")
        identity = {
            "dataset": "qmsum", "split": "test", "meeting_id": meeting_id,
            "query_type": "specific", "query_index": query_index, "question": question,
            "reference_answer": reference, "turns": selected_turns, "truncation": truncation,
        }
        content_hash = _hash(identity)
        instruction = "Answer using only the meeting transcript. A concise answer is enough."
        fixture = {
            "fixture_id": f"qmsum_test_{meeting_id}_specific_{query_index:02d}_{content_hash[:8]}",
            "dataset": "qmsum", "split": "test", "content_hash": content_hash,
            "source_row_hash": _hash(raw), "question": question, "reference_answer": reference,
            "prompt_parts": {"context": context, "question": question, "instruction": instruction, "system": None},
            "prompt": f"Meeting transcript:\n{context}\n\nQuestion:\n{question}\n\n{instruction}",
            "meeting": {"meeting_id": meeting_id, "turns": selected_turns},
            "qmsum_policy": {"query_policy": "specific_only", "query_type": "specific", "query_index": query_index},
            "truncation": truncation,
            "lineage": {
                "source_identity": "psunlpgroup/QMSum:test", "source_revision": source_revision,
                "source_raw_sha256": raw_sha256, "meeting_index": meeting_index,
                "meeting_id": meeting_id, "query_type": "specific", "query_index": query_index,
            },
            "evaluation": {"policy": "reference_precision_recall_proxy", "semantic_correctness": "NOT_CLAIMED"},
        }
        _validate_fixture(fixture)
        rows.append(fixture)
    if not rows:
        raise ValueError("QMSum meeting has no specific queries")
    return rows


@dataclass(frozen=True)
class DatasetBuildConfig:
    raw_root: Path
    output_root: Path
    seed: int = 42
    sample_size: int = 10
    qmsum_max_context_words: int = 1500
    enforce_source_lock: bool = True


def _sample(rows: list[dict[str, Any]], seed: int, sample_size: int) -> list[dict[str, Any]]:
    if sample_size < 1 or sample_size > len(rows):
        raise ValueError(f"sample_size must be in [1, {len(rows)}]")
    return sorted(
        rows,
        key=lambda row: hashlib.sha256(f"{seed}:{row['fixture_id']}".encode("utf-8")).hexdigest(),
    )[:sample_size]


def build_datasets(config: DatasetBuildConfig) -> dict[str, Any]:
    """Build complete processed splits plus a seeded deterministic evaluation sample."""
    raw_root, output_root = config.raw_root.resolve(), config.output_root.resolve()
    raw_paths = {name: raw_root / "raw" / name / RAW_FILENAMES[name] for name in SOURCE_URLS}
    raw_hashes = {name: _file_hash(path) for name, path in raw_paths.items()}
    if config.enforce_source_lock:
        for name, actual_sha256 in raw_hashes.items():
            expected_sha256 = SOURCE_SPECS[name]["expected_raw_sha256"]
            if actual_sha256 != expected_sha256:
                raise ValueError(f"raw source drift for {name}: {actual_sha256} != {expected_sha256}")
    processed = {
        "gsm8k": [
            _gsm8k(row, index, raw_hashes["gsm8k"], SOURCE_SPECS["gsm8k"]["revision"])
            for index, row in enumerate(_read_jsonl(raw_paths["gsm8k"]))
        ],
        "qmsum": [
            item for index, row in enumerate(_read_jsonl(raw_paths["qmsum"]))
            for item in _qmsum_rows(
                row, index, raw_hashes["qmsum"], SOURCE_SPECS["qmsum"]["revision"],
                config.qmsum_max_context_words,
            )
        ],
    }
    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "builder_version": BUILDER_VERSION,
        "cohort_version": COHORT_VERSION,
        "seed": config.seed, "sample_size": config.sample_size,
        "sampling_strategy": "sha256(seed:fixture_id)_ascending", "datasets": {},
    }
    for name, rows in processed.items():
        ids = [row["fixture_id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate {name} fixture IDs")
        processed_path = output_root / "processed" / name / f"{name}_processed.jsonl"
        sample_path = output_root / "eval" / name / f"{name}_n{config.sample_size}.jsonl"
        sample = _sample(rows, config.seed, config.sample_size)
        _write_jsonl(processed_path, rows)
        _write_jsonl(sample_path, sample)
        manifest["datasets"][name] = {
            "split": "test", "raw_path": f"raw/{name}/{RAW_FILENAMES[name]}",
            "source_revision": SOURCE_SPECS[name]["revision"],
            "expected_raw_sha256": SOURCE_SPECS[name]["expected_raw_sha256"],
            "source_lock_pass": raw_hashes[name] == SOURCE_SPECS[name]["expected_raw_sha256"],
            "raw_sha256": raw_hashes[name], "raw_row_count": len(_read_jsonl(raw_paths[name])),
            "processed_path": f"processed/{name}/{name}_processed.jsonl",
            "processed_sha256": _file_hash(processed_path), "processed_row_count": len(rows),
            "sample_path": f"eval/{name}/{name}_n{config.sample_size}.jsonl",
            "sample_sha256": _file_hash(sample_path), "sample_row_count": len(sample),
            "sample_row_ids": [row["fixture_id"] for row in sample],
        }
    _write_json(output_root / "manifests/dataset_manifest.json", manifest)
    return manifest
