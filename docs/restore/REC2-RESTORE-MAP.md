# REC-2 Controlled Restore Map

Status: live pre-change baseline recorded. Runtime source has not been modified.

## Source roles and identity

- **Workspace:** `/data/Projects/CCDF-Rework` (same inode target as `~/Projects/CCDF-Rework`).
- **Current-best:** `.worktrees/0-CURRENT-BEST-PERF-BEFORE-RESTORE/`.
- **REC-2:** `.worktrees/b21218f6-REC-2-RESTORE/`.
- The current and current-best `src/` trees are byte-identical, excluding generated `__pycache__` files.
- The REC-2 `src/` tree is byte-identical to current except `src/ccdf/validation/quality.py`; the current tree adds one valid zero-product wording to the evaluator.
- All three `config.yml` files have SHA-256 `15f829f308ab3584a09d0c211abcef7ef7c79e08bc706d5b706eef0eace4070f`.
- Both truth-source manifests passed `sha256sum -c` before this map was created.
- Both truth-source `data` and `models` entries resolve to the authorized workspace assets.

## Mapping

Decision values are restricted to `KEEP_CURRENT`, `RESTORE_REC2`, `PORT_CURRENT_BEST`, `MERGE`, `REWRITE_MINIMAL`, and `REJECT`.

