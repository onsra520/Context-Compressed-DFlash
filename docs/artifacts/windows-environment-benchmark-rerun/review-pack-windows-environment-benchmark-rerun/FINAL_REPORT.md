# FINAL_REPORT.md

## Overall verdict: FAIL

This result is sealed as **FAIL**. The Windows environment repair and canonical regression pass, but generated-token parity fails in both mock10 and dataset smoke. No failed benchmark was retried, resumed, or tuned with another block size/SDPA policy.

## Sealed identity

- Config: `config.yml`
- Config SHA-256: `904c408e5d492ec03ec0b21a710303b06589479012e804725a575bb14ba4c086`
- Effective platform: `win32`
- SDPA kernel: `math`
- Mock10 and dataset fixed block size: `8`
- Canonical fixed block size: `16`
- Local-only checkpoints: enabled; offline environment enforced in workers

## Environment audit and fixes: PASS

- Pre-fix `pip check`: FAIL; post-fix: PASS.
- Windows allocator: `expandable_segments` warning reproduced, classified unsupported/non-fatal, then removed through the config-declared `win32` override (`cuda_allocator_conf: null`).
- AWQ Baseline/target: pre-fix requested BF16 but effective FP16; post-fix config and probes both report FP16.
- Compressor, Baseline AWQ, target AWQ, and drafter: all post-fix isolated load/inference probes PASS with CUDA-resident parameters, buffers, and inference tensors.
- AutoAWQ remains pinned at 0.2.9; deprecation is a non-fatal compatibility risk because inference passes.
- Official Triton has no Windows wheel. The pinned `triton-windows==3.7.1.post27` implementation plus metadata-only bridge resolves the reproduced package-metadata failure without changing the backend.

## Canonical Baseline-AR vs DFlash-R1: PASS

- Runs: 50 Baseline + 50 DFlash.
- Rendered-input parity: 50/50.
- Generated-token parity: 50/50.
- Frozen-reference parity: 50/50.
- DFlash peak reserved: 3.625000 GiB (limit 6 GiB).
- Determinism, structural checks, exact quality, and process stability: PASS.

## Four-condition mock10: FAIL

- Successful conditions: 40/40.
- Pair parity: 19/20 (required 20/20) — FAIL.
- Exact quality: 40/40.
- Metric validity: 40/40.
- DFlash-R1 peak reserved: 5.408203 GiB.
- CC-DFlash-R2 peak reserved: 4.527344 GiB.
- Failure: compressed pair `mock_04`, identical rendered input, divergent 20 vs 21 generated tokens.

## GSM8K n10 + QMSum n10: FAIL

- Successful runs: 80/80.
- Rendered-input parity: 40/40.
- Generated-token parity: 26/40 (required 40/40) — FAIL.
- GSM8K evaluator valid: 10/10.
- QMSum evaluator valid: 10/10.
- QMSum coverage: 100.0%; hidden truncation: 0.
- Metric validity: 80/80.
- DFlash-R1 peak reserved: 5.710938 GiB.
- CC-DFlash-R2 peak reserved: 5.710938 GiB.

Parity breakdown:

- gsm8k / compressed: 9/10 parity
- gsm8k / original: 9/10 parity
- qmsum / compressed: 6/10 parity
- qmsum / original: 2/10 parity

## Process stability

- Condition workers: 10/10 exit 0; native crashes 0; retries 0; resumes 0.
- Mock10 and dataset parent commands exit 1 only after sealing parity gate failures; they are not native crashes. Therefore the global zero-nonzero-exit gate across every invoked parent and worker process is FAIL.

## Protocol deviation

- Requested clean execution order: canonical regression → mock10 → dataset smoke.
- Actual clean execution order: mock10 → canonical regression → dataset smoke.
- Order gate: **FAIL**. Mock10 had already been sealed on its first attempt before the ordering issue was identified. It was not rerun because retry/rerun and policy tuning after a parity failure are prohibited.

## Repository validation

- compileall: PASS
- pytest: PASS (`69 passed`)
- pip check: PASS
- git diff --check: PASS
- Dataset artifact verifier: FAIL only because the sealed summary/gate matrix are FAIL; it verified 80 rows, 40 parity records, four worker attempts, and all chunk maps.
- D-Flash core unchanged proof: PASS.
- No commit or push was performed.

## Warning classification

- Unsupported on Windows: `expandable_segments`; non-fatal reproduction, config-fixed.
- Deprecated but operational: AutoAWQ, dependency `torch_dtype`, dependency `torch.jit.script`.
- Package/version incompatibility: AutoAWQ `triton` distribution metadata vs native Windows; fixed with pinned platform provider and metadata bridge.
- Invalid config claim: AWQ BF16 request while effective dtype was FP16; fixed to FP16.
- Fatal runtime warnings or native crashes: none.

## Final conclusion

**FAIL** — environment repair PASS and canonical regression PASS, but required mock10 and dataset generated-token parity gates do not pass. Raw evidence is preserved without fixture, reference, evaluator, block-size, or SDPA-policy changes made to manufacture a PASS.
