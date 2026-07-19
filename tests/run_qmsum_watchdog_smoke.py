"""Run the guarded QMSum n=2 x four-condition diagnostic before any n10 rerun."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import time

from ccdf.benchmark.dataset_smoke import (
    WatchdogTimeoutError,
    _prepare_inputs,
    _read_jsonl,
    _run_conditions_isolated,
    _write_json,
    _write_jsonl,
)
from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/artifacts/qmsum-runtime-timeout-diagnostic/n2-qmsum-four-conditions"


def main() -> None:
    source_config = load_config(ROOT / "config.yml")
    profile = source_config.resolve_dataset_smoke_profile()
    settings = profile.settings
    source_rows = _read_jsonl(Path(str(settings["cohorts"]["qmsum"])))
    selected = sorted(
        source_rows,
        key=lambda row: (
            int(row["truncation"]["original_words"]),
            str(row["fixture_id"]),
        ),
    )[:2]
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to replace diagnostic output: {OUTPUT}")
    OUTPUT.mkdir(parents=True)
    started_at_utc = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    lifecycle: list[dict] = []
    prepared, compression = _prepare_inputs(
        profile.config,
        settings,
        {"gsm8k": [], "qmsum": selected},
        lifecycle,
    )
    _write_json(OUTPUT / "selection.json", {
        "policy": "two shortest full-transcript QMSum samples for conservative protocol smoke",
        "fixture_ids": [row["fixture_id"] for row in selected],
        "original_words": [row["truncation"]["original_words"] for row in selected],
        "conditions": [row["name"] for row in settings["conditions"]],
        "qmsum_max_new_tokens": settings["generation"]["qmsum_max_new_tokens"],
        "watchdog": settings["watchdog"],
    })
    _write_json(OUTPUT / "compression_stage.json", compression)
    _write_jsonl(OUTPUT / "prepared.jsonl", prepared)
    try:
        rows, attempts = _run_conditions_isolated(
            source_config, settings, prepared, OUTPUT, started
        )
    except WatchdogTimeoutError as exc:
        summary = {
            "status": "FAIL",
            "verdict": "TIMEOUT_FAIL",
            "started_at_utc": started_at_utc,
            "finished_at_utc": datetime.now(timezone.utc).isoformat(),
            "duration_seconds": time.perf_counter() - started,
            "completed_cases": sum(
                int(item.get("rows_written", 0)) for item in exc.evidence.get("attempts", [])
            ),
            "expected_cases": len(selected) * len(settings["conditions"]),
            "failure": exc.evidence,
            "n10_rerun_permitted": False,
            "slow_sample_phase_permitted": False,
        }
        _write_json(OUTPUT / "summary.json", summary)
        print(json.dumps(summary, indent=2, sort_keys=True))
        raise SystemExit(1)
    duration = time.perf_counter() - started
    projected_n10_seconds = duration * (10 / len(selected))
    summary = {
        "status": "PASS" if projected_n10_seconds < float(
            settings["watchdog"]["dataset_wall_clock_timeout_seconds"]
        ) else "FAIL",
        "started_at_utc": started_at_utc,
        "finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": duration,
        "completed_cases": len(rows),
        "expected_cases": len(selected) * len(settings["conditions"]),
        "attempts": attempts,
        "projected_n10_seconds": projected_n10_seconds,
        "n10_rerun_permitted": projected_n10_seconds < float(
            settings["watchdog"]["dataset_wall_clock_timeout_seconds"]
        ),
        "slow_sample_phase_permitted": True,
    }
    _write_jsonl(OUTPUT / "rows.jsonl", rows)
    _write_json(OUTPUT / "summary.json", summary)
    shutil.rmtree(OUTPUT / ".working", ignore_errors=True)
    print(json.dumps(summary, indent=2, sort_keys=True))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
