# CC-DFlash Reconstruction Plan

**Phạm vi:** `Rec-T02A` đến `Rec-T04B`  
**Trạng thái ban đầu:** `PLANNED`  
**Nguồn tham chiếu lịch sử:** `.archives/20260711-043859/project/`  
**Runtime canonical mới:** source được xây lại ngoài `.archives/`  
**Roadmap canonical:** Markdown này; không tiếp tục cập nhật `docs/ROADMAP.html`

---

## 1. Nguyên tắc Reconstruction

1. `.archives/20260711-043859/project/` chỉ dùng để đọc, audit và lấy lại có chọn lọc các module đã xác minh.
2. Không sao chép nguyên khối runtime, benchmark glue, dataset glue hoặc metric aggregation cũ.
3. Mỗi task chỉ ghi artifact vào đúng folder của task:

```text
results/
└── Rec-TxxY/
    ├── logs/
    ├── reports/
    ├── *.json
    ├── *.csv
    └── Rec-TxxY1-*/
```

4. Không ghi đè artifact lịch sử từ Phase 1, Phase 2, T105B, T106B, T114H hoặc T115.
5. Không dùng notebook làm source of truth.
6. Model chỉ được load từ local path đã khóa trong `models/MODEL_LOCK.json`.
7. Mọi benchmark phải ghi dataset hash, model revision, prompt hash, resolved config và source commit.
8. Benchmark mode và profiling mode phải tách biệt.
9. Không dùng metric có tên mơ hồ như `accepted_tokens` nếu semantic thực là “tokens advanced”.
10. Không claim QMSum semantic correctness; QMSum chỉ dùng quality proxy và failure analysis trong phạm vi đã định nghĩa.

---

## 2. Tổng quan task

| Task        | Title                                    | Phụ thuộc   | Output quyết định                                                      |
| ----------- | ---------------------------------------- | ----------- | ---------------------------------------------------------------------- |
| `Rec-T02A`  | Dataset Pipeline Reconstruction          | `Rec-T01B`  | Frozen GSM8K/QMSum với stable IDs, lineage và nested subsets           |
| `Rec-T02B`  | Benchmark Contract Reconstruction        | `Rec-T02A`  | Benchmark runner, metric schema, timing contract và process isolation  |
| `Rec-T02B1` | Single-Prompt Runner                     | `Rec-T02B`  | CLI chạy một prompt/fixture để test và demo                            |
| `Rec-T03A`  | Baseline-AR and DFlash-R1 Reconstruction | `Rec-T02B1` | Runtime AR/DFlash sạch, test được, không mang benchmark glue cũ        |
| `Rec-T03B`  | Baseline-AR and DFlash-R1 Audit n=10     | `Rec-T03A`  | Kết quả n=10 trên hai dataset và quyết định có được đi tiếp            |
| `Rec-T04A`  | Compression Architecture Reconstruction  | `Rec-T03B`  | Structured compression path, prompt invariants và metric contract đúng |
| `Rec-T04B`  | CC-DFlash Audit and Benchmark n=30       | `Rec-T04A`  | Benchmark ba condition trên cùng frozen n=30                           |

---

# Rec-T02A — Dataset Pipeline Reconstruction

## Mục tiêu

Xây lại pipeline dataset có thể tái hiện, kiểm chứng được provenance và bảo đảm cùng một fixture ID luôn đại diện cho cùng một nội dung.

Hai dataset canonical:

- `GSM8K`: short-context numeric reasoning.
- `QMSum`: long-context meeting QA.

## Phạm vi

### A. Source lock

Mỗi nguồn phải có:

- dataset/repository identity;
- upstream revision hoặc commit SHA;
- file URL cụ thể;
- SHA-256 của raw source;
- thời điểm fetch;
- builder version;
- license/source note.

Không tải từ branch động như `master` mà không ghi commit đã resolve.

### B. Stable fixture identity

Không tạo ID theo vị trí sau random sample.

**GSM8K** dùng split, upstream row identity và content hash. Ví dụ:

```text
gsm8k_test_004291_a13f9c2d
```

**QMSum** dùng meeting ID, query type, query index và content hash. Ví dụ:

```text
qmsum_ami_ES2002a_specific_03_5f71c9b2
```

### C. Pipeline stages

