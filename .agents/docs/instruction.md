# HTFSD: Hierarchical Token-Feature Speculative Decoding

## 1. Abstract

Dự án này đề xuất phát triển và đánh giá một kiến trúc **Hierarchical Token-Feature Speculative Decoding** nhằm tăng tốc quá trình suy luận của mô hình ngôn ngữ lớn thông qua hai tầng suy đoán liên tiếp.

Ở **Low Tier**, mô hình nhỏ **Qwen3-0.6B** đóng vai trò cross-family drafter. Vì Qwen và Gemma không chia sẻ tokenizer, vocabulary, hidden-state geometry hoặc KV-cache layout, tầng này không cố gắng tái sử dụng token ID hay KV-cache của Qwen. Thay vào đó, Qwen sinh các candidate continuation ở dạng văn bản có cấu trúc thông qua giao thức **D-Flash**. D-Flash được xem là một **side-channel candidate proposal format**, không phải nội dung được đưa trực tiếp vào context của Gemma.

Ở **High Tier**, **Gemma E2B** đóng vai trò mid-level verifier cho Low Tier, đồng thời cung cấp hidden states của những token đã được chấp nhận cho cơ chế **EAGLE-style / EAGLE-2 feature speculation**. Cơ chế này sinh candidate tree cho **Gemma E4B**, mô hình đích cuối cùng.

Mục tiêu nghiên cứu là tăng tốc độ sinh token của **Gemma E4B** từ khoảng **2× đến 4×** so với autoregressive decoding thông thường, trong khi vẫn giữ chất lượng đầu ra tương đương với Gemma E4B baseline trong chế độ strict/lossless hoặc gần-lossless. Các kết quả về throughput, acceptance rate, latency, memory footprint và quality drift sẽ được đo trong giai đoạn thực nghiệm.

---

## 2. Problem Statement

Quá trình sinh văn bản tự hồi quy của LLM bị giới hạn bởi đặc tính tuần tự: mỗi token mới cần một forward pass mới của mô hình đích. Với các mô hình lớn, điều này tạo ra bottleneck về memory bandwidth và latency.

**Speculative Decoding** giải quyết vấn đề này bằng cách dùng một mô hình nhỏ hơn để sinh trước nhiều candidate token, sau đó mô hình đích xác minh nhiều token trong một hoặc ít forward pass hơn. Nếu nhiều token được chấp nhận, tốc độ sinh token có thể tăng đáng kể.

Tuy nhiên, các phương pháp speculative decoding truyền thống thường giả định draft model và target model có mức độ tương thích cao:

- cùng tokenizer hoặc vocabulary gần tương thích;
- cùng model family;
- hidden states hoặc feature space dễ liên kết;
- KV-cache layout có thể tái sử dụng hoặc ít nhất không xung đột.

Dự án này đặt ra bài toán khó hơn:

```text
Qwen3-0.6B  →  Gemma E2B  →  Gemma E4B
```

Trong đó:

- Qwen3-0.6B và Gemma E2B là **cross-family pair**;
- Gemma E2B và Gemma E4B là **intra-family pair**;
- mục tiêu là kết hợp token-level candidate proposal và feature-level speculation trong một pipeline phân cấp.

---

## 3. Core Research Goal

Dự án này đề xuất phát triển và đánh giá một kiến trúc speculative decoding mới, kết hợp đồng thời cả hai mức độ:

1. **Token/Text-level speculation**  
   Qwen3-0.6B sinh candidate continuation cho Gemma E2B thông qua D-Flash.

2. **Feature-level speculation**  
   Gemma E2B cung cấp hidden states cho EAGLE-style draft head để sinh candidate tree cho Gemma E4B.

Mục tiêu cốt lõi:

```text
Tăng tốc độ suy luận của Gemma E4B từ 2× đến 4×
so với autoregressive decoding thông thường,
trong khi không làm suy giảm chất lượng đầu ra của mô hình đích.
```

Mức mục tiêu:

