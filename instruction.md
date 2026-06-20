# CC-DFlash — Agent Instruction

> **Agent Operating Manual** · v5.2  
> Read this file first. Do not duplicate live task status from canonical docs.

---

## Canonical Sources

| Document                    | Path                           | Role                                                                                    |
| --------------------------- | ------------------------------ | --------------------------------------------------------------------------------------- |
| Live roadmap / task tracker | `docs/Roadmap.html`            | Source of truth for live task ledger, next task, reports, artifacts, phase gates        |
| Stable research context     | `docs/CC-DFlash-Overview.html` | Source of truth for research context, claims, architecture, risks, benchmark philosophy |
| Agent manual                | `instruction.md`               | Source of truth for agent behavior, rules, validation expectations                      |

---

## Active Agent Bootstrap

Before starting any meaningful task, read these sources in order:

1. `instruction.md`
2. `docs/Roadmap.html`
3. `docs/CC-DFlash-Overview.html`
4. The latest relevant task report under `docs/reports/`

Use `docs/Roadmap.html` to determine the current task, next task, task status, required report path, and expected artifacts.

Use `docs/CC-DFlash-Overview.html` to understand the project context, research claim, architecture, benchmark philosophy, and risks.

Use `instruction.md` to determine what is allowed, forbidden, and required during execution.

Do not use Understand-Anything commands. They are no longer part of the active workflow in this environment.

---

## Source of Truth Rules

- `instruction.md` controls agent behavior, forbidden actions, update rules, and validation expectations.
- `docs/Roadmap.html` controls task progress, live task status, next task, report index, artifact index, and phase gates.
- `docs/CC-DFlash-Overview.html` controls stable research context, claims, architecture, benchmark philosophy, and risks.
- Do not copy live task status into `instruction.md`.
- Do not duplicate the roadmap or research overview inside `instruction.md`.
- If task status is needed, read `docs/Roadmap.html`.
- If project context or claim policy is needed, read `docs/CC-DFlash-Overview.html`.

---

## Update Rules

- Update `docs/Roadmap.html` after every meaningful task.
- Create or update a numbered Markdown report under `docs/reports/` for every meaningful task.
- Update `docs/CC-DFlash-Overview.html` only when research interpretation, claims, architecture, benchmark policy, risks, or phase interpretation change.
- Update `instruction.md` only when agent rules, source-of-truth policy, validation expectations, or forbidden actions change.
- Do not update `instruction.md` merely because a task was completed.

---

## Agent Coordination

- `docs/Roadmap.html` is the source of truth for live task progress, task ledger, next task, reports, artifacts, and phase gates.
- `docs/CC-DFlash-Overview.html` is the source of truth for stable research context, claims, architecture, benchmark philosophy, and risks.
- `instruction.md` is the source of truth for agent behavior, forbidden actions, update rules, and validation expectations.
- If `docs/Roadmap.html` and the relevant reports disagree, verify the repository state with `git status`, `git diff`, and `git log` before updating docs.
- Update only with verified, objective facts.
- Do not overwrite or modify completed task logs or report index entries unless explicitly instructed.

## What To Update After Each Task

1. `docs/Roadmap.html`: update the task status, relevant artifact paths, next task, and update log.
2. `docs/reports/`: create or update a numbered report file for the task under the appropriate report folder.
3. `docs/CC-DFlash-Overview.html`: update only if research interpretation, claims, architecture, benchmark policy, or risks actually changed.

### Final Response Checklist

- Include a summary of files created or modified.
- Confirm whether benchmarks, model loading, or result artifacts were touched.
- Include a validation summary.
- Print `git status --short`.
- Print `git diff --stat`.
- List the changed files.

---

## Project Rules

### Forbidden Folders

- Archive, deprecated, and backup folders are forbidden unless the user explicitly names a file in one of them.
- Do not scan, grep, read, or index: `.archives/`, `archive/`, `archives/`, `backup/`, `backups/`, `old/`, `deprecated/`.

### Code Constraints

- Markdown code fences must remain balanced.
- Raw DFlash files are reference-only; production split modules must not import `*_raw.py`.
- Do not modify old artifacts in `results/` or `tests/fixtures/` unless the task explicitly requests regeneration or replacement.
- Do not use vLLM, SGLang, Docker, or scale-up infrastructure unless the user explicitly requests it.
- Keep the current project on the Transformers backend only.
- Do not introduce Gemma4-E2B compressor into MVP.

### Claims Policy

- Do not claim final speedup.
- Do not claim final correctness.
- Do not claim deploy readiness.
- Do not claim confirmed 8 GB deployment.
- Do not claim compression has been proven useful end-to-end.
- Keep all benchmark and evidence claims preliminary unless an explicit numbered report proves otherwise.

### Dataset Evaluation Policy

- CC-DFlash uses a two-dataset evaluation setup:
  - `gsm8k_short`: GSM8K short-context numeric QA for answer extraction / exact-match proxy.
  - `qmsum_meeting_qa_long`: QMSum-style meeting QA long-context data for speed, prefill, and compression-overhead evaluation.
