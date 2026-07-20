#!/usr/bin/env python3
"""Materialize the frozen seed-42 n20 cohorts without changing dataset semantics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from transformers import AutoTokenizer

from ccdf.config import load_config
from ccdf.datasets.pipeline import build_samples


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/final-benchmark-n20"
DATA = ROOT / "data"
SEED = 42
TARGET_COUNT = 20


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8") + b"\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"".join(canonical_bytes(row) for row in rows))


def coordinate_key(dataset: str, coordinate: dict[str, int]) -> str:
    return hashlib.sha256(
        canonical_bytes({"dataset": dataset, "seed": SEED, "coordinate": coordinate})
    ).hexdigest()


def extend_locked_prefix(
    dataset: str,
    prefix: list[dict[str, int]],
    universe: list[dict[str, int]],
) -> tuple[list[dict[str, int]], list[dict[str, int]]]:
    prefix_keys = {canonical_bytes(row) for row in prefix}
    if len(prefix_keys) != len(prefix):
        raise ValueError(f"{dataset} locked prefix contains duplicate coordinates")
    universe_keys = {canonical_bytes(row) for row in universe}
    if not prefix_keys <= universe_keys:
        raise ValueError(f"{dataset} locked prefix contains coordinates outside the source")
    remaining = [row for row in universe if canonical_bytes(row) not in prefix_keys]
    remaining.sort(key=lambda row: (coordinate_key(dataset, row), canonical_bytes(row)))
    extension = remaining[: TARGET_COUNT - len(prefix)]
    selected = [*prefix, *extension]
    if len(selected) != TARGET_COUNT:
        raise ValueError(f"{dataset} cannot supply {TARGET_COUNT} deterministic coordinates")
    return selected, extension


def main() -> int:
    config = load_config(ROOT / "config.yml")
    frozen = json.loads((DATA / "manifests/dataset_smoke_selection.json").read_text(encoding="utf-8"))
    if frozen.get("seed") != SEED:
        raise ValueError("frozen n10 selection seed is not 42")
    gsm_raw_path = DATA / "raw/gsm8k/gsm8k_test.jsonl"
    qmsum_raw_path = DATA / "raw/qmsum/qmsum_test.jsonl"
    gsm_raw = read_jsonl(gsm_raw_path)
    qmsum_raw = read_jsonl(qmsum_raw_path)
    gsm_universe = [{"upstream_row_index": index} for index in range(len(gsm_raw))]
    qmsum_universe = [
        {"meeting_index": meeting_index, "query_index": query_index}
        for meeting_index, meeting in enumerate(qmsum_raw)
        for query_index, query in enumerate(meeting.get("specific_query_list", []))
        if str(query.get("query", "")).strip()
    ]
    gsm_coordinates, gsm_extension = extend_locked_prefix("gsm8k", frozen["gsm8k"], gsm_universe)
    qmsum_coordinates, qmsum_extension = extend_locked_prefix("qmsum", frozen["qmsum"], qmsum_universe)
    selection = {
        "schema": "ccdf.final-benchmark-n20.selection.v1",
        "seed": SEED,
        "target_count": TARGET_COUNT,
        "policy": "locked_n10_prefix_then_seed42_sha256_coordinate_rank",
        "ranking_payload": {"keys": ["dataset", "seed", "coordinate"], "encoding": "canonical-json-utf8"},
        "reference_used_for_selection": False,
        "datasets": {
            "gsm8k": {"locked_prefix_count": len(frozen["gsm8k"]), "coordinates": gsm_coordinates, "extension": gsm_extension},
            "qmsum": {"locked_prefix_count": len(frozen["qmsum"]), "coordinates": qmsum_coordinates, "extension": qmsum_extension},
        },
    }
    selection_input = {
        "seed": SEED,
        "gsm8k": gsm_coordinates,
        "qmsum": qmsum_coordinates,
    }

    tokenizer = AutoTokenizer.from_pretrained(
        str(config.require("models.baseline.tokenizer_path")),
        local_files_only=True,
        trust_remote_code=bool(config.get("models.baseline.trust_remote_code", True)),
    )

    def token_count(text: str) -> int:
        return len(tokenizer.encode(text, add_special_tokens=False))

    options = {
        "token_count": token_count,
        "qmsum_context_budget_tokens": int(config.require("datasets.qmsum_context_budget_tokens")),
        "qmsum_chunk_target_tokens": int(config.require("datasets.qmsum_chunk_target_tokens")),
    }
    rows_by_dataset: dict[str, list[dict[str, Any]]] = {}
    for dataset, raw in (("gsm8k", gsm_raw), ("qmsum", qmsum_raw)):
        first = build_samples(raw, selection_input, dataset, **options)
        second = build_samples(raw, selection_input, dataset, **options)
        if [canonical_bytes(row) for row in first] != [canonical_bytes(row) for row in second]:
            raise ValueError(f"{dataset} n20 double-build is not byte-identical")
        rows_by_dataset[dataset] = first
        write_jsonl(DATA / f"eval/{dataset}/{dataset}_n20.jsonl", first)

    write_json(OUT / "selection-config.json", selection)
    qmsum_selection = []
    for sample in rows_by_dataset["qmsum"]:
        evidence = sample["metadata"]["context_selection"]
        qmsum_selection.append(
            {
                "schema": "ccdf.final-benchmark-n20.qmsum-selection.v1",
                "sample_id": sample["sample_id"],
                "source_fingerprint": sample["source_fingerprint"],
                "meeting_index": sample["source_index"],
                "query_index": sample["metadata"]["query_index"],
                "full_transcript_target_tokens": evidence["full_transcript_token_count"],
                "chunk_count": evidence["full_chunk_count"],
                "selected_chunk_ids": evidence["selected_chunk_ids"],
                "selected_source_ranges": evidence["selected_source_ranges"],
                "selected_context_target_tokens": evidence["selected_context_token_count"],
                "selection_keep_rate": evidence["selection_keep_rate"],
                "query_term_coverage": evidence["query_term_coverage"],
                "selected_context_sha256": evidence["selected_context_sha256"],
                "compressed_context_sha256": None,
                "llmlingua_keep_rate": None,
                "overall_keep_rate": None,
                "reference_used_for_selection": False,
            }
        )
    write_jsonl(OUT / "qmsum/selection.jsonl", qmsum_selection)

    source_fetch = json.loads((DATA / "manifests/source_fetch.json").read_text(encoding="utf-8"))
    datasets: dict[str, Any] = {}
    for dataset, raw_path in (("gsm8k", gsm_raw_path), ("qmsum", qmsum_raw_path)):
        sample_path = DATA / f"eval/{dataset}/{dataset}_n20.jsonl"
        raw_hash = sha256_file(raw_path)
        expected_hash = source_fetch["sources"][dataset]["expected_raw_sha256"]
        if raw_hash != expected_hash:
            raise ValueError(f"{dataset} raw source hash does not match source lock")
        datasets[dataset] = {
            "sample_file": str(sample_path.relative_to(ROOT)),
            "sample_file_sha256": sha256_file(sample_path),
            "sample_count": len(rows_by_dataset[dataset]),
            "raw_source": str(raw_path.relative_to(ROOT)),
            "raw_source_sha256": raw_hash,
            "source_revision": source_fetch["sources"][dataset]["revision"],
            "samples": [
                {
                    "sample_id": row["sample_id"],
                    "reference": row["reference"],
                    "source_fingerprint": row["source_fingerprint"],
                    "source_index": row["source_index"],
                    "prompt_version": row["prompt_version"],
                    "prompt_sha256": hashlib.sha256(row["prompt"].encode("utf-8")).hexdigest(),
                }
                for row in rows_by_dataset[dataset]
            ],
        }
    manifest = {
        "schema": "ccdf.final-benchmark-n20.sample-manifest.v1",
        "seed": SEED,
        "selection_policy": selection["policy"],
        "selection_config": "docs/final-benchmark-n20/selection-config.json",
        "selection_config_sha256": sha256_file(OUT / "selection-config.json"),
        "byte_identical_double_build": True,
        "reference_used_for_selection": False,
        "datasets": datasets,
    }
    write_json(OUT / "SAMPLE-MANIFEST.json", manifest)
    print(json.dumps({dataset: datasets[dataset]["sample_file_sha256"] for dataset in datasets}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
