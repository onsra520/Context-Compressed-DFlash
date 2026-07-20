# Final benchmark n=20 command log

All commands run from `/data/Projects/CCDF-Rework` through the required RTK
shell wrapper. The environment Python is
`/home/quyseggs/miniforge3/envs/CCDF/bin/python` with `PYTHONPATH=src`.

## Preflight

```text
python docs/final-benchmark-n20/tools/build_final_n20_inputs.py
sha256sum data/eval/gsm8k/gsm8k_n20.jsonl data/eval/qmsum/qmsum_n20.jsonl docs/final-benchmark-n20/selection-config.json docs/final-benchmark-n20/SAMPLE-MANIFEST.json docs/final-benchmark-n20/qmsum/selection.jsonl
python docs/final-benchmark-n20/tools/build_final_n20_inputs.py
sha256sum -c /tmp/final-n20-hashes-1.txt
pytest -q tests/test_dataset_pipeline.py tests/test_quality_repair.py tests/test_compression_safeguard.py tests/test_four_condition_protocol.py
python docs/final-benchmark-n20/tools/run_preflight.py
```

Model execution commands will be appended before execution. Any interruption
and resume command will be recorded here without deleting valid evidence.

## Model execution

```text
bash docs/final-benchmark-n20/tools/run_dataset.sh gsm8k 256
bash docs/final-benchmark-n20/tools/run_dataset.sh qmsum 512
```

Both commands use fresh dataset-specific compression caches and invoke every
condition with `--resume`. The detailed subprocess commands and outputs are in
`gsm8k/execution.log` and `qmsum/execution.log`.

## Independent audit and packaging

```text
python docs/final-benchmark-n20/tools/finalize_results.py
```

The initial derived decision classified GSM8K parser/quality failures as hard
pipeline invalidity. The original outputs are preserved as
`gsm8k/audit-preclassification.json`, `final-decision-preclassification.json`,
and `finalize.initial.stdout.json`. A `jq`-only derived-artifact reclassification
then separated model-output quality failures from validity/integrity gates,
producing `classification-audit.json`. No raw JSONL was edited and no benchmark
was rerun.

The GSM8K v4-to-v5 instruction token delta was computed after the run using the
frozen target tokenizer, identical questions, identical chat template, and the
two frozen instruction suffixes. This was tokenizer-only analysis, not a v4
model run; results are in `gsm8k/instruction-token-reduction.json`.

## Final verification

The first full-suite invocation used the system shell without the explicit
Conda Python and failed before collection because `pytest` was absent from
`PATH`; that bootstrap-only output is preserved in
`final-tests.bootstrap-failure.txt`. The environment-qualified command then
passed:

```text
PYTHONPATH=src /home/quyseggs/miniforge3/envs/CCDF/bin/python -m pytest -q
```

Result: 97 passed. Packaging then captured the relevant source/config/input
snapshot, worktree state, per-file SHA-256 manifest, and archive checksum.
