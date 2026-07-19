import importlib.util
from pathlib import Path

import pytest

from ccdf.validation.quality import evaluate_complete_answer


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_rec3_canonical.py"
SPEC = importlib.util.spec_from_file_location("run_rec3_canonical", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_describe_reports_required_statistics() -> None:
    result = MODULE.describe([1.0, 2.0, 3.0])
    assert result == {
        "count": 3,
        "mean": 2.0,
        "median": 2.0,
        "min": 1.0,
        "max": 3.0,
        "stdev": 1.0,
    }


def test_describe_rejects_non_finite_series() -> None:
    with pytest.raises(ValueError, match="finite"):
        MODULE.describe([1.0, float("nan")])


def test_optional_file_identity_records_absence_without_failing(tmp_path) -> None:
    missing = tmp_path / "config-backup.yml"
    assert MODULE.optional_file_identity(missing) == {
        "path": str(missing),
        "exists": False,
        "sha256": None,
    }


def test_quality_accepts_equivalent_zero_product_wording() -> None:
    result = evaluate_complete_answer(
        prompt_index=1,
        text="0 multiplied by any number gives 0.\nFinal answer: The product of any number and 0 is 0.",
        stop_reason="eos",
        output_tokens=20,
        max_new_tokens=256,
    )
    assert result.quality_pass
