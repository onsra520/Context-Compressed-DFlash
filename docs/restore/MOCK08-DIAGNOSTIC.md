# Mock-08 Full Execution-Contract Diagnostic

The isolated instrumented Baseline and DFlash requests reproduce the live raw rows exactly and diverge first at generated-token index 21: Baseline token 353 versus DFlash token 24768.

| Contract field | Baseline | DFlash | Result |
|---|---|---|:---:|
| Prompt input IDs | 155 tokens, same SHA-256 | 155 tokens, same SHA-256 | PASS |
| Generated prefix before index 21 | Same 21 IDs | Same 21 IDs | PASS |
| Logical context predicting index 21 | length 176, same SHA-256 | length 176, same SHA-256 | PASS |
| Selected position ID | 175 | block offset 4 -> 175 | PASS |
| Derived cache position | 175 | block offset 4 -> 175 | PASS |
| Visible keys | caller all-ones; optimized effective mask | Boolean causal row keys 0..175 | PASS |
| KV cache | 36 layers, FP16, CUDA; length 175 before q=1 | 36 layers, FP16, CUDA; length 171 before q=16 | Logically equivalent at offset 4 |
| Selected logits | 353=37.21875; 24768=37.21875 | 24768=37.28125; 353=37.25 | One FP16 ULP shape effect |
| Deterministic selection | exact tie -> lower ID 353 | one-ULP winner -> 24768 | Root cause |
| Stopping | downstream of mismatch | downstream of mismatch | Not causal |

The evidence rules out prompt/tokenizer, prefix, position, cache-position, visible-mask, KV dtype/device, selected-index, and stopping defects. The authorized repair boundary is generic correction-row selection at a one-representable-value band. Replay, sequential verification, oracle fallback, token-specific logic, and workload changes remain rejected.