```text
data/
├── raw/
│   ├── gsm8k/
│   └── qmsum/
├── processed/
│   ├── gsm8k/
│   └── qmsum/
├── eval/
│   ├── gsm8k/
│   └── qmsum/
└── manifests/
```

Mỗi stage phải có manifest chứa input hash và output hash. Pipeline phải từ chối chạy nếu lineage không khớp.

### D. QMSum corrections

- Không dùng `specific_query_list or general_query_list`.
- Policy chọn query phải explicit: `specific_only`, `general_only` hoặc `specific_and_general`.
- Không flatten toàn bộ speaker/newline một cách âm thầm.
- Truncation phải ghi original length, retained length, boundary và strategy.
- Không vô tình overweight meeting có nhiều QA.
- Không giữ reference như evidence-complete nếu context bị cắt mất phần liên quan mà không ghi caveat.

### E. Nested frozen subsets

```text
n10  = 10 fixture đầu
n30  = 30 fixture đầu
n100 = 100 fixture đầu
```

Bắt buộc:

```text
n10 ⊂ n30 ⊂ n100
```

Không được sample lại riêng cho từng `n`.

### F. Safe write policy

- Builder chỉ ghi vào staging.
- Chỉ lệnh freeze mới được ghi vào `data/eval/`.
- Không có default command nào được phép overwrite canonical dataset.
- Freeze phải yêu cầu flag rõ ràng, ví dụ:

```bash
python -m ccdf.datasets freeze --dataset qmsum --confirm-freeze
```

## Source đề xuất

```text
src/ccdf/datasets/
├── __init__.py
├── schemas.py
├── source_lock.py
├── gsm8k.py
├── qmsum.py
├── pipeline.py
├── freeze.py
├── manifests.py
└── validation.py
```

## Subtasks đề xuất

### Rec-T02A1 — Source and schema lock

- định nghĩa schema raw/processed/eval;
- định nghĩa source lock;
- định nghĩa stable ID;
- tạo validation tests.

### Rec-T02A2 — GSM8K builder

- fetch/process/freeze;
- final-answer reference extraction;
- stable IDs;
- nested subsets.

### Rec-T02A3 — QMSum builder

- pin source revision;
- preserve meeting structure;
- explicit query policy;
- truncation audit;
- stable IDs;
- nested subsets.

### Rec-T02A4 — Reproducibility audit

Chạy pipeline hai lần trong hai staging folder khác nhau và yêu cầu:

- byte-identical manifests;
- identical fixture order;
- identical content hashes;
- identical n10/n30/n100 membership.

## Required artifacts

```text
results/Rec-T02A/
├── reports/
│   └── report.md
├── source_lock.json
├── dataset_schema.json
├── dataset_lineage.json
├── frozen_subset_manifest.json
├── fixture_inventory.csv
├── reproducibility_audit.json
├── truncation_audit.csv
└── logs/
```

## Tests

- stable ID không đổi khi run lại;
- thay đổi content phải đổi content hash/ID;
- raw hash mismatch làm pipeline fail;
- processed lineage mismatch làm freeze fail;
- n10/n30/n100 lồng nhau;
- không có duplicate fixture ID;
- canonical file không bị overwrite nếu thiếu `--confirm-freeze`;
- source revision và SHA bắt buộc tồn tại.

## PASS gate

- GSM8K và QMSum đều có source lock;
- stable IDs được kiểm;
- nested subsets đúng;
- reproducibility audit pass;
- canonical eval hash được ghi vào manifest;
- không còn đường mặc định overwrite dataset;
- QMSum query/truncation policy được ghi rõ;
- report liệt kê mọi caveat còn lại.

## STOP conditions

- upstream source không resolve được revision;
- cùng fixture ID nhưng content khác;
- freeze không tái hiện byte-level;
- subset không lồng nhau;
- pipeline dùng cache không xác định lineage;
- QMSum structure bị flatten/truncate mà không có audit.

---

# Rec-T02B — Benchmark Contract Reconstruction

## Mục tiêu

Xây benchmark runner mới có contract rõ ràng, không trộn runtime, profiling, evaluator và summary.

## Kiến trúc bắt buộc

```text
src/ccdf/
├── benchmark/
│   ├── schemas.py
│   ├── runner.py
│   ├── execution.py
│   ├── process_isolation.py
│   ├── timing.py
│   ├── vram.py
│   ├── aggregation.py
│   └── validation.py
├── evaluation/
│   ├── gsm8k.py
│   └── qmsum.py
├── metrics/
│   ├── common.py
│   ├── dflash.py
│   └── compression.py
└── artifacts/
    ├── writer.py
    └── manifests.py
```