| ID | Subsystem | Current workspace | Current-best | REC-2 | Contract/behavior difference | Decision | Risk | Required tests | Status |
|---|---|---|---|---|---|---|---|---|---|
| M01 | Configuration loading | `config.py:load_config`, `Rec2Config.validate` | Byte-identical | Byte-identical | None; same expanded paths and canonical validation | KEEP_CURRENT | Low | validate-config; config unit tests | MAPPED_PRE_BASELINE |
| M02 | CUDA/device initialization | `device.py` | Byte-identical | Byte-identical | None | KEEP_CURRENT | Medium | validate-env; CUDA smoke; placement checks | MAPPED_PRE_BASELINE |
| M03 | Model identity validation | `loaders.py:validate_dflash_contract` | Byte-identical | Byte-identical | None | KEEP_CURRENT | Medium | both model smokes; contract assertions | MAPPED_PRE_BASELINE |
| M04 | AWQ compatibility | `loaders.py:_prepare_awq_*` | Byte-identical | Byte-identical | None; activation alias and deterministic split-K shim present | KEEP_CURRENT | High | AWQ load smoke; deterministic repeat | MAPPED_PRE_BASELINE |
| M05 | Target model loading | `loaders.py:load_baseline`, `load_dflash_models` | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | Baseline/DFlash model smoke; CUDA-only placement | MAPPED_PRE_BASELINE |
| M06 | Drafter model loading | `loaders.py:load_dflash_models` | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | DFlash model smoke; block-size/mask contract | MAPPED_PRE_BASELINE |
| M07 | Target-drafter dtype handling | `generate.py` bridge casts | Byte-identical | Byte-identical | FP16 AWQ target and BF16 drafter are bridged locally in all trees | KEEP_CURRENT | High | dtype diagnostic; canonical parity | MAPPED_PRE_BASELINE |
| M08 | Attention implementation | Loader requests `sdpa`; runtime records effective attention | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | SDPA runtime metadata; no flash/mem-efficient kernels | MAPPED_PRE_BASELINE |
| M09 | Deterministic SDPA policy | `determinism.py` | Byte-identical | Byte-identical | None; math SDPA, TF32 off, deterministic algorithms on | KEEP_CURRENT | High | determinism unit/state checks; repeated token IDs | MAPPED_PRE_BASELINE |
| M10 | Tokenizer and prompt preparation | `engine.py:encode_prompt` | Byte-identical | Byte-identical | None; non-thinking chat template | KEEP_CURRENT | High | input-token parity; prompt hashes | MAPPED_PRE_BASELINE |
| M11 | Target prefill | `baseline.py:generate_baseline`; `verifier.py:prefill` | Byte-identical | Byte-identical | Baseline supplies all-ones mask; verifier relies on model default; same in REC-2 | KEEP_CURRENT | High | mock-08 execution-contract trace | DIAGNOSTIC_PROVEN |
| M12 | Drafter cache initialization | `generate.py:DynamicCache` | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | cache trace; structural audit | MAPPED_PRE_BASELINE |
| M13 | Target cache initialization | `verifier.py:TargetVerifier` | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | cache length trace; canonical parity | MAPPED_PRE_BASELINE |
| M14 | `position_ids` | Baseline scalar positions; verifier block ranges | Byte-identical | Byte-identical | Expected AR versus block shape difference | KEEP_CURRENT | High | exact mock-08 position trace | DIAGNOSTIC_PROVEN |
| M15 | `cache_position` | Derived inside Transformers from cache and positions | Byte-identical | Byte-identical | No explicit caller override in any tree | KEEP_CURRENT | High | instrument derived values without measured-run mutation | DIAGNOSTIC_PROVEN |
| M16 | `attention_mask` | Baseline explicit; block verifier implicit | Byte-identical | Byte-identical | Baseline q=1 uses caller all-ones and optimized null effective mask; block q=16 uses a Boolean causal mask with the same 176 visible keys at the selected position | KEEP_CURRENT | High | capture effective masks and SDPA inputs | DIAGNOSTIC_PROVEN |
| M17 | Block drafting | `generate.py` drafter call and proposal sampling | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | proposal IDs; dtype/device; acceptance trace | MAPPED_PRE_BASELINE |
| M18 | Target block verification | `verifier.py:verify` | Byte-identical | Byte-identical | Logical context, position, cache-position, mask visibility, KV dtype/device, and selected offset are proven correct; q=1 versus q=16 changes FP16 rounding | KEEP_CURRENT | Critical | mock-08 full contract trace; 50/50 parity | DIAGNOSTIC_PROVEN |
| M19 | Logit position selection | Baseline last logit; verifier posterior alignment | Byte-identical | Byte-identical | Baseline has an exact FP16 maximum tie and argmax chooses token 353; block verification separates token 24768 by one FP16 ULP | REWRITE_MINIMAL | Critical | ULP-boundary unit tests; mock-08 5/5; canonical 50/50 | ACCEPTED_REC2_R002 |
| M20 | Token acceptance | `acceptance.py`; verifier accepted prefix | Byte-identical | Byte-identical | None | KEEP_CURRENT | Critical | accepted-prefix unit tests; structural audit | MAPPED_PRE_BASELINE |
| M21 | Rollback after rejection | `verifier.py:cache.crop`; `generate.py` boundary crop | Byte-identical | Byte-identical | None | KEEP_CURRENT | Critical | cache-before/after trace; rejection fixtures | MAPPED_PRE_BASELINE |
| M22 | EOS and stopping behavior | `stopping.py` | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | stop-reason parity; no post-EOS tokens | MAPPED_PRE_BASELINE |
| M23 | `max_new_tokens` accounting | `BlockStopController`; generation loops | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | cap boundary tests; output count parity | MAPPED_PRE_BASELINE |
| M24 | Timing measurement | `baseline.py`, `generate.py`, `engine.py` | Byte-identical | Byte-identical | Current-best runner preserves non-invasive measured region | KEEP_CURRENT | Medium | CUDA sync audit; finite timing fields | MAPPED_PRE_BASELINE |
| M25 | tok/s calculation | `schemas.py:decode_tokens`, throughput properties | Byte-identical | Byte-identical | None; decode excludes prefill seed | KEEP_CURRENT | Medium | schema unit tests; independent recompute | MAPPED_PRE_BASELINE |
| M26 | E2E calculation | `engine.py` and timing schema | Byte-identical | Byte-identical | None | KEEP_CURRENT | Medium | raw-to-summary recompute | MAPPED_PRE_BASELINE |
| M27 | VRAM reset and measurement | `device.py`; runtime generators | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | peak reset; allocated/reserved gate | MAPPED_PRE_BASELINE |
| M28 | Structural metrics | `schemas.py:DFlashStats`; compact audit | Byte-identical | Byte-identical | None | KEEP_CURRENT | High | all block audits pass; counter invariant | MAPPED_PRE_BASELINE |
| M29 | Quality/parity validation | Current evaluator adds valid zero-product wording | Same as current | REC-2 lacks wording extension | Quality fix does not change tokens; parity remains exact-ID comparison | MERGE | Medium | quality regression; per-repetition token comparison | MAPPED_PRE_BASELINE |
| M30 | Canonical benchmark orchestration | `scripts/run_rec3_canonical.py` | Current-best requires root debug backup | Absent | Current keeps raw evidence and separate processes while allowing the forbidden root debug backup to be absent | MERGE | High | 10 prompts; 1 warm-up; 5 repetitions; row contract; final audit | ACCEPTED_REC2_R003 |
| M31 | Tests and smoke entrypoints | Current ignored `tests/` plus runner smoke | Byte-identical | REC-2 has no local ignored additions | Current adds regression and evidence helpers | KEEP_CURRENT | Medium | compileall; pytest; both model smokes | MAPPED_PRE_BASELINE |
| M32 | Linux-specific path/process assumptions | Relative root paths; `.worktrees/` ignored; separate condition processes | Current-best lacks only later `.worktrees/` ignore | REC-2 lacks restore workspace guard | Workspace-only safety and clean GPU release are Linux-compatible | KEEP_CURRENT | Medium | path resolution; process ownership; truth-source manifest recheck | MAPPED_PRE_BASELINE |

