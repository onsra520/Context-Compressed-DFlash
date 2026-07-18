"""One-row CUDA preflight for the full-context compression protocol."""

from __future__ import annotations

import json
from pathlib import Path

from ccdf.compression import CompressionConfig, ContextOnlyProtocol, LLMLinguaCompressor
from ccdf.config import load_config


def main() -> None:
    profile = load_config("config.yml").resolve_dataset_smoke_profile()
    settings, config = profile.settings, profile.config
    rows = [json.loads(line) for line in Path(settings["cohorts"]["qmsum"]).read_text().splitlines()]
    row = min(rows, key=lambda value: value["truncation"]["original_words"])
    protocol = ContextOnlyProtocol(
        row["prompt_parts"]["context"],
        row["question"],
        row["prompt_parts"]["instruction"],
        context_header=settings["prompts"]["qmsum_context_header"],
        question_header=settings["prompts"]["qmsum_question_header"],
    )
    compression_settings = settings["compression"]
    compression_config = CompressionConfig(**compression_settings)
    compressor = LLMLinguaCompressor(
        config.path_for("models.compressor.local_path"),
        device=config.require("models.compressor.device"),
        local_files_only=config.require("runtime.local_files_only"),
        reserved_vram_budget_gib=config.require("models.compressor.reserved_budget_gib"),
    )
    try:
        result = compressor.compress(protocol, compression_config)
        print(json.dumps({
            "fixture_id": row["fixture_id"],
            "original_tokens": result.original_tokens,
            "compressed_tokens": result.compressed_tokens,
            "chunks": result.chunk_count,
            "coverage": result.coverage_rate,
            "hidden_truncated_tokens": result.hidden_truncated_tokens,
            "peak_reserved_vram_bytes": result.peak_reserved_vram_bytes,
            "first_range": result.chunk_token_ranges[0],
            "last_range": result.chunk_token_ranges[-1],
        }, indent=2))
    finally:
        compressor.close()


if __name__ == "__main__":
    main()