## Tách bốn lớp

1. **Execution:** gọi condition và nhận raw result.
2. **Measurement:** timing, VRAM, token counts, DFlash counters.
3. **Evaluation:** GSM8K numeric evaluator và QMSum proxy.
4. **Aggregation:** per-row thành dataset summary.

Không lớp nào được âm thầm sửa field của lớp trước.

## Condition contract

Mỗi condition phải resolve thành config đầy đủ:

```text
condition_id
target_model_lock_id
draft_model_lock_id
compressor_model_lock_id
tokenizer_source
generation_mode
max_new_tokens
temperature
block_size
enable_thinking
stop_token_ids
attention_backend
quantization_mode
dataset_manifest_hash
prompt_policy_id
```

## Per-row artifact contract

Mỗi JSONL row tối thiểu có:

### Identity

```text
run_id
task_id
dataset
dataset_manifest_hash
fixture_id
fixture_content_hash
condition
source_commit
resolved_config_hash
```

### Prompt

```text
prompt_policy_id
structured_prompt_parts_hash
precompression_prompt_hash
final_prompt_hash
input_tokens_precompression
input_tokens_final
```

### Output

```text
generated_text
generated_text_hash
output_token_ids_hash
output_tokens
stop_reason
cap_hit
success
error
```

### Timing

```text
model_init_ms
compressor_init_ms
compression_total_ms
target_prefill_ms
draft_prefill_ms
decode_total_ms
request_e2e_ms
```

Detailed profiling fields chỉ xuất hiện trong profiling mode:

```text
draft_proposal_ms
target_verification_ms
cache_management_ms
synchronization_overhead_ms
```

### VRAM

```text
peak_allocated_bytes
peak_reserved_bytes
measurement_scope
```

### DFlash

```text
verification_calls
acceptance_lengths
tau_tokens_advanced_per_verification
draft_tokens_proposed
accepted_draft_tokens
draft_acceptance_rate
rollback_tokens
```

## DFlash invariants

```text
verification_calls == len(acceptance_lengths)

tokens_advanced == sum(acceptance_lengths)

accepted_draft_tokens
== tokens_advanced - verification_calls

rollback_tokens
== draft_tokens_proposed - accepted_draft_tokens
```

Không gọi `tokens_advanced` là pure `accepted_tokens`.

## Aggregation contract

Phải báo cả:

```text
mean_per_row_tau
global_weighted_tau
```

Trong đó:

```text
mean_per_row_tau = mean(row_tau)
global_weighted_tau = sum(tokens_advanced) / sum(verification_calls)
```

## Benchmark mode và profiling mode

### Benchmark mode

- chỉ synchronize ở boundary cần thiết;
- không đặt sync trước/sau mỗi draft/verification;
- dùng để báo latency chính thức;
- process isolation cho từng condition;
- warmup policy giống nhau.

### Profiling mode

- cho phép instrumentation sâu;
- latency không được đưa vào bảng benchmark chính;
- artifact phải ghi `measurement_mode=profiling`.

## Process isolation

Mỗi condition chạy trong process riêng:

```text
load model
warmup
run rows
write artifact
release process
```

Không reuse process giữa Baseline, DFlash và CC-DFlash trong benchmark canonical.

## Evaluator contract

### GSM8K

- extract numeric final answer;
- xử lý dấu phẩy, currency, integer/decimal hợp lệ;
- phân loại strict correct, wrong numeric, invalid và cap-limited incomplete;
- evaluator version/hash phải được ghi.

### QMSum

Chỉ dùng proxy đã định nghĩa rõ:

- reference recall;
- reference precision;
- invalid/cap-hit;
- output length;
- optional lexical coverage.

Không claim semantic correctness.

## Required artifacts

```text
results/Rec-T02B/
├── reports/
│   └── report.md
├── benchmark_schema.json
├── metric_contract.json
├── timing_contract.json
├── evaluator_contract.json
├── process_isolation_audit.json
├── synthetic_rows.jsonl
├── synthetic_summary.json
└── logs/
```

## Tests

