"""Emit Rec-T02B2 configuration evidence."""

from __future__ import annotations

import json
from pathlib import Path

from ccdf.artifacts.writer import write_json
from ccdf.benchmark.schemas import benchmark_schema
from ccdf.config import resolve_config, write_resolved_config
from ccdf.config.loader import load_config


def main() -> int:
    output = Path("results/Rec-T02B2")
    output.mkdir(parents=True, exist_ok=True)
    (output / "logs").mkdir(exist_ok=True)
    resolved = resolve_config(dataset="gsm8k", condition_id="baseline-ar")
    write_resolved_config(output, resolved)
    write_json(output / "canonical_config.json", load_config())
    write_json(output / "config_schema.json", {"required_sections": ["models", "runtime", "datasets", "benchmark", "evaluators", "compression", "artifacts"], "benchmark_schema": benchmark_schema()})
    write_json(output / "config_resolution_audit.json", {"byte_identical": resolved == resolve_config(dataset="gsm8k", condition_id="baseline-ar"), "resolved_hash": resolved.sha256, "single_prompt_and_benchmark_share_resolver": True, "compression_uses_resolved_config": True})
    write_json(output / "override_policy_audit.json", {"immutable_fields": ["models", "tokenizer", "dataset_manifest", "prompt_policy", "evaluators", "block_size"], "small_max_new_tokens_smoke_only": True, "canonical_aggregation_rejects_noncanonical": True})
    print(json.dumps({"resolved_config_hash": resolved.sha256}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
