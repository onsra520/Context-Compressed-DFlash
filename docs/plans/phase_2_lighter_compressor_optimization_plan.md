# Phase 2 Lighter Compressor Optimization Plan

## Goal & Framing

Phase 2 focuses on making the compressed CC-DFlash path faster, rather than avoiding compression.

### Core Research Question

When compression is required under the same compression budget, can a lighter compressor reduce $T_{\text{compress}}$ and bring CC-DFlash-R2 E2E latency/tok/s closer to DFlash-R1, while preserving quality proxy near Baseline-AR?

### Framing & Context

- Phase 1 showed that the compressed path can preserve benchmark quality proxies near Baseline-AR in the current controlled setting.
- The remaining weakness is E2E latency: CC-DFlash-R2 is slower than DFlash-R1 mainly because $T_{\text{compress}}$ is large.
- Phase 2 therefore targets $T_{\text{compress}}$ reduction through a lighter compressor while keeping the same compression budget and quality-proxy constraints.

### The Lighter Compressor Tradeoff

Lighter compressor is a double-edged tradeoff:

- It may reduce $T_{\text{compress}}$.
- But it may compress less effectively or lose answer-critical tokens.

Therefore, it must be accepted only if it is faster, compresses enough, and preserves quality proxy.

### Secondary Notes & Rejected Alternatives (Non-Main Focus)

- **Adaptive routing to avoid compression:** Considered secondary; may be discussed as an ablation/alternative but is not the main Phase 2 direction.
- **Offline/cached compression:** Not the main solution; online latency reduction via a lighter compressor is the priority.
- **Skipping compression for short prompts:** Secondary; not the main result.

---

## Freeze Items

To ensure controlled and reproducible comparison with Phase 1, the following parameters are frozen:

- **Dataset:**
  - `data/eval/gsm8k_100.jsonl`
  - `data/eval/qmsum_meeting_qa_100.jsonl`

- **Seed / sample order:**
  - `seed = 42`
  - Fixed canonical eval order

- **Target model / DFlash setup:**
  - Unchanged from Task88/Task90
  - Do not modify DFlash logic during T91 planning

- **Prompt format:**
  - Unchanged canonical GSM8K and QMSum prompt templates

- **Generation config:**
  - Deterministic generation setting
  - Same `max_new_tokens` / output cap as controlled Phase 1 reruns unless explicitly justified later

- **Compression budget:**
  - `max_cut_token = 368`
  - Same `keep_rate` / token-reduction target across compressors

- **Preserve policy:**
  - Preserve instruction/question/final-answer format
  - Do not allow compressor to remove answer-format instruction
  - Preserve numeric/entity/speaker/topic/action cues when guard is introduced later

- **Runtime reporting:**
  - Report CPU compressor mode and GPU compressor mode separately
  - Do not mix CPU/GPU metrics into one claim

- **Claim boundary:**
  - No universal speedup claim
  - No final correctness claim
  - No QMSum semantic correctness claim
  - No deployment readiness claim
  - No confirmed 8GB claim
  - No DFlash-R1 broken claim

---

## Acceptance Gate for Lighter Compressor

A lighter compressor candidate can be adopted only if:

1. **Runtime:**
   $T_{\text{compress}}$ decreases clearly compared with the large compressor.

2. **Compression:**
   Token reduction reaches the same or near-same compression target. It must not appear faster only because it compresses less.

3. **Quality:**
   GSM8K numeric proxy does not drop sharply. QMSum diagnostic proxy does not become clearly worse. Empty/generic/too-short outputs do not increase materially.

4. **Stability:**
   No OOM, segfault, or severe runtime-order instability under the tested 8GB setup.

5. **Speed target:**
   CC-DFlash-R2 E2E latency / E2E tok/s moves closer to DFlash-R1 than the Phase 1 large-compressor setting.

---

## Main Technical Task Roadmap (T91–T100)

### T91 — Lighter Compressor Feasibility Setup

- **Purpose:** Identify lighter compressor candidate, freeze benchmark budget/config, and prepare feasibility checks.
- **Current Compressor:** `llmlingua-2-xlm-roberta-large-meetingbank`
- **Candidate Lighter Compressor:** `llmlingua-2-bert-base-multilingual-cased-meetingbank`
- **Status:** NEXT

### T92 — Lighter Compressor Integration

- **Purpose:** Add runner/config support for the lighter compressor without breaking the existing large-compressor path.
- **Status:** PLANNED

### T93 — Compression Rate / Budget Calibration

- **Purpose:** Compare large vs lighter compressor under the same compression budget, including `max_cut_token=368` and same `keep_rate`/token-reduction target.
- **Status:** PLANNED

### T94 — Quality Proxy Calibration

- **Purpose:** Measure whether lighter-compressor outputs preserve GSM8K numeric proxy and QMSum diagnostic proxy near Baseline-AR / existing large-compressor behavior.
- **Status:** PLANNED

### T95 — GPU Co-resident Feasibility under 8GB

- **Purpose:** Check whether the lighter compressor can run on GPU with target/DFlash under 8GB without OOM, segfault, or harmful runtime instability.
- **Status:** PLANNED

### T96 — Controlled n=10 Optimized CC-DFlash Rerun

- **Purpose:** Run controlled n=10 benchmark with the best validated lighter-compressor setting.
- **Status:** PLANNED

### T97 — Controlled n=30 Phase 2 Benchmark

- **Purpose:** If T96 passes, run controlled n=30 Phase 2 benchmark and compare against Task88 evidence.
- **Status:** PLANNED

### T98 — Phase 2 Optimization Summary

- **Purpose:** Summarize quality-speed-compression tradeoff from the optimized compressed path.
- **Status:** PLANNED

### T99 — Final Claim Boundary Audit

- **Purpose:** Audit which claims are supported and which must remain out of scope.
- **Status:** PLANNED

### T100 — Final Report Integration

- **Purpose:** Integrate Phase 2 result into final report/demo materials.
- **Status:** PLANNED