- schema round-trip;
- invalid row bị reject;
- field scope không trộn tokenizer;
- benchmark/profiling mode tách biệt;
- DFlash invariants;
- weighted/unweighted tau;
- process isolation;
- evaluator deterministic;
- summary chỉ đọc run artifact cùng manifest/config hash;
- không merge stale artifact.

## PASS gate

- benchmark schema ổn định;
- timing boundary được mô tả và test;
- process isolation pass;
- DFlash metric invariants pass;
- evaluator deterministic;
- artifact writer atomic;
- summary từ synthetic fixture chính xác;
- benchmark mode không có per-iteration synchronization instrumentation.

---

# Rec-T02B1 — Single-Prompt Runner

## Mục tiêu

Tạo đường chạy nhỏ nhất cho debug, kiểm tra và demo mà không cần benchmark dataset.

## CLI dự kiến

```bash
ccdf run --condition baseline-ar --prompt "How many positive divisors does 196 have?"
```

```bash
ccdf run --condition dflash-r1 --prompt "How many positive divisors does 196 have?"
```

```bash
ccdf run   --condition cc-dflash-r2   --context-file meeting.txt   --question "What decision was made?"
```

```bash
ccdf run   --condition dflash-r1   --dataset qmsum   --fixture-id qmsum_...   --format json
```

Profiling:

```bash
ccdf run   --condition dflash-r1   --dataset qmsum   --fixture-id qmsum_...   --profile   --format json
```

## Output mặc định

```text
Condition
Answer
Input tokens
Output tokens
Request latency
Generation tok/s
Stop reason
```

## Yêu cầu

- cùng runtime path với benchmark;
- không có implementation riêng cho demo;
- hỗ trợ local-only models;
- exit code khác 0 khi validation fail;
- không tự ghi vào canonical benchmark results;
- khi có `--save`, ghi vào `results/Rec-T02B1/`.

## Required artifacts

```text
results/Rec-T02B1/
├── reports/
│   └── report.md
├── cli_contract.json
├── smoke_baseline.json
├── smoke_dflash.json
└── logs/
```

## PASS gate

- chạy được prompt trực tiếp;
- chạy được canonical fixture;
- text và JSON mode hoạt động;
- benchmark và single-prompt dùng cùng runtime function;
- profile mode được đánh dấu rõ;
- không cần notebook để demo.

---

# Rec-T03A — Baseline-AR and DFlash-R1 Reconstruction

## Mục tiêu

Đưa lại Baseline-AR và DFlash-R1 bằng cách lấy có chọn lọc các module đã audit từ archive, đồng thời loại bỏ runtime glue và instrumentation lỗi.

## Model contract

### Target

```text
models/target/unsloth--Qwen3-4B-bnb-4bit
```

- Qwen3-4B;
- BitsAndBytes NF4 4-bit;
- BF16 compute theo config đã khóa;
- dùng giống hệt nhau cho Baseline và DFlash.

### Drafter

```text
models/drafter/z-lab--Qwen3-4B-DFlash-b16
```

- Qwen3-4B DFlash;
- block size 16;
- non-thinking;
- target layer IDs phải khớp checkpoint.

### Tokenizer

Tokenizer phải resolve từ target model lock. Không dùng tokenizer khác giữa hai conditions.

## Module được phép phục hồi

Chỉ sau khi diff với upstream và có test:

```text
dflash/model.py
dflash/attention.py
dflash/generate.py
dflash/utils.py
dflash/loader.py
```

Không phục hồi:

- old `run_mvp.py`;
- old benchmark runner;
- old dataset glue;
- old summary/aggregation;
- old timing wrappers.

## Source đề xuất

```text
src/ccdf/inference/
├── __init__.py
├── schemas.py
├── model_registry.py
├── target_loader.py
├── baseline_ar.py
├── dflash_runtime.py
└── generation_common.py

src/ccdf/dflash/
├── __init__.py
├── model.py
├── attention.py
├── generate.py
├── utils.py
└── loader.py
```

## Correctness requirements

### Baseline-AR

- greedy decoding khi `temperature=0`;
- same chat template;
- `enable_thinking=False`;
- EOS/stop đúng;
- max token cap rõ;
- chỉ một target prefill;
- không detached prefill measurement.

### DFlash-R1

- same target model và tokenizer;
- draft checkpoint đúng;
- block size 16;
- acceptance prefix logic khớp upstream;
- target/draft cache crop đúng;
- final partial block đúng;
- EOS/stop không scan sai vùng buffer;
- statistics không thay đổi output trajectory.

