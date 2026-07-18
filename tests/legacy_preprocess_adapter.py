"""Run the old preprocessing implementation against explicitly supplied raw rows."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".worktrees/source-main/src"))

from ccdf.datasets import gsm8k, qmsum  # noqa: E402


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("gsm8k", "qmsum"), required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    identity = "openai/gsm8k:test" if args.dataset == "gsm8k" else "psunlpgroup/QMSum:test"
    source_lock = {"identity": identity, "resolved_revision": args.revision, "raw_sha256": _hash_file(args.raw)}
    raw_rows = _read_jsonl(args.raw)
    if args.dataset == "gsm8k":
        fixtures = gsm8k.build_fixtures(raw_rows, source_lock)
    else:
        fixtures, _ = qmsum.build_fixtures(
            raw_rows, source_lock, query_policy="specific_only", max_context_words=1500
        )
    _write_jsonl(args.output, fixtures)
    print(json.dumps({"dataset": args.dataset, "raw_rows": len(raw_rows), "processed_rows": len(fixtures)}))


if __name__ == "__main__":
    main()