| Mức            | Speedup mục tiêu | Ý nghĩa                                  |
| -------------- | ---------------: | ---------------------------------------- |
| Minimum target |             2.0× | Có giá trị thực tế nếu overhead thấp     |
| Strong target  |             3.0× | Mục tiêu chính của dự án                 |
| Stretch target |             4.0× | Kết quả rất tốt, cần acceptance rate cao |

---

## 4. System Architecture

HTFSD gồm ba mô hình được tổ chức thành hai tầng suy đoán.

```text
Input Prompt x
    |
    v
+----------------+
| Qwen3-0.6B      |
| Low Drafter     |
+----------------+
    |
    | D-Flash candidate proposal
    v
+----------------+
| Gemma E2B       |
| Mid Verifier    |
| Feature Source  |
+----------------+
    |
    | Accepted hidden states
    | EAGLE-style feature speculation
    v
+----------------+
| Gemma E4B       |
| Target Verifier |
+----------------+
    |
    v
Final Output
```

Vai trò của từng mô hình:

| Model      | Vai trò                             | Ghi chú                                       |
| ---------- | ----------------------------------- | --------------------------------------------- |
| Qwen3-0.6B | Low-level drafter                   | Sinh candidate continuation dạng text         |
| Gemma E2B  | Mid-level verifier + feature source | Verify candidate từ Qwen, trích hidden states |
| Gemma E4B  | Target model / final verifier       | Quyết định output cuối cùng                   |

Nguyên tắc quan trọng:

- Qwen không chia sẻ KV-cache với Gemma.
- D-Flash không được đưa trực tiếp vào context của Gemma như prompt prefix.
- Gemma E2B phải verify candidate dựa trên context gốc.
- Chỉ hidden states của token đã được Gemma E2B chấp nhận mới được đưa lên High Tier.
- Gemma E4B là mô hình đích cuối cùng, mọi đánh giá quality phải so với Gemma E4B baseline.

---

## 5. Low Tier: Qwen3-0.6B → Gemma E2B bằng D-Flash

### 5.1 Mục tiêu của Low Tier

Low Tier giải quyết bài toán suy đoán liên họ giữa **Qwen3-0.6B** và **Gemma E2B**.

Hai mô hình này có thể khác nhau ở:

- tokenizer;
- vocabulary;
- token boundary;
- hidden-state dimension;
- normalization scheme;
- KV-cache layout;
- model architecture.

Vì vậy, Low Tier không cố gắng dùng trực tiếp token IDs hoặc KV-cache của Qwen. Thay vào đó, Qwen chỉ được dùng như một **candidate text generator**.

### 5.2 D-Flash là gì?

**D-Flash** là một format trung gian để Qwen xuất candidate continuation có cấu trúc, dễ parse và dễ kiểm tra.

D-Flash không phải là:

- learned tokenizer projection;
- shared vocabulary mapping;
- KV-cache bridge;
- prompt prefix cho Gemma;
- bằng chứng rằng cross-family speculative decoding đã lossless.

D-Flash là:

- side-channel metadata;
- candidate proposal format;
- cách ép Qwen sinh output có cấu trúc;
- cầu nối để chuyển từ Qwen text output sang Gemma-tokenized candidate.

### 5.3 D-Flash Envelope

Ví dụ D-Flash envelope:

```json
{
  "draft_text": "def fibonacci(n):\n    if n <= 1:\n        return n",
  "confidence": 0.82,
  "alternatives": [
    "iterative fibonacci implementation",
    "memoized recursive implementation"
  ],
  "max_tokens": 6
}
```

Các field chính:

| Field          | Vai trò                                                                     |
| -------------- | --------------------------------------------------------------------------- |
| `draft_text`   | Candidate continuation chính                                                |
| `confidence`   | Confidence do Qwen tự đánh giá, dùng để filter hoặc điều chỉnh draft length |
| `alternatives` | Các hướng candidate phụ, dùng cho branch generation nếu cần                 |
| `max_tokens`   | Giới hạn số token Gemma sẽ retokenize/verify                                |