## Instrumentation design

Core generation trả raw counters nhưng không tự synchronize chi tiết trong benchmark mode.

Có thể dùng profiler riêng:

```text
NoOpProfiler
CudaComponentProfiler
```

Benchmark mode dùng `NoOpProfiler`.

## Tests

### Static/upstream parity

- compare critical functions với upstream revision đã ghi;
- target layer IDs;
- block size;
- model config.

### Unit tests

- greedy sampler;
- acceptance prefix;
- zero accepted draft tokens;
- full accepted block;
- EOS giữa block;
- max token partial block;
- cache crop;
- metric invariants.

### Integration smoke

- Baseline single prompt;
- DFlash single prompt;
- GSM8K fixture;
- QMSum fixture;
- local-only load;
- repeated run determinism.

## Required artifacts

```text
results/Rec-T03A/
├── reports/
│   └── report.md
├── archive_module_audit.csv
├── upstream_parity.json
├── runtime_contract.json
├── dflash_invariant_tests.json
├── baseline_smoke.json
├── dflash_smoke.json
└── logs/
```

## PASS gate

- target/drafter local-only load pass;
- Baseline single prompt pass;
- DFlash single prompt pass;
- no duplicated prefill;
- DFlash invariants pass;
- benchmark mode không bị profiling sync;
- source recovered modules có audit trail;
- không import từ `.archives/` lúc runtime;
- không dùng old benchmark glue.

## STOP conditions

- target/drafter config mismatch;
- cache invariant fail;
- output không deterministic ở temperature 0;
- DFlash commit token không được target verify;
- duplicated target work chưa giải thích;
- instrumentation thay đổi output hoặc acceptance.

---

# Rec-T03B — Audit and Benchmark Baseline-AR and DFlash-R1 n=10

## Mục tiêu

Xác nhận runtime sạch trên hai frozen dataset trước khi tích hợp compression.

## Matrix

| Dataset    | Baseline-AR | DFlash-R1 |
| ---------- | ----------: | --------: |
| GSM8K n=10 |         Run |       Run |
| QMSum n=10 |         Run |       Run |

Tổng: `40 rows`.

## Protocol

1. Dùng frozen `n10` từ `Rec-T02A`.
2. Mỗi condition chạy process riêng.
3. Same target, tokenizer, prompt policy, stop policy và max token.
4. Warmup policy giống nhau.
5. Benchmark mode cho latency chính thức.
6. Profiling chỉ chạy trên tối đa 1–3 fixture đại diện khi cần điều tra.
7. Không sửa config giữa hai condition ngoài `generation_mode` và drafter presence.

## Metrics

### Common

- success count;
- input/output tokens;
- target prefill;
- decode;
- request E2E;
- generation tok/s;
- E2E tok/s;
- peak allocated/reserved;
- cap-hit;
- output hash.

### DFlash

- verification calls;
- tau per row;
- global weighted tau;
- accepted draft tokens;
- draft acceptance rate;
- rollback;
- output tokens per verification.

### Quality

**GSM8K:** strict correct, wrong numeric, invalid, cap-limited incomplete.  
**QMSum:** reference precision/recall proxy, invalid, cap-hit, output length; no semantic correctness claim.

## Performance target

### GSM8K

Kỳ vọng DFlash nhanh hơn Baseline. Nếu không:

- audit acceptance;
- audit duplicated work;
- audit cache;
- audit timing;
- chưa được đi tiếp nếu nguyên nhân là implementation defect.

### QMSum

DFlash không bị ép phải nhanh hơn trên mọi row.

Chấp nhận đi tiếp khi:

- runtime đúng;
- không duplicated work;
- metric đúng;
- slowdown, nếu có, được giải thích bằng low acceptance/workload behavior;
- không có regression do implementation.

## Controlled profiling trigger

Chỉ bật profiling nếu:

- DFlash chậm hơn Baseline trên 10%;
- global weighted tau thấp bất thường;
- rollback rate trên 90%;
- output length lệch lớn;
- E2E và tok/s mâu thuẫn.

## Required artifacts

```text
results/Rec-T03B/
├── reports/
│   └── report.md
├── runs/
│   ├── gsm8k_baseline_ar.jsonl
│   ├── gsm8k_dflash_r1.jsonl
│   ├── qmsum_baseline_ar.jsonl
│   └── qmsum_dflash_r1.jsonl
├── summary.csv
├── dflash_acceptance_audit.csv
├── quality_summary.json
├── performance_summary.json
├── gate_decision.json
└── logs/
```

