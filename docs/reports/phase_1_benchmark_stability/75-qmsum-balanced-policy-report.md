# Task 75 — QMSum Balanced-Answer Policy Calibration

Date: 2026-06-13

Status: PASS_WITH_NOTES

## Scope

Task 75 replaced the Task 73 QMSum-only terse protected suffix with a balanced answer policy, then ran bounded compressed-only QMSum calibration at `n=30`, `max_new_tokens=384`, `seed=42`.

This is preliminary prompt-policy calibration only. It is not a final benchmark, not a final correctness claim, and not evidence of production readiness.

## Task 74 Commit

Task 74 was committed before this task:

- Commit: `8ee61cd test: triage qmsum concise proxy degradation`

## Prompt / Output Policy Change

Previous active QMSum suffix:

```text
Answer concisely in 1-3 sentences.
Do not repeat the full context.
Do not include long reasoning.
Use only information supported by the meeting context.
```

New active QMSum suffix:

```text
Answer in 3-6 concise sentences.
Include the key entities, decisions, reasons, and supporting details needed to answer the question.
Do not repeat the full context.
Do not include unrelated meeting details.
Use only information supported by the meeting context.
```

The suffix remains protected outside LLMLingua compression. GSM8K still uses its separate strict `Final answer: <number>` suffix.

New compressed QMSum metadata fields:

- `qmsum_answer_policy_enabled`
- `qmsum_answer_policy_type = "balanced"`
- `qmsum_answer_policy_preserved`
- `qmsum_output_policy_preview`
- existing `final_prompt_tail_preview`

## Commands Run

Prompt dry-run:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --n 3 --seed 42 --dry-run-prompts
```

Bounded real runs:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition LLMLingua-AR-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task75_qmsum_long_llmlingua_ar_r2_n30_mnt384_balanced.jsonl --resume --store-generated-text
```

```bash
PYTHONPATH=src .venv/bin/python scripts/run_mvp.py --prompt-source dataset --dataset qmsum_meeting_qa_long --condition CC-DFlash-R2 --n 30 --seed 42 --max-new-tokens 384 --output results/task75_qmsum_long_cc_dflash_r2_n30_mnt384_balanced.jsonl --resume --store-generated-text
```

Analysis:

```bash
PYTHONPATH=src .venv/bin/python scripts/phase_1_analysis/analyze_task75_qmsum_balanced_policy.py
```

## Artifacts

| Artifact | Rows / scope |
| --- | ---: |
| `results/task75_qmsum_long_llmlingua_ar_r2_n30_mnt384_balanced.jsonl` | 30 |
| `results/task75_qmsum_long_cc_dflash_r2_n30_mnt384_balanced.jsonl` | 30 |
| `results/task75_qmsum_balanced_policy_summary.json` | 3 stages × 2 conditions |
| `results/task75_qmsum_balanced_policy_table.csv` | 6 metric rows |
| `results/task75_qmsum_balanced_policy_cases.jsonl` | 60 case rows |

Both real runs used `--resume` and did not use `--overwrite`.

## Row Counts

| Condition | Rows | Policy preserved | Cap hits |
| --- | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 30 | 30/30 | 0/30 |
| CC-DFlash-R2 | 30 | 30/30 | 0/30 |

## Cap-Hit Comparison

| Condition | Task 71 original | Task 73 terse | Task 75 balanced |
| --- | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 22/30 | 0/30 | 0/30 |
| CC-DFlash-R2 | 21/30 | 0/30 | 0/30 |

The balanced policy did not reintroduce cap pressure. `max_new_tokens=512` is not justified by this calibration.

## Proxy Quality Comparison

Average normalized overlap:

| Condition | Task 71 original | Task 73 terse | Task 75 balanced | Balanced vs terse | Balanced vs original |
| --- | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | 0.358644 | 0.227541 | 0.261336 | +0.033795 | -0.097308 |
| CC-DFlash-R2 | 0.357483 | 0.228499 | 0.259867 | +0.031368 | -0.097616 |

Balanced wording recovered some lexical overlap compared with the terse suffix, but remained materially below the original long-answer outputs. Because QMSum uses a lexical proxy, this is directional only and not a semantic correctness judgment.