## Initial decision boundary

No REC-2 runtime function is currently eligible for wholesale restore because its bytes already match the workspace. The first live baseline and the full mock-08 execution-contract trace control whether any row moves from `KEEP_CURRENT` to `MERGE`, `REWRITE_MINIMAL`, or `REJECT`.

## Live pre-change finding

The required isolated canonical run completed with 1 warm-up plus 50 measured rows per condition. Baseline-AR mean decode throughput was 31.2469 tok/s; DFlash-R1 was 104.3243 tok/s; decode speedup was 3.3387x. Exact generated-token parity was 45/50: all five `mock-08` repetitions diverged at generated-token index 21, while every other prompt passed 5/5. Quality, structural, memory, policy, metric-validity, and workload gates passed. This result confirms the regression and narrows investigation to the rows still marked `DIAGNOSTIC_REQUIRED`; it is not an acceptance decision.

## Mock-08 contract result

The isolated instrumented requests reproduce both raw outputs exactly. At generated index 21, the prompt IDs and generated prefix are identical, yielding the same 176-token logical context. Both selected positions and derived cache positions are 175. Baseline's explicit all-ones mask and DFlash's effective Boolean causal row both expose keys 0 through 175. All 36 KV layers are FP16 on `cuda:0`; the differing cache lengths (175 for q=1 and 171 for q=16) plus the selected block offset 4 describe the same logical context. Baseline logits contain an exact maximum tie at 37.21875 for tokens 353 and 24768, and deterministic argmax chooses the lower token ID 353. Block verification produces 37.28125 versus 37.25, a one-ULP separation, and chooses 24768. Stopping is downstream and uninvolved. This proof authorizes only a minimal, local verifier tie-selection experiment; it does not authorize replay, an oracle, sequential target fallback, or an attention/backend change.

## Accepted repair boundary

REC2-R002 keeps strict argmax for proposal acceptance and applies the one-ULP representable-value band only when selecting the correction token at the already-computed rejection boundary. It does not consult Baseline output, token-specific state, prompt identity, or a replayed target call. If the top gap exceeds one ULP, the ordinary winner is retained; stochastic sampling is unchanged. The accepted full matrix is 50/50 exact, including `mock-08` 5/5, with no new mismatch and unchanged structural counters.