## Gate decisions

```text
PASS_READY_FOR_COMPRESSION
PASS_WITH_WORKLOAD_LIMITATION
FAIL_RUNTIME_DEFECT
FAIL_METRIC_CONTRACT
FAIL_DATASET_CONTRACT
INSUFFICIENT_EVIDENCE
```

## PASS gate

- 40/40 row có artifact hợp lệ hoặc mọi failure được giải thích;
- dataset/prompt/config hash match giữa conditions;
- GSM8K quality không regression bất thường;
- QMSum evaluator boundary đúng;
- DFlash invariant pass trên mọi row;
- không duplicated prefill;
- performance anomaly được phân loại implementation hay workload;
- chỉ hai trạng thái PASS mới mở `Rec-T04A`.

---

# Rec-T04A — Compression Architecture Reconstruction

## Mục tiêu

Xây lại CC-DFlash compression path theo structured prompt, loại bỏ segmentation, question duplication, prompt marker drift và token metric scope lỗi.

## Structured prompt contract

```python
PromptParts(
    context: str,
    question: str,
    instruction: str,
    system: str | None,
)
```

Chỉ `context` được phép nén.

Không dùng:

```python
full_prompt.rsplit("\n\n", 1)
```

## Prompt reconstruction invariant

### DFlash-R1

```text
Meeting transcript:
<context>

Question:
<question>

<instruction>
```

### CC-DFlash-R2

```text
Meeting transcript:
<compressed_context>

Question:
<question>

<instruction>
```

Chỉ `<context>` được thay đổi.

Bắt buộc:

```text
question occurrence == 1
instruction occurrence == 1
section markers preserved
```

## Compressor interface

```python
compress(
    context: str,
    question: str,
    config: CompressionConfig,
) -> CompressionResult
```

`CompressionResult` phải tách:

```text
compressed_context
segment_original_tokens
segment_compressed_tokens
segment_tokenizer_id
compression_factor
retained_ratio
reduction_pct
chunk_count
compression_total_ms
backend_metadata
```

Không trả full prompt từ compressor backend.

## Passthrough control

```text
compressed_context == context
```

Prompt final phải byte-equivalent với uncompressed prompt sau cùng một renderer.

## LLMLingua corrections

- question chỉ dùng conditioning;
- không concatenate question vào từng chunk output;
- chunk planning deterministic;
- chunk merge giữ separator;
- model/tokenizer local path và revision được khóa;
- compressor init timing tách riêng;
- per-request timing gồm segmentation, tokenization, chunk planning, backend compression, merge và validation.

## Token metric scopes

### Compressor segment

```text
segment_original_tokens
segment_compressed_tokens
segment_retained_ratio
segment_reduction_pct
```

### Full target prompt

```text
precompression_target_prompt_tokens
final_target_prompt_tokens
full_prompt_retained_ratio
full_prompt_reduction_pct
```

Hai nhóm phải ghi tokenizer ID riêng và không được chia chéo.

## Compression routing

Hỗ trợ policy rõ:

```text
compression_enabled
compression_profile
keep_rate
min_context_tokens
```

GSM8K có thể bị bypass khi context quá ngắn; bypass phải được ghi rõ.

## Source đề xuất

```text
src/ccdf/compression/
├── __init__.py
├── schemas.py
├── base.py
├── passthrough.py
├── llmlingua.py
├── chunking.py
├── validation.py
└── registry.py

src/ccdf/prompts/
├── schemas.py
├── renderer.py
└── policies.py
```

## Tests

- structured parts round-trip;
- only context changes;
- question exactly once;
- instruction exactly once;
- markers preserved;
- passthrough byte-equivalent;
- no repeated question across chunks;
- empty/short context;
- long QMSum chunking;
- deterministic compression config;
- segment/full-prompt metric scope;
- timing includes chunk planning;
- bypass is explicit;
- no tokenizer cross-scope ratio.

## Single-prompt audit

Trước benchmark n=30, chạy:

- 1 GSM8K fixture;
- 1 QMSum fixture ngắn;
- 1 QMSum fixture dài;
- passthrough control;
- LLMLingua compression.

## Required artifacts

