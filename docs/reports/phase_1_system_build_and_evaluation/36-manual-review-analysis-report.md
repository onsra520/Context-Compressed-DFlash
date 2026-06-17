# Task 36: Manual Review Analysis Summary

Date: 2026-06-04

## Result

PASS, preliminary.

## Input

Input report path:

- `docs/reports/35-manual-review-sample-report.md`

Analyzer command:

```bash
PYTHONPATH=src .venv/bin/python scripts/manual_review.py --input docs/reports/35-manual-review-sample-report.md
```

## Analyzer Output Summary

```json
{
  "counts_by_condition": {
    "CC-LLM-R2": 4,
    "CC-LLM-R3": 5,
    "DFlash-R1": 3,
    "LLMLingua-AR-R2": 3,
    "LLMLingua-AR-R3": 5
  },
  "counts_by_manual_label": {
    "PARAPHRASE_OR_FORMAT_MISS": 0,
    "TRUE_FAIL": 20,
    "UNCLEAR": 0
  },
  "paraphrase_or_format_miss_rate": 0.0,
  "reviewed_rows": 20,
  "true_fail_rate_in_reviewed_no_containment": 1.0,
  "unclear_rate": 0.0
}
```

## Interpretation

Task 35 no-containment rows appear to be true answer failures in this reviewed sample.

The containment scorer did not appear overly strict on the reviewed rows because the manual pass found no paraphrase-only or formatting-only misses.

`CC-LLM-R3` and `LLMLingua-AR-R3` remain the riskiest conditions in this sample because they produced the highest reviewed no-containment counts.

## Limitations

- Small sample.
- Synthetic fixture.
- Manual labels only cover `NO_CONTAINMENT` rows.
- Not final EM.
- Not a semantic-correctness benchmark.

## Recommendation

- Keep `DFlash-R1` as `KEEP_BASELINE`.
- Keep `LLMLingua-AR-R2` as `KEEP_LOW_VRAM_BASELINE`.
- Keep `CC-LLM-R2` and `CC-LLM-R3` as `WATCHLIST` pending larger `n`, `T_prefill`, and a real dataset.
- Proceed to Task 37 Baseline-AR implementation.
