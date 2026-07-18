import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tests" / "run_short_prompt_smoke.py"
SPEC = importlib.util.spec_from_file_location("run_short_prompt_smoke", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _row(condition, prompt_index, token_ids, sequence):
    return {
        "condition": condition,
        "prompt_index": prompt_index,
        "order_index": sequence // 5,
        "repetition": sequence % 5,
        "sequence": sequence,
        "result": {
            "generated_token_ids": token_ids,
            "output_tokens": len(token_ids),
            "text": " ".join(str(token) for token in token_ids),
        },
    }


def test_determinism_and_parity_require_repeatable_cross_condition_tokens():
    rows = []
    for prompt_index in range(2):
        for condition in ("baseline", "dflash"):
            rows.extend(_row(condition, prompt_index, [prompt_index, 7], sequence) for sequence in range(10))

    deterministic = MODULE._determinism(rows, 2, True)
    parity = MODULE._parity(rows, 2)

    assert deterministic["pass"] is True
    assert parity["pass"] is True
    assert deterministic["by_condition"]["baseline"]["cases"][0]["unique_text_count"] == 1


def test_determinism_and_parity_report_a_single_divergent_repetition():
    rows = []
    for condition in ("baseline", "dflash"):
        rows.extend(_row(condition, 0, [1, 2], sequence) for sequence in range(10))
    rows[3] = _row("baseline", 0, [1, 9], 3)

    deterministic = MODULE._determinism(rows, 1, True)
    parity = MODULE._parity(rows, 1)

    assert deterministic["pass"] is False
    divergence = deterministic["by_condition"]["baseline"]["cases"][0]["divergences"][0]
    assert divergence["token_index"] == 1
    assert divergence["expected_token_id"] == 2
    assert divergence["actual_token_id"] == 9
    assert parity["pass"] is False