```text
results/Rec-T04A/
├── reports/
│   └── report.md
├── compression_contract.json
├── prompt_invariant_audit.csv
├── token_scope_audit.csv
├── passthrough_equivalence.json
├── chunking_audit.json
├── single_prompt_smokes.jsonl
└── logs/
```

## PASS gate

- chỉ context bị nén;
- question/instruction đúng một lần;
- passthrough tương đương;
- không lặp question qua chunks;
- prompt markers giữ nguyên;
- token scopes đúng;
- full compression latency được đo;
- single-prompt smokes pass;
- CC-DFlash runtime dùng lại DFlash path từ `Rec-T03A`.

## STOP conditions

- compressor trả full prompt không kiểm soát;
- prompt reconstruction khác template ngoài context;
- question/instruction bị mất hoặc lặp;
- token ratio trộn tokenizer;
- compression timing bỏ chunk/tokenization work;
- quality regression do prompt corruption.

---

# Rec-T04B — Audit and Benchmark CC-DFlash n=30

## Mục tiêu

Benchmark ba condition trên cùng frozen `n30`, đánh giá giá trị thật của compression sau khi sửa toàn bộ contract.

## Matrix

| Dataset    | Baseline-AR | DFlash-R1 | CC-DFlash-R2 |
| ---------- | ----------: | --------: | -----------: |
| GSM8K n=30 |         Run |       Run |          Run |
| QMSum n=30 |         Run |       Run |          Run |

Tổng: `180 rows`.

## Fairness contract

Ba condition trong cùng dataset phải có:

- cùng fixture IDs và order;
- cùng target model;
- cùng tokenizer;
- cùng question/instruction;
- cùng generation config;
- cùng max token và stop policy;
- cùng evaluator.

CC-DFlash chỉ khác context được nén, compressor được load và có compression metrics.

## Benchmark protocol

1. Process isolation cho từng condition.
2. Benchmark mode cho latency chính.
3. Một profile smoke riêng nếu cần.
4. Không reuse stale artifact.
5. Summary chỉ đọc run có dataset hash, model lock hash, config hash và source commit khớp.
6. Không rerun từng row theo cách làm thay đổi subset.

## Metrics

### Runtime

- target prefill;
- decode;
- request E2E;
- generation tok/s;
- E2E tok/s;
- compressor init;
- compression total;
- VRAM allocated/reserved.

### Compression

- segment reduction;
- full-prompt reduction;
- chunk count;
- bypass count;
- compression cost;
- prefill saved;
- net E2E delta.

### DFlash

- mean per-row tau;
- global weighted tau;
- accepted draft tokens;
- draft acceptance rate;
- verification calls;
- rollback.

### Quality

**GSM8K:** strict correct, wrong numeric, invalid, cap-limited.  
**QMSum:** reference recall/precision proxy, invalid, cap-hit, output length, failure review; semantic correctness vẫn `NOT_CLAIMED`.

## Required comparisons

### DFlash vs Baseline

- quality;
- prefill;
- decode;
- E2E;
- tok/s;
- VRAM;
- acceptance explanation.

### CC-DFlash vs DFlash

- segment và full-prompt reduction;
- compression cost;
- target prefill saving;
- decode delta;
- acceptance delta;
- output-length delta;
- quality delta;
- net E2E delta.

## GSM8K decision boundary

CC-DFlash không bắt buộc phải thắng.

Kết luận hợp lệ có thể là:

```text
Short-context compression is not worthwhile.
DFlash-R1 is preferred for GSM8K-like inputs.
```

khi full-prompt reduction nhỏ, compression làm chậm, VRAM tăng hoặc quality giảm.

## QMSum decision boundary

CC-DFlash chỉ có lợi khi:

```text
compression_total_ms < prefill_saved_ms + decode_saved_ms
```

và quality proxy không suy giảm vượt boundary đã khóa.

Nếu compression giảm prefill nhưng làm acceptance thấp hơn hoặc output dài hơn, phải trình bày decomposition.

## Failure sample review

Chọn ít nhất:

- 3 row CC tốt hơn DFlash;
- 3 row không đổi;
- 3 row CC kém hơn;
- mọi invalid/cap-hit;
- các row có rollback hoặc output-length bất thường.

## Required artifacts

