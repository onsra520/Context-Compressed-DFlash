# 25 Long-Context Fixture Report

## Task Title and Date

- Task: Long-context / dataset augmentation mini-spec or artifact
- Date: 2026-06-04

## Scope

This task adds a small controlled long-context fixture and a CPU-only validation test for future CCDF benchmark work. It does not download external datasets, does not run new GPU benchmarks, and does not make any final benchmark claims.

## Fixture Path

- `tests/fixtures/long_context_smoke.jsonl`

## Fixture Row Schema

Each JSONL row uses this contract:

- `id`
- `domain`
- `context`
- `question`
- `expected_answer`
- `evidence`
- `noise_type`
- `approximate_context_words`

Validation expectations:

- each non-empty line must parse as JSON
- required fields must be present
- `context`, `question`, `expected_answer`, and `evidence` must be non-empty strings
- `expected_answer` must appear in either `context` or `evidence`
- `approximate_context_words` must be an integer and above a small long-context threshold

## Example Categories and Domains

The fixture currently contains 6 examples across:

- finance invoice lookup
- public library policy lookup
- warehouse arithmetic
- clinic room schedule lookup
- compliance retention lookup
- school trip roster arithmetic

Design choices:

- contexts are meaningfully longer than the existing tiny smoke prompts
- every answer is explicitly recoverable from the fixture text
- each example includes irrelevant distractor content
- some examples are arithmetic, some are factual lookup
- questions are clean standalone strings that should remain preserved after compression
- all content is synthetic and non-sensitive

## Why This Helps Future Analysis

Task 24 used a tiny fixed prompt cycle, which was enough to verify plumbing but not enough to stress compression on longer inputs. This fixture gives us a small controlled corpus where:

- compression can remove obvious distractor material
- answer evidence still remains explicit
- longer input length can make compression overhead more meaningful
- future breakeven-style analysis can compare shorter and longer prompt regimes without needing a large external dataset

This makes it a good bridge into a later Task 26 analysis of speedup, tau, compression ratio, and end-to-end tradeoffs.

## Validation Commands and Results

Commands used for this task:

- `python3 -m compileall src tests scripts`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py tests/test_smoke_artifact_audit.py -q`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_long_context_fixture.py -q`

Results:

- `compileall`: PASS
- existing lightweight tests: PASS
- long-context fixture validation test: PASS

## Limitations

- This is a small synthetic fixture, not a full dataset benchmark.
- `approximate_context_words` is only a rough length signal, not tokenizer-derived token count.
- The fixture is designed for controlled future analysis, not for final model quality measurement.
- No benchmark run is attached to this task.
- Compression benefit remains a hypothesis to test, not a conclusion.

## Next Step

Task 26: preliminary analysis of speedup, tau, compression, and breakeven using Task 24 artifacts plus this long-context fixture.
