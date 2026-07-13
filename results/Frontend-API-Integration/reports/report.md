# Frontend-API Integration Smoke Test Report

## Health Check
```json
{
  "status": "ok",
  "version": "1.0"
}
```
## Capabilities
```json
{
  "cuda_available": true,
  "gpu_name": "NVIDIA GeForce RTX 4070 Laptop GPU",
  "compressor_options": [
    "cpu",
    "cuda"
  ],
  "job_active": false
}
```
## Scenario: Question-only
Job created: 3e4a1c53-ef7b-4570-96b7-e72112a6b10a
### SSE Events
```
data: event: job.started
data: data: {"job_id": "3e4a1c53-ef7b-4570-96b7-e72112a6b10a"}
data:
data:

data: event: input.parsed
data: data: {"context_length": 0, "question_length": 28}
data:
data:

data: event: condition.started
data: data: baseline-ar
data:
data:

data: event: condition.completed
data: data: {"condition_id": "baseline-ar", "display_name": "Baseline-AR", "status": "completed", "generated_text": "The meaning of life is a philosophical question with no single answer. It varies depending on individual beliefs, values, and perspectives. Some find purpose in relationships, personal growth, contributing to others, or pursuing passions. Ultimately, it is a personal journey of discovery and self-reflection.", "stop_reason": "eos", "input_tokens_precompression": 55, "input_tokens_final": 55, "prompt_reduction_tokens": null, "prompt_reduction_pct": 0.0, "compression_ratio": 1.0, "compression_applied": true, "compression_bypassed": false, "compression_bypass_reason": null, "compression_total_ms": 0.0, "target_prefill_ms": 271.52829700207803, "draft_prefill_ms": 0.0, "decode_total_ms": 1756.9411049989867, "generation_request_e2e_ms": 2028.5650360019645, "warm_request_e2e_ms": 2042.067035999935, "cold_start_e2e_ms": 5909.890745002485, "output_tokens": 57, "generation_tok_s": 32.44274941135996, "warm_request_tok_s": 27.912893649002527, "target_forwards_per_output_token": null, "effective_tau": 0.0, "draft_acceptance_rate": 0.0, "verification_calls": 0, "draft_forward_calls": 0, "rollback_tokens": 0, "peak_cuda_allocated_bytes": 2723410432, "peak_cuda_reserved_bytes": 3045064704, "process_current_rss_bytes": null, "resource_composition": "quantized target", "compressor_device": null, "compressor_cuda_verified": null}
data:
data:

data: event: condition.started
data: data: dflash-r1
data:
data:

: ping - 2026-07-13 00:18:20.688279+00:00

data: event: condition.completed
data: data: {"condition_id": "dflash-r1", "display_name": "D-Flash", "status": "completed", "generated_text": "The meaning of life is a philosophical question with no single answer. It varies depending on individual beliefs, values, and perspectives. Some find purpose in relationships, personal growth, contributing to others, or pursuing passions. Ultimately, it is a personal journey of discovery.", "stop_reason": "eos", "input_tokens_precompression": 55, "input_tokens_final": 55, "prompt_reduction_tokens": null, "prompt_reduction_pct": 0.0, "compression_ratio": 1.0, "compression_applied": true, "compression_bypassed": false, "compression_bypass_reason": null, "compression_total_ms": 0.0, "target_prefill_ms": 254.9875049990078, "draft_prefill_ms": 0.0, "decode_total_ms": 2246.5252139991208, "generation_request_e2e_ms": 2501.7390930006513, "warm_request_e2e_ms": 2517.245543000172, "cold_start_e2e_ms": 6770.919716007484, "output_tokens": 53, "generation_tok_s": 23.591989829329705, "warm_request_tok_s": 21.054759694531867, "target_forwards_per_output_token": null, "effective_tau": 2.08, "draft_acceptance_rate": 0.07466666666666667, "verification_calls": 25, "draft_forward_calls": 25, "rollback_tokens": 347, "peak_cuda_allocated_bytes": 3826855936, "peak_cuda_reserved_bytes": 3854565376, "process_current_rss_bytes": null, "resource_composition": "quantized target + drafter", "compressor_device": null, "compressor_cuda_verified": null}
data:
data:

data: event: condition.started
data: data: cc-dflash-r2
data:
data:

data: event: condition.failed
data: data: {"error": "Worker failed for cc-dflash-r2: "}
data:
data:

data: event: job.failed
data: data: {"job_id": "3e4a1c53-ef7b-4570-96b7-e72112a6b10a", "error": "Worker failed for cc-dflash-r2: "}
data:
data:

```
## Scenario: Context + question CPU
Job created: 35ad192c-b13c-4202-92ad-1e8691d55289
### SSE Events
```
data: event: job.started
data: data: {"job_id": "35ad192c-b13c-4202-92ad-1e8691d55289"}
data:
data:

data: event: input.parsed
data: data: {"context_length": 26, "question_length": 28}
data:
data:

data: event: condition.started
data: data: baseline-ar
data:
data:

data: event: condition.completed
data: data: {"condition_id": "baseline-ar", "display_name": "Baseline-AR", "status": "completed", "generated_text": "The meaning of life is 42.", "stop_reason": "eos", "input_tokens_precompression": 69, "input_tokens_final": 69, "prompt_reduction_tokens": null, "prompt_reduction_pct": 0.0, "compression_ratio": 1.0, "compression_applied": true, "compression_bypassed": false, "compression_bypass_reason": null, "compression_total_ms": 0.0, "target_prefill_ms": 272.7812379998795, "draft_prefill_ms": 0.0, "decode_total_ms": 277.4186249989725, "generation_request_e2e_ms": 550.3085060008743, "warm_request_e2e_ms": 563.9161109975248, "cold_start_e2e_ms": 4410.756118995778, "output_tokens": 10, "generation_tok_s": 36.04660645995573, "warm_request_tok_s": 17.733134069020938, "target_forwards_per_output_token": null, "effective_tau": 0.0, "draft_acceptance_rate": 0.0, "verification_calls": 0, "draft_forward_calls": 0, "rollback_tokens": 0, "peak_cuda_allocated_bytes": 2726043136, "peak_cuda_reserved_bytes": 3040870400, "process_current_rss_bytes": null, "resource_composition": "quantized target", "compressor_device": null, "compressor_cuda_verified": null}
data:
data:

data: event: condition.started
data: data: dflash-r1
data:
data:

data: event: condition.completed
data: data: {"condition_id": "dflash-r1", "display_name": "D-Flash", "status": "completed", "generated_text": "The meaning of life is 42.", "stop_reason": "eos", "input_tokens_precompression": 69, "input_tokens_final": 69, "prompt_reduction_tokens": null, "prompt_reduction_pct": 0.0, "compression_ratio": 1.0, "compression_applied": true, "compression_bypassed": false, "compression_bypass_reason": null, "compression_total_ms": 0.0, "target_prefill_ms": 259.05320799938636, "draft_prefill_ms": 0.0, "decode_total_ms": 111.58401600187062, "generation_request_e2e_ms": 370.8620500001416, "warm_request_e2e_ms": 387.6792660012143, "cold_start_e2e_ms": 4706.269974998577, "output_tokens": 10, "generation_tok_s": 89.61857045754974, "warm_request_tok_s": 25.79451850274778, "target_forwards_per_output_token": null, "effective_tau": 9.0, "draft_acceptance_rate": 0.6, "verification_calls": 1, "draft_forward_calls": 1, "rollback_tokens": 6, "peak_cuda_allocated_bytes": 3814551552, "peak_cuda_reserved_bytes": 3848273920, "process_current_rss_bytes": null, "resource_composition": "quantized target + drafter", "compressor_device": null, "compressor_cuda_verified": null}
data:
data:

data: event: condition.started
data: data: cc-dflash-r2
data:
data:

: ping - 2026-07-13 00:18:43.899353+00:00

data: event: condition.failed
data: data: {"error": "Worker failed for cc-dflash-r2: `torch_dtype` is deprecated! Use `dtype` instead!\n"}
data:
data:

data: event: job.failed
data: data: {"job_id": "35ad192c-b13c-4202-92ad-1e8691d55289", "error": "Worker failed for cc-dflash-r2: `torch_dtype` is deprecated! Use `dtype` instead!\n"}
data:
data:

```
## Scenario: Context + question GPU
Job created: 8048e861-2fae-409b-acbe-ec346ee83dce
### SSE Events
```
data: event: job.started
data: data: {"job_id": "8048e861-2fae-409b-acbe-ec346ee83dce"}
data:
data:

data: event: input.parsed
data: data: {"context_length": 26, "question_length": 28}
data:
data:

data: event: condition.started
data: data: baseline-ar
data:
data:

data: event: condition.completed
data: data: {"condition_id": "baseline-ar", "display_name": "Baseline-AR", "status": "completed", "generated_text": "The meaning of life is 42.", "stop_reason": "eos", "input_tokens_precompression": 69, "input_tokens_final": 69, "prompt_reduction_tokens": null, "prompt_reduction_pct": 0.0, "compression_ratio": 1.0, "compression_applied": true, "compression_bypassed": false, "compression_bypass_reason": null, "compression_total_ms": 0.0, "target_prefill_ms": 265.41355600056704, "draft_prefill_ms": 0.0, "decode_total_ms": 278.6323820000689, "generation_request_e2e_ms": 544.1457670021919, "warm_request_e2e_ms": 557.8640380008437, "cold_start_e2e_ms": 4435.382749001292, "output_tokens": 10, "generation_tok_s": 35.88958299899804, "warm_request_tok_s": 17.925514675288813, "target_forwards_per_output_token": null, "effective_tau": 0.0, "draft_acceptance_rate": 0.0, "verification_calls": 0, "draft_forward_calls": 0, "rollback_tokens": 0, "peak_cuda_allocated_bytes": 2726043136, "peak_cuda_reserved_bytes": 3032481792, "process_current_rss_bytes": null, "resource_composition": "quantized target", "compressor_device": null, "compressor_cuda_verified": null}
data:
data:

data: event: condition.started
data: data: dflash-r1
data:
data:

data: event: condition.completed
data: data: {"condition_id": "dflash-r1", "display_name": "D-Flash", "status": "completed", "generated_text": "The meaning of life is 42.", "stop_reason": "eos", "input_tokens_precompression": 69, "input_tokens_final": 69, "prompt_reduction_tokens": null, "prompt_reduction_pct": 0.0, "compression_ratio": 1.0, "compression_applied": true, "compression_bypassed": false, "compression_bypass_reason": null, "compression_total_ms": 0.0, "target_prefill_ms": 255.95274399893242, "draft_prefill_ms": 0.0, "decode_total_ms": 101.78834299949813, "generation_request_e2e_ms": 357.9732899997907, "warm_request_e2e_ms": 373.35349500062875, "cold_start_e2e_ms": 4876.137673003541, "output_tokens": 10, "generation_tok_s": 98.24307681331747, "warm_request_tok_s": 26.784267815634507, "target_forwards_per_output_token": null, "effective_tau": 9.0, "draft_acceptance_rate": 0.6, "verification_calls": 1, "draft_forward_calls": 1, "rollback_tokens": 6, "peak_cuda_allocated_bytes": 3814551552, "peak_cuda_reserved_bytes": 3848273920, "process_current_rss_bytes": null, "resource_composition": "quantized target + drafter", "compressor_device": null, "compressor_cuda_verified": null}
data:
data:

data: event: condition.started
data: data: cc-dflash-r2-gpu
data:
data:

: ping - 2026-07-13 00:19:04.313812+00:00

data: event: condition.failed
data: data: {"error": "Worker failed for cc-dflash-r2-gpu: `torch_dtype` is deprecated! Use `dtype` instead!\n"}
data:
data:

data: event: job.failed
data: data: {"job_id": "8048e861-2fae-409b-acbe-ec346ee83dce", "error": "Worker failed for cc-dflash-r2-gpu: `torch_dtype` is deprecated! Use `dtype` instead!\n"}
data:
data:

```