```text
results/Rec-T04B/
├── reports/
│   └── report.md
├── runs/
│   ├── gsm8k_baseline_ar.jsonl
│   ├── gsm8k_dflash_r1.jsonl
│   ├── gsm8k_cc_dflash_r2.jsonl
│   ├── qmsum_baseline_ar.jsonl
│   ├── qmsum_dflash_r1.jsonl
│   └── qmsum_cc_dflash_r2.jsonl
├── summary.csv
├── runtime_decomposition.csv
├── compression_metrics.csv
├── dflash_acceptance_comparison.csv
├── quality_summary.json
├── failure_samples.jsonl
├── claim_boundary.json
└── gate_decision.json
```

## Gate decisions

```text
PASS_RECONSTRUCTION_COMPLETE
PASS_WITH_SHORT_CONTEXT_BYPASS
FAIL_COMPRESSION_CORRECTNESS
FAIL_RUNTIME_CONTRACT
FAIL_QUALITY_BOUNDARY
FAIL_METRIC_CONTRACT
INSUFFICIENT_EVIDENCE
```

## PASS gate

- 180 rows được thực thi hoặc mọi failure có audit;
- prompt fairness pass;
- token metric scope pass;
- timing contract pass;
- DFlash invariants pass;
- GSM8K decision rõ;
- QMSum runtime decomposition rõ;
- QMSum semantic correctness không bị overclaim;
- claim boundary được khóa;
- kết quả đủ để mở closure task sau `Rec-T04B`.

---

## 3. Quy tắc thực thi agent

Mỗi task prompt phải có:

```text
Branch
Task
Scope
Inputs
Implementation boundary
Required artifacts
Checks
Commit
Final response
```

Agent được phép:

- sửa source trong phạm vi task;
- chạy test/benchmark đã định nghĩa;
- tạo local commit;
- tạo subtask khi có blocker thật.

Agent không được:

- push;
- merge;
- sửa `.archives/`;
- sửa artifact lịch sử;
- tự thay model/dataset;
- thay claim boundary để làm đẹp kết quả;
- chạy full n=100 trước khi gate n=10/n=30 pass;
- dùng notebook làm canonical evidence.

---

## 4. Trạng thái khởi tạo

```text
Rec-T02A:  PLANNED
Rec-T02B:  BLOCKED_BY_REC_T02A
Rec-T02B1: BLOCKED_BY_REC_T02B
Rec-T03A:  BLOCKED_BY_REC_T02B1
Rec-T03B:  BLOCKED_BY_REC_T03A
Rec-T04A:  BLOCKED_BY_REC_T03B
Rec-T04B:  BLOCKED_BY_REC_T04A
```

---

## 5. Definition of Done

Phạm vi `Rec-T02A → Rec-T04B` hoàn tất khi:

- dataset provenance và nested subsets PASS;
- benchmark/timing/metric contract PASS;
- single-prompt runner dùng cùng runtime với benchmark;
- Baseline-AR và DFlash-R1 n=10 được audit;
- DFlash anomaly được phân loại bằng evidence;
- compression prompt invariants PASS;
- CC-DFlash n=30 được benchmark công bằng;
- result artifacts đúng folder;
- report không overclaim;
- source mới không phụ thuộc runtime import từ archive.

---

# Rec-T06A3 — NF4 Structural Correctness and Efficient DFlash Production Repair

## Approved direction

```text
RETAIN_NF4_AND_USE_STRUCTURAL_PLUS_EMPIRICAL_CORRECTNESS
```

- Cached Baseline-AR remains the comparison target.
- DFlash-R1 uses one target verification forward per proposed block.
- CC-DFlash-R2 uses the same DFlash-R1 executor after optional compression.
- Exact cached-AR token equivalence is `NOT_CLAIMED`.
- Structural target-verification correctness is required and audited.
- Quality preservation is evaluated empirically on coupled GSM8K/QMSum gates.
- Quantization is never described as lossless.

## Worktree convention

```text
.worktrees/rec-<id>-ongoing
.worktrees/rec-<id>-closed
```

Checkpoints remain under the primary repository's `models/` directory and are
resolved by `@shared/models/...`; they must not be copied into linked
worktrees.

## A3 gate

1. Source/unit checks.
2. Coupled n3: all three conditions on GSM8K and QMSum.
3. Coupled n10: Baseline-AR versus DFlash-R1 on both datasets.
4. No n30 and no merge before independent result-pack audit.

Rec-T06B/C/D remain responsible for canonical process isolation, final timing
and provenance, compare UX, optimization, and n30.