Trong MVP, chỉ cần bắt buộc field:

```json
{
  "draft_text": "..."
}
```

Các field khác có thể thêm sau.

### 5.4 Low Tier Pipeline

```text
Input context x
    |
    v
Qwen3-0.6B generates D-Flash envelope
    |
    v
D-Flash parser extracts draft_text
    |
    v
Gemma tokenizer retokenizes draft_text
    |
    v
Gemma E2B verifies candidate tokens under original context x
    |
    v
Accepted prefix tokens + hidden states
```

Chi tiết từng bước:

1. Qwen3-0.6B nhận context gốc `x`.
2. Qwen sinh D-Flash envelope.
3. Parser kiểm tra JSON hợp lệ.
4. Parser trích xuất `draft_text`.
5. `draft_text` được tokenize lại bằng tokenizer của Gemma E2B.
6. Gemma E2B chạy verification trên context gốc `x`.
7. Token prefix nào được Gemma E2B chấp nhận thì được giữ lại.
8. Hidden states tương ứng với accepted tokens được lưu cho High Tier.
9. Token bị reject thì bị bỏ, không đưa lên High Tier.

### 5.5 Low Tier Acceptance Policy

Low Tier cần định nghĩa rõ policy chấp nhận token. Có thể bắt đầu với hai chế độ.

#### Strict Mode

Gemma E2B chỉ chấp nhận candidate token nếu token đó đủ phù hợp với phân phối của Gemma tại cùng vị trí.

Ví dụ policy:

```text
accept token if draft_token ∈ top_k(Gemma_E2B_logits)
```

hoặc:

```text
accept token if P_Gemma_E2B(draft_token | context) >= threshold
```

Strict Mode phù hợp để đánh giá khả năng gần-lossless.

#### Approximate Mode

Gemma E2B có thể chấp nhận candidate dựa trên semantic similarity, confidence hoặc heuristic khác.

Chế độ này có thể tăng acceptance rate, nhưng không được gọi là lossless speculative decoding nếu chưa chứng minh được output distribution tương đương Gemma baseline.

MVP nên ưu tiên **Strict Mode** trước.

---

## 6. High Tier: Gemma E2B → Gemma E4B bằng EAGLE-2 / EAGLE-style Speculation

### 6.1 Mục tiêu của High Tier

High Tier khai thác quan hệ cùng họ giữa **Gemma E2B** và **Gemma E4B**. Sau khi Gemma E2B chấp nhận một số token từ Low Tier, hidden states tương ứng với những token này được dùng để hỗ trợ sinh candidate cho Gemma E4B.

Mục tiêu của High Tier là tăng số token được Gemma E4B xác minh trong mỗi verification step.

### 6.2 EAGLE-style Draft Head

High Tier sử dụng một draft head kiểu EAGLE/EAGLE-2 để dự đoán candidate continuation từ hidden states.

Tùy vào compatibility giữa Gemma E2B và Gemma E4B, có thể cần:

- EAGLE-style draft head;
- projection layer từ hidden space của E2B sang không gian phù hợp với E4B;
- lightweight adapter;
- calibration layer;
- confidence scorer cho dynamic tree.

Không nên gọi High Tier là zero-training nếu có bất kỳ head/projection nào cần train.

Cách gọi chính xác hơn:

```text
No target-model weight modification, but may require a lightweight trained speculator head.
```

### 6.3 High Tier Pipeline

```text
Accepted tokens from Gemma E2B
    |
    v
Extract hidden states from accepted positions
    |
    v
EAGLE-style head builds candidate tree
    |
    v
Gemma E4B batch-verifies candidate tree
    |
    v
Accepted high-tier prefix is appended to output
    |
    v
Fallback to Gemma E4B one-token decoding if rejected
```

### 6.4 Critical Compatibility Checks

Trước khi triển khai High Tier, cần kiểm tra:

| Kiểm tra           | Câu hỏi                                                            |
| ------------------ | ------------------------------------------------------------------ |
| Hidden size        | Gemma E2B và Gemma E4B có cùng hidden dimension không?             |
| Layer mapping      | Hidden states nên lấy từ layer nào của E2B?                        |
| Tokenizer          | E2B và E4B có dùng cùng tokenizer không?                           |
| Feature projection | Có cần projection layer không?                                     |
| Draft head         | EAGLE head đã có sẵn hay cần train?                                |
| vLLM integration   | Có lấy được hidden states và logits cần thiết trong runtime không? |

### 6.5 Promotion Rule

Chỉ được đưa hidden states lên High Tier nếu token tương ứng đã được Gemma E2B chấp nhận.

```text
Rejected low-tier tokens must not be promoted to high-tier speculation.
```

Lý do:

- hidden state của token chưa được accept có thể không phản ánh trajectory hợp lệ;
- High Tier sẽ build candidate tree trên trạng thái sai;
- Gemma E4B verification sẽ reject nhiều hơn, làm giảm speedup.

---

## 7. Decoding Loop

Pseudo-code cấp cao:

```text
Input: prompt x
Output: generated sequence y

while not EOS:

    # LOW TIER: Qwen3-0.6B -> Gemma E2B
    envelope = Qwen.generate_dflash(x)
    draft_text = parse_dflash(envelope)
    draft_ids_e2b = GemmaE2B.tokenize(draft_text)

    accepted_low, hidden_low = GemmaE2B.verify(
        context=x,
        candidate_tokens=draft_ids_e2b
    )

    if len(accepted_low) == 0:
        # optional fallback at mid level
        token = GemmaE2B.sample_one(x)
        accepted_low = [token]
        hidden_low = GemmaE2B.hidden_state_for(token)

    # HIGH TIER: Gemma E2B -> Gemma E4B
    candidate_tree = EagleHead.build_tree(hidden_low)

    accepted_high = GemmaE4B.batch_verify(
        context=x + accepted_low,
        candidate_tree=candidate_tree
    )

    if len(accepted_high) > 0:
        x = x + accepted_low + accepted_high
    else:
        fallback_token = GemmaE4B.sample_one(x)
        x = x + [fallback_token]
```

Lưu ý:

- pseudo-code trên là định hướng, chưa phải implementation cuối cùng;
- acceptance rule cần được định nghĩa cụ thể khi triển khai;
- fallback policy có thể thay đổi tùy strict mode hoặc approximate mode;
- cần tránh duplicate token giữa `accepted_low` và `accepted_high` nếu high-tier context đã bao gồm low-tier prefix.

---

## 8. Evaluation Metrics

### 8.1 Throughput

Đo số token sinh ra mỗi giây:

```text
tokens_per_second = total_generated_tokens / total_generation_time
```

So sánh với baseline:

```text
Gemma E4B autoregressive decoding = 1.0× baseline
```

### 8.2 Speedup

```text
speedup = tokens_per_second_HTFSD / tokens_per_second_Gemma_E4B_baseline
```

Mục tiêu:

```text
minimum target: 2.0×
strong target: 3.0×
stretch target: 4.0×
```

### 8.3 Low-Tier Acceptance Rate

```text
low_acceptance_rate = accepted_tokens_by_Gemma_E2B / drafted_tokens_by_Qwen
```

Metric phụ:

```text
average_accepted_low_prefix_length
malformed_dflash_rate
dflash_parse_latency
qwen_draft_latency
gemma_e2b_verify_latency
```

### 8.4 High-Tier Acceptance Rate

```text
high_acceptance_rate = accepted_tokens_by_Gemma_E4B / drafted_tokens_by_EAGLE
```

Metric phụ:

```text
candidate_tree_size
eagle_tree_construction_latency
gemma_e4b_batch_verify_latency
fallback_rate
average_accepted_high_prefix_length
```

### 8.5 End-to-End Acceptance

```text
end_to_end_acceptance = accepted_tokens_by_Gemma_E4B / total_drafted_tokens
```

Cần đo thêm:

```text
accepted_tokens_per_cycle
verification_cycles_per_response
fallback_tokens_per_response
```

### 8.6 Latency per Token

```text
latency_per_token = total_generation_time / total_generated_tokens
```

Nên tách latency theo stage:

| Stage            | Metric            |
| ---------------- | ----------------- |
| Qwen draft       | `qwen_draft_ms`   |
| D-Flash parse    | `dflash_parse_ms` |
| Gemma E2B verify | `e2b_verify_ms`   |
| EAGLE tree build | `eagle_build_ms`  |
| Gemma E4B verify | `e4b_verify_ms`   |
| fallback         | `fallback_ms`     |

### 8.7 Memory Usage

Cần đo:

```text
peak_vram_usage
steady_state_vram_usage
kv_cache_usage
model_weight_usage
speculation_buffer_usage
```

Vì runtime mục tiêu là vLLM, không nên giả định memory footprint từ llama.cpp/GGUF nếu chưa đo.

### 8.8 Quality Preservation

Mục tiêu chất lượng:

```text
Output của HTFSD phải tương đương Gemma E4B baseline trong strict/lossless mode.
```

Metric đề xuất:

| Metric               | Mục đích                                              |
| -------------------- | ----------------------------------------------------- |
| Exact token match    | Kiểm tra lossless behavior khi deterministic decoding |
| KL divergence        | So sánh phân phối logits nếu lấy được logits          |
| ROUGE-L              | So sánh overlap text                                  |
| Task accuracy        | Đánh giá trên task cụ thể                             |
| LLM-as-judge winrate | So sánh chất lượng hội thoại                          |
| Human review         | Đánh giá lỗi semantic nghiêm trọng                    |

Trong approximate mode, cần báo cáo rõ:

```text
quality_drift = quality_HTFSD - quality_Gemma_E4B_baseline
```

---

## 9. Planned Experiments

Các kết quả trong dự án chưa được đo. Phần này mô tả kế hoạch đánh giá.

### 9.1 Baseline: Gemma E4B Autoregressive Decoding

Mục tiêu:

- đo tốc độ gốc của Gemma E4B;
- lấy baseline cho quality;
- lấy baseline cho VRAM và latency.

Metric:

```text
tokens/s
latency/token
peak VRAM
output quality
```

### 9.2 Qwen3-0.6B Drafting Benchmark

Mục tiêu:

- đo tốc độ sinh draft của Qwen;
- đo tỷ lệ JSON hợp lệ;
- đo độ ổn định của D-Flash output.

Metric:

```text
qwen_tokens/s
valid_json_rate
malformed_json_rate
draft_text_length
confidence_distribution
```

### 9.3 Low Tier Ablation

Pipeline:

```text
Qwen3-0.6B -> D-Flash -> Gemma E2B
```

Mục tiêu:

- đo xem D-Flash có tạo candidate hữu ích cho Gemma E2B không;
- đo acceptance rate của cross-family candidate;
- đo overhead parsing và retokenization.

Metric:

```text
low_acceptance_rate
accepted_low_prefix_length
dflash_parse_latency
gemma_retokenization_latency
gemma_e2b_verify_latency
low_tier_tokens/s
```

### 9.4 High Tier Ablation

Pipeline:

```text
Gemma E2B -> EAGLE-style head -> Gemma E4B
```

Mục tiêu:

- đo khả năng dùng Gemma E2B làm feature-level drafter cho Gemma E4B;
- xác định có cần projection/adaptor không;
- đo acceptance rate của candidate tree.

Metric:

```text
hidden_compatibility_score
candidate_tree_size
high_acceptance_rate
accepted_high_prefix_length
eagle_build_latency
gemma_e4b_batch_verify_latency
high_tier_speedup
```

### 9.5 Full HTFSD Evaluation

Pipeline:

```text
Qwen3-0.6B -> D-Flash -> Gemma E2B -> EAGLE-style -> Gemma E4B
```

Mục tiêu:

- đo speedup end-to-end;
- đo interaction giữa hai tầng;
- kiểm tra overhead có vượt lợi ích không;
- đánh giá quality drift so với Gemma E4B baseline.

Metric:

```text
end_to_end_tokens/s
speedup_over_e4b_baseline
end_to_end_acceptance
fallback_rate
latency_per_token
peak_vram_usage
quality_drift
```

### 9.6 Target Evaluation Table

| Method                | Tokens/s |       Speedup | Acceptance Rate | Quality Drift | Status        |
| --------------------- | -------: | ------------: | --------------: | ------------: | ------------- |
| Gemma E4B Baseline    |      TBD |          1.0× |               — |             0 | To measure    |
| Qwen3-0.6B Standalone |      TBD |           TBD |               — |           TBD | To measure    |
| Gemma E2B Standalone  |      TBD |           TBD |               — |           TBD | To measure    |
| Low Tier only         |      TBD |           TBD |             TBD |           TBD | To implement  |
| High Tier only        |      TBD |           TBD |             TBD |           TBD | To implement  |
| Full HTFSD            |      TBD | Target: 2×–4× |             TBD |    Target: ≈0 | Research goal |

---

## 10. Implementation Risks

### 10.1 D-Flash May Not Improve Acceptance Enough

Qwen output có thể khác Gemma E2B distribution quá nhiều, làm low-tier acceptance rate thấp.

Rủi ro:

```text
low_acceptance_rate thấp -> overhead Qwen + parsing > lợi ích
```

Giảm rủi ro:

- bắt đầu với prompt đơn giản;
- giới hạn draft length nhỏ;
- dùng strict JSON schema;
- đo malformed JSON rate;
- fallback nhanh nếu candidate kém.

### 10.2 JSON Overhead

D-Flash parsing và structured generation có thể làm tăng latency.

Giảm rủi ro:

- dùng compact JSON;
- chỉ bắt buộc `draft_text` trong MVP;
- giới hạn max draft tokens;
- benchmark parse latency riêng.

### 10.3 EAGLE Head Requires Training

Nếu cần EAGLE-style head, dự án không còn là zero-training.

Giảm rủi ro:

- gọi đúng là no target-weight modification;
- tách phase training head riêng;
- trước tiên đo high-tier bằng draft-model speculative baseline nếu vLLM hỗ trợ.

### 10.4 Hidden Dimension Mismatch

Gemma E2B và Gemma E4B có thể không có hidden state dimension tương thích.

Giảm rủi ro:

- kiểm tra config model trước;
- nếu mismatch, thêm projection layer;
- đo cosine similarity hoặc predictive utility thay vì giả định feature space gần nhau.

### 10.5 vLLM Integration Complexity

vLLM có speculative decoding support, nhưng pipeline 3 model + custom D-Flash + hidden-state EAGLE có thể cần custom scheduler hoặc wrapper.

Giảm rủi ro:

- MVP chạy từng tier riêng trước;
- không tích hợp cả 3 model ngay từ đầu;
- log đầy đủ latency từng stage;
- dùng offline benchmark trước khi tối ưu serving.

### 10.6 Memory Pressure on 12GB VRAM

Chạy 3 model cùng lúc bằng vLLM trên RTX 4070 12GB có thể khó vì còn KV-cache, CUDA graph, activation buffer và runtime overhead.

Giảm rủi ro:

- bắt đầu với quantized models;
- giới hạn context length;
- chạy từng tier riêng;
- profile VRAM trước khi full integration;
- cân nhắc CPU offload nếu cần.

---

## 11. MVP Roadmap

### Phase 0: Baseline Setup

Mục tiêu:

- chạy được Gemma E4B baseline bằng vLLM;
- đo tokens/s, latency/token, VRAM;
- lưu output baseline.

Deliverables:

```text
baseline_e4b.py
benchmark_results_baseline.json
```

### Phase 1: D-Flash Generator

Mục tiêu:

- chạy Qwen3-0.6B sinh D-Flash envelope;
- parse được `draft_text`;
- đo valid JSON rate.

