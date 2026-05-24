# Feature Tier

`Gemma E2B -> Gemma E4B` is required by the HTFS-Decoding proposal.

The current GGUF / llama.cpp runtime path does not provide the hidden-state
interface needed for real feature-level speculation. The high-tier
implementation is therefore blocked until a backend with hidden-state access is
added, such as a future Transformers / PyTorch backend.

Current capability result for llama.cpp-backed runs:

```text
supports_hidden_states = False
readiness = blocked
reason = hidden_states_unavailable
```

This package contains contracts and capability checks only. It does not claim
to implement Gemma E2B to Gemma E4B feature speculation.