- These are evaluation / benchmark datasets only; they are not training datasets.
- They are not official LLMLingua-2 paper benchmark reproduction datasets.
- GSM8K+Wikipedia augmented data is optional / legacy ablation only, not the main CC-DFlash dataset plan.
- For QMSum-style meeting QA, use containment / normalized-text proxy unless manual or LLM-judge evaluation is explicitly added and documented. Do not claim exact semantic correctness from this proxy.
- CC-DFlash remains an end-to-end hypothesis evaluation: compression is useful only if prefill savings plus DFlash decoding gain outweigh LLMLingua-2 `T_compress` while preserving quality.

### Frozen Post-Task-48 Benchmark Matrix

Use this matrix for the next benchmark phase unless `docs/Roadmap.html` or the user explicitly changes it:

| Dataset | Main role | Conditions | Primary metrics |
| --- | --- | --- | --- |
| `gsm8k_short` | Short-context numeric QA quality / answer extraction | Baseline-AR, DFlash-R1, LLMLingua-AR-R2, CC-DFlash-R2 / CC-LLM-R2 | numeric exact-match proxy, invalid output rate; latency and tok/s are secondary |
| `qmsum_meeting_qa_long` | Long-context speed / prefill / compression-overhead evaluation | Baseline-AR, DFlash-R1, LLMLingua-AR-R2, CC-DFlash-R2 / CC-LLM-R2 | end-to-end latency, `T_compress`, `T_prefill`, tok/s, compression ratio / input token reduction, `tau_mean`, VRAM |

Condition definitions:

- Baseline-AR: no compression, no DFlash, target autoregressive baseline.
- DFlash-R1: no compression, DFlash decoding, full prompt.
- LLMLingua-AR-R2: LLMLingua-2 compression, `keep_rate=0.5`, no DFlash; attribution baseline for compression-only benefit.
- CC-DFlash-R2 / CC-LLM-R2: LLMLingua-2 compression, `keep_rate=0.5`, DFlash decoding; main CC-DFlash condition.

Benchmark interpretation:

