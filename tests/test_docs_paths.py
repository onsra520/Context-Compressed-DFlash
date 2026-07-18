from pathlib import Path

from ccdf.config import load_config


ROOT = Path(__file__).resolve().parents[1]


def test_config_artifacts_root_is_under_docs():
    config = load_config(ROOT / "config.yml")
    assert config.path_for("paths.artifacts_root") == ROOT / "docs" / "artifacts"


def test_canonical_scripts_write_only_under_docs():
    runner = (ROOT / "tests" / "run_256token_audit.py").read_text(encoding="utf-8")
    assert 'ROOT / "docs" / "audit" / "canonical-freeze"' in runner
    assert 'ROOT / "docs" / "artifacts"' in runner
