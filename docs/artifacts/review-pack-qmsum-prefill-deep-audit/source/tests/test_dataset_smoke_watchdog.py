from pathlib import Path

from ccdf.benchmark.dataset_smoke import _watchdog_reason
from ccdf.config import load_config


def _settings():
    root = Path(__file__).resolve().parents[1]
    return load_config(root / "config.yml").resolve_dataset_smoke_profile().require(
        "watchdog"
    )


def test_watchdog_limits_are_read_from_config():
    settings = _settings()
    dataset = float(settings["dataset_wall_clock_timeout_seconds"])
    condition = float(settings["condition_wall_clock_timeout_seconds"])
    no_progress = float(settings["no_progress_timeout_seconds"])
    epsilon = min(dataset, condition, no_progress) / 1000

    assert _watchdog_reason(
        now=no_progress - epsilon,
        workflow_started=0,
        condition_started=0,
        last_progress=0,
        settings=settings,
    ) is None
    assert _watchdog_reason(
        now=dataset,
        workflow_started=0,
        condition_started=dataset,
        last_progress=dataset,
        settings=settings,
    ) == "dataset_wall_clock_timeout"
    assert _watchdog_reason(
        now=condition,
        workflow_started=condition,
        condition_started=0,
        last_progress=condition,
        settings=settings,
    ) == "condition_wall_clock_timeout"
    assert _watchdog_reason(
        now=no_progress,
        workflow_started=no_progress,
        condition_started=no_progress,
        last_progress=0,
        settings=settings,
    ) == "no_progress_timeout"
