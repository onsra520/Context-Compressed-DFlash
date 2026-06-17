# Task 73 - QMSum Concise-Answer Prompt Refinement

Date: 2026-06-13

## Result

PASS_WITH_NOTES.

Task 73 added a QMSum-specific concise-answer output policy, preserved it outside compression, and ran bounded compressed-only QMSum n=30 calibrations at `max_new_tokens=384`.

The concise policy eliminated compressed cap hits in both Task 73 artifacts, but normalized-overlap proxy quality dropped materially versus Task 71. Therefore the policy is useful as a cap-pressure mitigation, but it should not be frozen as the final QMSum quality policy without further prompt/proxy triage.

Task 72 commit: `cb2b8f9 test: triage qmsum compressed cap hits`.

## Prompt and Code Changes

Added a QMSum-only concise-answer policy:

```text
Answer concisely in 1-3 sentences.
Do not repeat the full context.
Do not include long reasoning.
Use only information supported by the meeting context.
```

Policy behavior:

- Applies only to `qmsum_meeting_qa_long`.
- Does not modify GSM8K final-answer suffix behavior.
- Is appended as a protected suffix outside compression for compressed QMSum conditions.
- Is recorded in compressed artifact metadata:
  - `qmsum_concise_policy_enabled`
  - `qmsum_concise_policy_preserved`
  - `qmsum_output_policy_preview`
  - `final_prompt_tail_preview`

## Commands Run

Prompt dry-run:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --n 3 --seed 42 --dry-run-prompts
```

Real bounded compressed-only runs:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl --resume --store-generated-text
```

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl --resume --store-generated-text
```

Analyzer:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task73_qmsum_concise_policy.py
```

## Run Completion

| Condition | Artifact | Rows | Policy Preserved | Cap Hits |
|---|---|---:|---:|---:|
| LLMLingua-AR-R2 | `results/task73_qmsum_long_llmlingua_ar_r2_n30_mnt384_concise.jsonl` | 30 | 30/30 | 0/30 |
| CC-DFlash-R2 | `results/task73_qmsum_long_cc_dflash_r2_n30_mnt384_concise.jsonl` | 30 | 30/30 | 0/30 |

## Cap-Hit Before/After

| Condition | Task 71 Cap Hits | Task 73 Cap Hits | Delta |
|---|---:|---:|---:|
| LLMLingua-AR-R2 | 22/30 | 0/30 | -22 |
| CC-DFlash-R2 | 21/30 | 0/30 | -21 |

The concise policy clearly reduced QMSum truncation/cap pressure at `max_new_tokens=384`.

## Proxy Quality Before/After

| Condition | Task 71 Avg Overlap | Task 73 Avg Overlap | Delta | Proxy Improved IDs | Proxy Degraded IDs |
|---|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 0.3586 | 0.2275 | -0.1311 | 1 | 23 |
| CC-DFlash-R2 | 0.3575 | 0.2285 | -0.1290 | 1 | 23 |

The concise policy shortened outputs substantially, but the normalized-overlap proxy fell. This may partly reflect the weakness of reference-overlap scoring for short abstractive answers, but it is still a quality warning and should block QMSum n=100 quality claims.

## Speed Before/After

| Condition | Task 71 Avg Output Tokens | Task 73 Avg Output Tokens | Task 71 Avg E2E Latency (s) | Task 73 Avg E2E Latency (s) | Task 71 Weighted E2E tok/s | Task 73 Weighted E2E tok/s |
|---|---:|---:|---:|---:|---:|---:|
| LLMLingua-AR-R2 | 348.53 | 48.50 | 26.38 | 8.04 | 13.21 | 6.03 |
| CC-DFlash-R2 | 345.33 | 48.67 | 19.06 | 7.58 | 18.12 | 6.42 |

Latency dropped because the generated answers became much shorter. Weighted tok/s also dropped because the denominator includes compression time while output tokens are much fewer. This is not a final speedup result.

## Decision

| Question | Decision |
|---|---|
| Did the concise policy reduce truncation? | Yes: cap hits dropped from 43 total to 0 total. |
| Did the concise policy harm proxy quality? | Yes by the current normalized-overlap proxy. |
| Should concise policy be kept as final QMSum default now? | Not yet. It needs prompt/proxy triage. |
| Is mnt512 still justified next? | No. Cap pressure was removed at mnt384. |
| Is QMSum n=100 justified next? | No, unless explicitly scoped as speed-only. |
| Does CC-DFlash-R2 still beat LLMLingua-AR-R2 e2e? | Yes in these Task 73 artifacts, but all claims remain preliminary. |

## Interpretation

Task 73 shows the cap-hit issue can be mitigated without increasing `max_new_tokens`. However, the current concise-answer wording appears too aggressive for the normalized-overlap proxy, or the proxy is too strict for short abstractive meeting answers. The next step should inspect changed rows and decide whether to:

- adjust the QMSum concise prompt to request reference-covering answers without long reasoning,
- improve the QMSum proxy/manual review policy,
- or frame future QMSum runs as speed/prefill diagnostics rather than quality claims.

## Limitations

- QMSum quality remains a normalized-overlap / containment proxy, not semantic correctness.
- No manual review or LLM judge was used.
- This is n=30 diagnostic evidence only.
- No GSM8K run was performed.
- No n=100 run was performed.
- No final speedup, correctness, deployment, 8 GB, or end-to-end compression benefit claim is supported.

## Recommended Next Task

Task 74: QMSum concise-policy proxy triage and prompt tuning. Analyze Task 73 degraded proxy rows and tune the QMSum output policy before any QMSum n=100 run.

## Validation

Validation commands were run after code, report, and documentation updates. Results are summarized in the final response for Task 73.

Understand-Anything refresh was skipped because `/understand` is not available in this environment, and a broad graph refresh could scan forbidden archive/deprecated/backup paths.
