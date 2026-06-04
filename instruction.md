# CC-DFlash — Agent Instruction

> **Agent Operating Manual** · v5.1 (synced to Task 34) · 2026
> Read this file first. Do not duplicate content from canonical docs.

---

## Canonical Docs

| Document                          | Path                                       | Role                          |
| --------------------------------- | ------------------------------------------ | ----------------------------- |
| Research overview / paper context | `docs/CC-DFlash-Overview.html`             | Stable paper-style reference  |
| Live roadmap / task tracker       | `docs/Roadmap.html`                        | Updated after every task      |
| Task reports                      | `docs/reports/`                            | Chronological, numeric prefix |

---

## Project Rules

### Living Roadmap & Reports

- `docs/Roadmap.html` is the live project roadmap and **must be updated** when an agent completes or changes a task.
- Every meaningful agent task must also produce or update a chronological Markdown report under `docs/reports/`.
- `docs/reports/` files **must use chronological numeric prefixes** (e.g. `34-docs-restructure-roadmap-overview-report.md`).
- Every agent task must produce a **verification summary**.

### Forbidden Folders

- Archive, deprecated, and backup folders are **forbidden** unless the user explicitly names a file in one of them.
- Do not scan, grep, read, or index: `.archives/`, `archive/`, `archives/`, `backup/`, `backups/`, `old/`, `deprecated/`.

### Code Constraints

- Markdown code fences must remain **balanced**.
- Raw DFlash files are reference-only; **production split modules must not import `*_raw.py`**.
- Do not modify old artifacts (`results/`, `tests/fixtures/`) unless the task explicitly requests regeneration or replacement.
- Do not use vLLM, SGLang, Docker, or scale-up infrastructure unless the user explicitly requests it.
- Keep current project on **Transformers backend** only.
- Do not introduce Gemma4-E2B compressor into MVP.

### Claims Policy

- Do **not** claim final speedup.
- Do **not** claim final correctness.
- Do **not** claim deploy readiness.
- Do **not** claim confirmed 8 GB deployment.
- Do **not** claim compression has been proven useful end-to-end.
- Keep all benchmark/evidence claims **preliminary** unless an explicit numbered report proves otherwise.

---

## Current Project Summary

CC-DFlash adds an input-side context compression layer before the DFlash speculative decoding pipeline.

**Correct claim:**
```
lossy input compression + lossless speculative decoding on C_nén
≠ lossless full pipeline
```

**Core stack (MVP):**
- Target: `Qwen/Qwen3-4B` at 4-bit NF4
- Draft: `z-lab/Qwen3-4B-DFlash-b16` (~0.5B, BF16)
- Compressor: `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` (CPU, locked Task 20)
- Backend: `transformers==4.57.3` + `torch==2.9.1`
- `enable_thinking=False` is **mandatory and hard-locked** in all pipeline calls

**Module layout:**
```
src/ccdf/
  dflash/          ← split from z-lab/dflash (do not change logic)
  compression/     ← new module (LLMLingua wrapper, passthrough, base)
  pipeline/        ← CCDFlashPipeline connecting compression + dflash
  benchmark/       ← runner, metrics, conditions, datasets
  config/          ← config.yml loader
  utils/           ← timing, vram, logging
```

---

## Current Status (after Task 33, updated Task 34)

| Item                             | Status                               |
| -------------------------------- | ------------------------------------ |
| Phase 1 MVP pilot                | **PASS**                             |
| Phase 2 (controlled experiments) | **Conditional GO**                   |
| Phase 1 Complete                 | **NOT DONE**                         |
| Final benchmark n≥100            | **NOT DONE**                         |
| DFlash-R1                        | **KEEP_BASELINE**                    |
| LLMLingua-AR-R2                  | **KEEP_LOW_VRAM_BASELINE**           |
| CC-LLM-R2                        | **WATCHLIST**                        |
| CC-LLM-R3                        | **WATCHLIST**                        |
| LLMLingua-AR-R3                  | **DEPRIORITIZE_FOR_NOW**             |
| Baseline-AR                      | **Not implemented** (Tasks 37–38)    |
| T_prefill measurement            | **Not done** (Task 39)               |
| GSM8K+Wikipedia dataset          | **Not built** (Tasks 41–42)          |
| VRAM measurement                 | **Not done** — do not claim 8 GB fit |

---

## Current Next Task

**Task 35 — Manual Review Sample**

Review no-containment rows from Task 31 artifacts (`results/task31_*_text_n6.jsonl`).
For each NO_CONTAINMENT row, label it as one of:
- `TRUE_FAIL` — model generated a wrong answer
- `PARAPHRASE_OR_FORMAT_MISS` — answer was present but in different form
- `UNCLEAR` — cannot determine without additional context

Produce report: `docs/reports/35-manual-review-sample-report.md`

See `docs/Roadmap.html` for the full future task plan (Tasks 34–50).

---

## Validation Expectations

When an agent completes a task, it must run and include in its response:

```bash
# If code was changed:
python3 -m compileall src tests scripts 2>&1 | tail -20

# If code was changed and tests exist:
python3 -m pytest tests/ -x -q 2>&1 | tail -30

# If markdown changed — check fence balance (manual review):
# Every ``` opener must have a matching ``` closer

# If HTML docs changed — sanity check:
find docs -name "*.html" -print
find docs -name "*.html" -exec grep -L "<!DOCTYPE html>" {} \;
find docs -name "*.html" -exec grep -L "</html>" {} \;

# Always:
git diff --stat
git status --short
```

Final agent response must include:
1. Summary of files created or modified
2. Confirmation that no benchmarks, model loading, or results artifacts were touched
3. Validation summary (above checks)
4. `git status --short` output
5. `git diff --stat` output
6. List of changed files
