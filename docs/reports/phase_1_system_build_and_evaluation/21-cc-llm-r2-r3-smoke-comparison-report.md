# CC-LLM R2/R3 Smoke Comparison Report

## Result

PASS

This is a smoke-only comparison against the existing DFlash-R1 control artifact. It is not a final benchmark claim.

## Exact Commands Run

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R2 --n 3 --output results/_archives/early_smokes/cc_llm_r2_smoke.jsonl
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --config config.yml --condition CC-LLM-R3 --n 3 --output results/_archives/early_smokes/cc_llm_r3_smoke.jsonl
```

Verification commands:

```bash
python3 -m compileall src tests scripts
PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q
PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run
PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q
wc -l results/_archives/early_smokes/cc_llm_r2_smoke.jsonl results/_archives/early_smokes/cc_llm_r3_smoke.jsonl
head -n 2 results/_archives/early_smokes/cc_llm_r2_smoke.jsonl
head -n 2 results/_archives/early_smokes/cc_llm_r3_smoke.jsonl
```

## Artifact Paths

- `results/_archives/early_smokes/cc_llm_r2_smoke.jsonl`
- `results/_archives/early_smokes/cc_llm_r3_smoke.jsonl`
- control: `results/_archives/early_smokes/dflash_r1_n20.jsonl`

## Schema Status

PASS

Both CC-LLM artifacts use the DFlash-R1 JSONL schema plus compression fields:

- `t_compress_ms`
- `R_actual`
- `N_original`
- `N_compressed`
- `keep_rate`
- `compressor_model`
- `question_preserved`

Validation result:

- `results/_archives/early_smokes/cc_llm_r2_smoke.jsonl`: 3 rows
- `results/_archives/early_smokes/cc_llm_r3_smoke.jsonl`: 3 rows
- every row has the requested condition
- every row has `question_preserved == true`
- every row has `R_actual >= 1.0`
- every row has non-empty `acceptance_lengths`

## Compressor Model

- model: `microsoft/llmlingua-2-xlm-roberta-large-meetingbank`
- device: `cpu`
- source: locked LLMLingua config in `config.yml`

## Per-Condition Summary Metrics

| Condition | n | keep_rate | avg tok/s | avg tau_mean | avg t_compress_ms | avg R_actual | max VRAM allocated | max VRAM reserved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CC-LLM-R2 | 3 | 0.50 | 27.70 | 4.33 | 1128.84 | 2.20 | 3.510836124420166 GiB | 3.626953125 GiB |
| CC-LLM-R3 | 3 | 0.33 | 23.19 | 3.72 | 870.75 | 3.30 | 3.510836124420166 GiB | 3.623046875 GiB |

## Question Preservation

PASS

The smoke path keeps the fixed prompt text as the protected question, compresses only a small fixed context, passes the question into LLMLingua via `question=...`, and merges the compressed context with the original question. All six artifact rows report `question_preserved == true`.

## Smoke-Only Comparison To DFlash-R1 Control

The DFlash-R1 control artifact remains `results/_archives/early_smokes/dflash_r1_n20.jsonl`.

Known control summary from the audited n=20 artifact:

- average tok/s: `17.38`
- average tau_mean: `2.52`
- max VRAM allocated: `3.510836124420166 GiB`
- max VRAM reserved: `3.619140625 GiB`

The CC-LLM results are encouraging as a smoke comparison, but they are not directly comparable as final benchmark results because:

- CC-LLM was run at `n=3`
- DFlash-R1 control is `n=20`
- the CC-LLM path adds a fixed synthetic compressible context
- the prompt set is tiny
- generation is short
- `flash_attn` is still not installed, so the backend uses `torch.sdpa`

## Failures Or Abnormal Rows

- One initial `CC-LLM-R3` invocation exited early after the pre-load VRAM print without the runner's normal failure details.
- Re-running the same required command immediately passed and produced the final accepted artifact.
- Prompt 1 in both CC conditions has low tok/s because it generated only 2 output tokens.
- No artifact rows failed schema, question preservation, ratio, or acceptance-length validation.

## DFlash Baseline Control Path

Confirmed unchanged.

- no DFlash generation logic was modified
- no DFlash-R1 baseline behavior was modified
- `results/_archives/early_smokes/dflash_r1_n20.jsonl` remains the control artifact

## Next Step

LLMLingua-AR smoke baseline or expanded small condition matrix.