## Speed / Latency Comparison

Approximate e2e latency includes generation time plus `t_compress_ms`.

| Condition | Stage | Avg output tokens | Avg e2e seconds | E2E tok/s | Avg `t_compress_ms` | Avg compression ratio |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| LLMLingua-AR-R2 | Task 71 original | 348.53 | 26.38 | 13.21 | 5846.40 | 2.07 |
| LLMLingua-AR-R2 | Task 73 terse | 48.50 | 8.04 | 6.03 | 5155.60 | 2.07 |
| LLMLingua-AR-R2 | Task 75 balanced | 91.00 | 10.48 | 8.69 | 5255.84 | 2.07 |
| CC-DFlash-R2 | Task 71 original | 345.33 | 19.06 | 18.12 | 5928.33 | 2.07 |
| CC-DFlash-R2 | Task 73 terse | 48.67 | 7.58 | 6.42 | 5226.33 | 2.07 |
| CC-DFlash-R2 | Task 75 balanced | 92.50 | 9.48 | 9.75 | 5296.27 | 2.07 |

Balanced outputs are longer than terse outputs and therefore slower than Task 73, but remain much shorter than Task 71 original capped long-answer outputs.

## Case Labels

| Label | Count |
| --- | ---: |
| `STILL_TOO_SHORT` | 49 |
| `UNCLEAR` | 7 |
| `ACCEPTABLE_BALANCED_ANSWER` | 2 |
| `PROXY_WEAKNESS` | 2 |

By condition:

| Condition | Label counts |
| --- | --- |
| LLMLingua-AR-R2 | `STILL_TOO_SHORT`: 24, `UNCLEAR`: 4, `ACCEPTABLE_BALANCED_ANSWER`: 1, `PROXY_WEAKNESS`: 1 |
| CC-DFlash-R2 | `STILL_TOO_SHORT`: 25, `UNCLEAR`: 3, `ACCEPTABLE_BALANCED_ANSWER`: 1, `PROXY_WEAKNESS`: 1 |

## Representative Examples

`ACCEPTABLE_BALANCED_ANSWER`:

- Prompt 15, both compressed conditions.
- Reference mentions the 25 Euro selling price, 50 million Euro profit aim, four million selling target, and remote-control design goals.
- Balanced outputs include the price/profit target and design focus, while avoiding the full-context repetition.

`PROXY_WEAKNESS`:

- Prompt 10, both compressed conditions.
- Reference is short: original, trendy, easy to use, international, and not too expensive.
- Balanced outputs discuss an international, user-friendly remote-control plan with price and design detail. Lexical proxy remains imperfect for this style of paraphrase.

`STILL_TOO_SHORT`:

- Prompt 1, both compressed conditions.
- Reference explains speech/gesture recognition, convenience when the controller is lost, reliability caveat, and product-differentiation motivation.
- Balanced output mentions intelligent controller and innovation but omits several reference-specific motivations.

`UNCLEAR`:

- Prompt 3 and prompt 8 examples.
- Outputs are on-topic and often useful, but lexical evidence is not strong enough to classify them as recovered details or true degradation without manual/semantic review.

## Decision

Balanced policy should be revised, not rejected outright and not frozen as final.

Reasons:

- It preserves the protected suffix in 60/60 compressed rows.
- It keeps cap hits at 0/60.
- It improves average normalized overlap versus the terse Task 73 policy.
- It still leaves most cases labeled `STILL_TOO_SHORT` under the current lexical proxy.

`max_new_tokens=512` is not needed while cap hits are zero. QMSum n=100 is not justified yet. The next task should refine the QMSum policy/proxy path, likely by requiring more explicit supporting details or adding a small manual-review/semantic-quality check rather than only changing token budget.

## Understand-Anything

Understand-Anything refresh was skipped because `/understand` is not available in this environment.

## Validation

Validation was run after code, test, artifact, and documentation changes. See final task response for exact command results.

## Limitations

- QMSum quality is still measured with lexical proxy diagnostics, not semantic correctness.
- Only compressed conditions were rerun.
- `n=30` is still a bounded calibration, not a final benchmark.
- Latency values are preliminary and may vary by environment.
- No n=100 run was performed.