Deliverables:

```text
dflash_schema.py
dflash_parser.py
qwen_dflash_drafter.py
```

### Phase 2: Low Tier Verification

Mục tiêu:

- retokenize `draft_text` bằng Gemma tokenizer;
- Gemma E2B verify candidate;
- đo low-tier acceptance rate.

Deliverables:

```text
low_tier_verifier.py
low_tier_benchmark.py
```

### Phase 3: High Tier Feasibility Check

Mục tiêu:

- kiểm tra tokenizer/config/hidden size của Gemma E2B và E4B;
- xác định có cần projection không;
- thử lấy hidden states từ Gemma E2B.

Deliverables:

```text
check_gemma_compatibility.py
hidden_state_probe.py
```

### Phase 4: EAGLE-style Prototype

Mục tiêu:

- xây dựng hoặc tích hợp EAGLE-style draft head;
- thử candidate tree nhỏ;
- Gemma E4B batch-verify candidate.

Deliverables:

```text
eagle_head.py
eagle_tree.py
high_tier_verifier.py
```

### Phase 5: Full HTFSD Integration

Mục tiêu:

- nối Low Tier và High Tier;
- chỉ promote accepted low-tier hidden states;
- đo end-to-end speedup.

Deliverables:

```text
htfsd_engine.py
htfsd_benchmark.py
metrics_report.json
```

### Phase 6: Evaluation Report

Mục tiêu:

- so sánh với Gemma E4B baseline;
- báo cáo throughput, speedup, acceptance, latency, VRAM, quality drift;
- xác định kiến trúc có đạt mục tiêu 2×–4× không.

Deliverables:

```text
report.md
plots/
benchmark_tables/
```

---

## 12. Recommended Project Structure

```text
htfsd/
├── README.md
├── configs/
│   ├── models.yaml
│   └── benchmark.yaml
├── src/
│   ├── dflash/
│   │   ├── schema.py
│   │   ├── parser.py
│   │   └── prompts.py
│   ├── low_tier/
│   │   ├── qwen_drafter.py
│   │   ├── gemma_e2b_verifier.py
│   │   └── acceptance.py
│   ├── high_tier/
│   │   ├── hidden_probe.py
│   │   ├── eagle_head.py
│   │   ├── tree_builder.py
│   │   └── gemma_e4b_verifier.py
│   ├── engine/
│   │   ├── htfsd_engine.py
│   │   └── scheduler.py
│   ├── metrics/
│   │   ├── latency.py
│   │   ├── throughput.py
│   │   ├── acceptance.py
│   │   └── quality.py
│   └── utils/
│       ├── logging.py
│       └── memory.py
├── benchmarks/
│   ├── baseline_e4b.py
│   ├── low_tier_benchmark.py
│   ├── high_tier_benchmark.py
│   └── full_htfsd_benchmark.py
├── tests/
│   ├── test_dflash_parser.py
│   ├── test_acceptance_policy.py
│   └── test_metrics.py
└── reports/
    └── results_template.md
```

---

## 13. Summary

HTFSD là một kiến trúc nghiên cứu nhằm kết hợp hai hướng tăng tốc inference:

```text
Cross-family text-level candidate proposal
+
Intra-family feature-level speculation
```

Điểm mạnh của kiến trúc là cách dùng **Gemma E2B** như một mô hình trung gian hai vai trò:

1. verifier cho candidate của Qwen ở Low Tier;
2. feature source/drafter cho Gemma E4B ở High Tier.

Tuy nhiên, hiện tại tất cả kết quả như speedup, acceptance rate, throughput và quality preservation phải được xem là **mục tiêu cần đo**, không phải kết quả đã đạt được.

Kết luận định vị đúng của dự án:

```text
HTFSD proposes a hierarchical speculative inference architecture.
It aims to achieve 2×–4× speedup over Gemma E4B autoregressive decoding.
The architecture must be validated through staged experiments before claiming lossless generation or measured throughput gains.
```
