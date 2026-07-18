"""Ensure trusted settings are resolved before test collection begins."""

from pathlib import Path

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def pytest_sessionstart(session) -> None:
    session.config._ccdf_trusted_config = load_config(ROOT / "config.yml")