- Do not expect compression speedup to be strong on `gsm8k_short`; `T_compress` may dominate short-context prompts.
- Treat QMSum-style quality as normalized containment / long-answer proxy unless manual review or a semantic judge is explicitly added.
- Always report both generation-only metrics and approximate end-to-end metrics that include LLMLingua-2 `T_compress` for compressed conditions.
- Do not compare CC-DFlash against DFlash-R1 using generation-only tok/s alone; end-to-end latency is the conservative decision metric.
- Treat GSM8K `max_new_tokens=32` quality results as truncation-prone. For GSM8K quality calibration, report the output cap and generated-text retention; `max_new_tokens=128` is a safer calibration floor, `max_new_tokens=192` is more informative for final-answer calibration, and `max_new_tokens=256` is the current compressed GSM8K calibration default after Task 60. None of these caps proves that answer quality is solved.
- For GSM8K, numeric extraction is the primary deterministic quality proxy; exact containment is diagnostic only because short numeric answers can appear as unrelated intermediate numbers.
- GSM8K prompts must preserve the original question and end with a strict `Final answer: <number>` line instruction.
- For compressed GSM8K quality triage, store enough compressed-prompt metadata or safe excerpts in new artifacts when explicitly running a new calibration, so compression-loss claims can be audited directly.
- For compressed GSM8K, protect the strict final-answer instruction outside the compressible context, alongside the protected question or as an explicit post-compression suffix.
- Compressed GSM8K artifact rows should expose `protected_suffix_preserved`, `protected_suffix_preview`, `final_prompt_preview`, and `final_prompt_tail_preview` before larger quality runs.
- Before increasing compressed GSM8K sample size, output cap, or keep rate, verify suffix survival and prompt-tail evidence in a tiny compressed-only artifact.
- Task 61B verified `--keep-rate-percent 67` in tiny compressed GSM8K runs, but numeric extraction stayed 8/10 with both `FAIL_TO_PASS` and `PASS_TO_FAIL` row changes. Do not adopt `0.67` as the default R2 keep rate based on this alone.
- Task 62 changed-outcome triage found no direct preview evidence that `0.67` repaired compression loss; it also found k67 pass-to-fail regressions and one remaining truncation-limited same-fail row. Do not test `--keep-rate-percent 80` next.
- Task 63 n=30 default-R2 compressed GSM8K verification was stable versus Task 60 under a preliminary ±10 percentage point margin, but both compressed conditions had 5/30 token-cap hits. Triage failures and cap-hit rows before any n=100 run.
- Task 64 cap-hit triage labeled the remaining Task 63 cases as truncation-dominant or completed wrong-answer reasoning failures; no extraction-issue label was observed from available evidence. Treat the projected cap-fix upper bound as theoretical only, and run only a tiny `max_new_tokens=384` calibration before any n=100 move.
- Task 65 compressed-only GSM8K `max_new_tokens=384` calibration improved both compressed conditions to 24/30 numeric matches and reduced cap hits to 3/30, but added large latency cost and did not eliminate cap-hit failures. Treat `384` as a quality-calibration setting, not a blanket speed-benchmark default, until remaining failures are triaged.
- Task 66 reran the same compressed GSM8K `max_new_tokens=384` calibration under a cleaner preflight. Quality and cap-hit counts reproduced, but Task 65 latency was noisy and should not be used for mnt384 latency interpretation. Still triage remaining failures before any n=100 move.
- Task 67 triaged persistent Task 66 mnt384 failures as an even split between remaining truncation and completed wrong-answer reasoning, with no extraction-fix or compression-loss label from available previews. Do not automatically increase to mnt512; synthesize Tasks 60–67 before any n=100 move. Use mnt256 as the speed-oriented compressed GSM8K setting and mnt384 as the quality-oriented compressed GSM8K setting.
- Task 68 froze final compressed GSM8K settings: speed-oriented uses `keep_rate=0.50`, `max_new_tokens=256`, and protected suffix; quality-oriented uses `keep_rate=0.50`, `max_new_tokens=384`, and protected suffix. Reject `keep_rate=0.67` as default, defer `0.75/0.80`, defer `max_new_tokens=512`, and run a comparable n=30 full GSM8K matrix before any n=100 move.
- Task 69 completed the comparable GSM8K n=30 full matrix at the quality-oriented setting. CC-DFlash-R2 matched LLMLingua-AR-R2 quality and improved e2e speed versus LLMLingua-AR-R2, but DFlash-R1 remains faster on short-context GSM8K. A bounded GSM8K n=100 full matrix is conditionally justified by the GSM8K evidence, still preliminary and not a final speedup/correctness claim.
- Task 70 audited existing QMSum long-context artifacts. The Task 51 n=10 QMSum matrix is sufficient for read-only diagnosis but stale for current long-context policy because every row uses `max_new_tokens=32` and most rows hit the cap. QMSum does not test GSM8K-style arithmetic failure; run a fresh QMSum n=30 diagnostic before larger long-context claims.
- Task 71 ran the fresh QMSum n=30 full matrix at `max_new_tokens=384`. CC-DFlash-R2 beat LLMLingua-AR-R2 on e2e speed and matched its normalized-overlap proxy, but compressed rows still hit the cap often. Do not jump directly to QMSum n=100; triage QMSum cap-hit rows and long-answer proxy behavior first.
- Task 72 triaged Task 71 QMSum cap-hit rows and found mostly long-answer cap pressure / truncation-like behavior in compressed outputs. This does not resemble GSM8K numeric-answer failure. Do not run QMSum n=100 next; use a bounded compressed-only QMSum follow-up with prompt-style refinement and/or tiny `max_new_tokens=512` calibration before any larger long-context run.
- Task 73 added a QMSum concise-answer protected suffix and ran compressed-only n=30 at `max_new_tokens=384`. Cap hits dropped to zero for both compressed conditions, but normalized-overlap proxy quality dropped materially. Do not freeze the concise QMSum policy as final or run QMSum n=100 until degraded proxy rows and prompt wording are triaged.
- Task 74 triaged the Task 73 QMSum concise-policy proxy drop and found that most concise rows are too short or unsupported by lexical evidence, not merely harmless proxy mismatch. Keep the protected-suffix mechanism, but revise to a balanced QMSum answer policy before any QMSum n=100 run. `max_new_tokens=512` is not needed while cap hits are already zero.
- Task 75 replaced the terse QMSum 1-3 sentence suffix with a balanced 3-6 sentence protected suffix and ran compressed-only n=30 calibration at `max_new_tokens=384`. Cap hits stayed at zero and lexical overlap improved versus the terse policy, but most rows remained too short or unsupported by the current proxy. Do not run QMSum n=100 yet; run another bounded QMSum policy/proxy follow-up.
- If compressed GSM8K rows still do not emit `Final answer:` markers or keep hitting the token cap, inspect compressed prompt/context previews and prompt-tail evidence before increasing sample size.
- Run tiny dry-run/smoke execution on both datasets before any full n=100 benchmark.
- For benchmark smoke runs, use unique `results/phase_1_system_build_and_evaluation/early_experiments/taskNN_*` output filenames, prefer `--resume`, avoid `--overwrite`, and store generated text when quality/audit work will follow.
- Run the lighter dataset/condition sequence first, then expand only after stable completion; long-context DFlash/CC-DFlash paths may be deferred if runtime or VRAM risk is high.
- After any staged benchmark expansion, audit the new JSONL artifacts and summarize metrics before launching another larger benchmark run.

### Validation Expectations

- Every meaningful agent task must produce a verification summary.
- If code was changed, run compile checks before completion.
- If tests exist for the changed area, run the relevant tests before completion.
- If Markdown changed, check fence balance before completion.
- If HTML docs changed, sanity-check the HTML structure before completion.
- Always report `git diff --stat` and `git status --short` in the final response.

---

## Final Response Format

Final agent response must include:

1. Summary of files created or modified
2. Whether benchmarks, model loading, or result artifacts were touched
3. Validation summary
4. `git status --short` output
5. `git diff --stat` output
6. List of changed files
