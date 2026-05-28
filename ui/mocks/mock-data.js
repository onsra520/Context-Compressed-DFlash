/**
 * HTFSD UI Demo Mock Data
 *
 * Intended path:
 *   ui/mocks/mock-data.js
 *
 * This file is UI-only mock/static data.
 * Replace these objects with FastAPI responses later.
 */

export const benchmarkData = {
    lowTier: {
        baseline: {
            architecture: "Gemma4:E2B Baseline",
            models: "Gemma4:E2B",
            latency_seconds: 0.56,
            decode_tokens_per_sec: 115.6,
            total_tokens_per_sec: 178.2,
            prompt_tokens: 36,
            completion_tokens: 64,
            total_tokens: 100,
            prefill_ms: 91,
            decode_ms: 469,
            memory_gb: "5.8 GB",
            draft_block_size: "-",
            cycle_count: "-",
            accepted_draft_tokens: "-",
            rejected_draft_tokens: "-",
            fallback_tokens: "-",
            acceptance_rate: "-",
            verification_mode: "none",
            correctness_note: "baseline reference",
            speedup: "1.00x",
            response:
                "Baseline E2B generates token by token without a separate drafter. This is slower in the mock run, but simpler and easier to reason about.",
        },
        dflash: {
            architecture: "D-Flash Low-tier",
            models: "Qwen3-0.6B + Gemma4:E2B",
            latency_seconds: 0.42,
            decode_tokens_per_sec: 152.8,
            total_tokens_per_sec: 214.5,
            prompt_tokens: 36,
            completion_tokens: 64,
            total_tokens: 100,
            prefill_ms: 84,
            decode_ms: 336,
            memory_gb: "6.4 GB",
            draft_block_size: 8,
            cycle_count: 8,
            accepted_draft_tokens: 47,
            rejected_draft_tokens: 12,
            fallback_tokens: 5,
            acceptance_rate: "73.4%",
            verification_mode: "text-prefix mock",
            correctness_note: "needs strict verifier later",
            speedup: "1.32x",
            response:
                "D-Flash Low-tier lets Qwen propose draft blocks and uses Gemma4:E2B to verify them. Accepted tokens move faster; rejected tokens fall back safely.",
        },
    },

    fullStack: {
        baseline: {
            architecture: "Gemma4:E4B Baseline",
            models: "Gemma4:E4B",
            latency_seconds: 1.24,
            decode_tokens_per_sec: 68.2,
            total_tokens_per_sec: 104.7,
            prompt_tokens: 44,
            completion_tokens: 96,
            total_tokens: 140,
            prefill_ms: 180,
            decode_ms: 1060,
            memory_gb: "8.9 GB",
            low_tier_accepted_tokens: "-",
            low_tier_rejected_tokens: "-",
            low_tier_fallback_tokens: "-",
            high_tier_accepted_tokens: "-",
            high_tier_rejected_tokens: "-",
            high_tier_fallback_tokens: "-",
            low_tier_acceptance_rate: "-",
            high_tier_acceptance_rate: "-",
            verification_mode: "none",
            correctness_note: "baseline reference",
            speedup: "1.00x",
            response:
                "The E4B baseline generates every output token autoregressively through the stronger target model. It is the clean reference path for final comparison.",
        },
        htfsd: {
            architecture: "Full HTFSD",
            models: "Qwen3-0.6B + Gemma4:E2B + Gemma4:E4B",
            latency_seconds: 0.88,
            decode_tokens_per_sec: 96.4,
            total_tokens_per_sec: 142.1,
            prompt_tokens: 44,
            completion_tokens: 96,
            total_tokens: 140,
            prefill_ms: 146,
            decode_ms: 734,
            memory_gb: "9.7 GB",
            low_tier_accepted_tokens: 68,
            low_tier_rejected_tokens: 18,
            low_tier_fallback_tokens: 10,
            high_tier_accepted_tokens: 72,
            high_tier_rejected_tokens: 14,
            high_tier_fallback_tokens: 10,
            low_tier_acceptance_rate: "70.8%",
            high_tier_acceptance_rate: "75.0%",
            verification_mode: "hierarchical mock",
            correctness_note: "needs equivalence harness later",
            speedup: "1.41x",
            response:
                "Full HTFSD drafts candidate text, verifies it through the low-tier path, then prepares a cleaner accepted stream for the high-tier Gemma4:E4B target.",
        },
    },
};

export const metricDefinitions = [
    {
        label: "Latency",
        description:
            "Total measured request time after models are already loaded. Lower is better.",
    },
    {
        label: "Decode tokens/sec",
        description:
            "Generated output tokens per second during decode. Higher is better.",
    },
    {
        label: "Total tokens/sec",
        description:
            "Prompt plus completion throughput. Useful for end-to-end comparison.",
    },
    {
        label: "Prompt tokens",
        description: "How many tokens are in the input prompt.",
    },
    {
        label: "Completion tokens",
        description: "How many tokens are generated as output.",
    },
    {
        label: "Total tokens",
        description: "Prompt tokens plus generated tokens.",
    },
    {
        label: "Prefill ms",
        description:
            "Mock time spent preparing the prompt/context before decoding.",
    },
    {
        label: "Decode ms",
        description: "Mock time spent generating output tokens.",
    },
    {
        label: "Memory GB",
        description: "Mock memory footprint shown for demo discussion.",
    },
    {
        label: "Draft block size",
        description: "How many tokens the drafter proposes at once.",
    },
    {
        label: "Cycle count",
        description: "How many draft/verify cycles occurred.",
    },
    {
        label: "Accepted draft tokens",
        description:
            "Drafted tokens approved by the verifier. More accepted tokens usually means more speedup.",
    },
    {
        label: "Rejected draft tokens",
        description: "Drafted tokens rejected by the verifier and discarded.",
    },
    {
        label: "Fallback tokens",
        description: "Tokens regenerated safely through the target path.",
    },
    {
        label: "Acceptance rate",
        description: "Percentage of draft tokens accepted.",
    },
    {
        label: "Speedup",
        description:
            "Architecture speed compared with baseline. 1.32x means 32% faster than baseline.",
    },
    {
        label: "Verification mode",
        description: "How the mock UI labels the future verifier behavior.",
    },
    {
        label: "Correctness note",
        description:
            "Reminder that real correctness needs backend verifier and equivalence tests.",
    },
];

export const architectureFlowData = {
    cycles: [
        {
            id: 1,
            contextIn: "Explain caching in one sentence.",
            draft: [
                "Caching",
                "stores",
                "data",
                "temporarily",
                "so",
                "future",
                "access",
                "faster",
            ],
            accepted: ["Caching", "stores", "data", "temporarily"],
            denied: "so",
            unused: ["future", "access", "faster"],
            fallback: "to",
            contextOut: "Caching stores data temporarily to",
        },
        {
            id: 2,
            contextIn: "Caching stores data temporarily to",
            draft: [
                "speed",
                "up",
                "future",
                "requests",
                "and",
                "reduce",
                "latency",
                ".",
            ],
            accepted: [
                "speed",
                "up",
                "future",
                "requests",
                "and",
                "reduce",
                "latency",
                ".",
            ],
            denied: null,
            unused: [],
            fallback: null,
            contextOut:
                "Caching stores data temporarily to speed up future requests and reduce latency.",
        },
    ],

    steps: [
        {
            title: "Prompt enters system",
            desc: "The user prompt becomes the starting context.",
            node: "nPrompt",
            packet: "prompt",
            cycle: "Start",
            payload: ["Explain", "caching", "..."],
        },
        {
            title: "Send context to drafter",
            desc: "The context enters the low-tier D-Flash loop.",
            node: "nQwen",
            edge: "ePromptQwen",
            packet: "context",
            cycle: "Cycle 1",
            dataCycleIndex: 0,
            phase: "draft",
        },
        {
            title: "Qwen drafts a block",
            desc: "Qwen proposes several tokens at once. These are only guesses.",
            node: "nQwen",
            packet: "draft x8",
            cycle: "Cycle 1",
            dataCycleIndex: 0,
            phase: "draft",
        },
        {
            title: "Gemma E2B verifies draft",
            desc: "Accepted prefix is kept; first mismatch uses one fallback token.",
            node: "nVerify",
            edge: "eQwenVerify",
            packet: "verify",
            cycle: "Cycle 1",
            dataCycleIndex: 0,
            phase: "verify",
            kind: "warn",
        },
        {
            title: "Update accepted buffer",
            desc: "Accepted tokens plus fallback become the new context.",
            node: "nBuffer",
            edge: "eVerifyBuffer",
            packet: "context+",
            cycle: "Cycle 1",
            dataCycleIndex: 0,
            phase: "buffer",
            kind: "ok",
        },
        {
            title: "Loop back for next block",
            desc: "The updated context loops back to Qwen.",
            node: "nQwen",
            edge: "eBufferQwen",
            packet: "loop",
            cycle: "Cycle 2",
            dataCycleIndex: 1,
            phase: "draft",
        },
        {
            title: "Second block accepted",
            desc: "Gemma E2B accepts the whole block this time.",
            node: "nVerify",
            edge: "eQwenVerify",
            packet: "accept all",
            cycle: "Cycle 2",
            dataCycleIndex: 1,
            phase: "verify",
            kind: "ok",
        },
        {
            title: "Low-tier output ready",
            desc: "The accepted context is stable enough to bridge into high tier.",
            node: "nBuffer",
            edge: "eVerifyBuffer",
            packet: "context+",
            cycle: "Low-tier done",
            dataCycleIndex: 1,
            phase: "buffer",
            kind: "ok",
        },
        {
            title: "Extract hidden states",
            desc: "Accepted text becomes feature vectors for the high-tier path.",
            node: "nHidden",
            edge: "eLowHigh",
            packet: "h states",
            cycle: "Bridge",
            phase: "hidden",
            kind: "future",
        },
        {
            title: "EAGLE-2 speculates",
            desc: "Feature-level speculation predicts the next high-tier path.",
            node: "nEagle",
            edge: "eHiddenEagle",
            packet: "pred_h",
            cycle: "High-tier",
            phase: "eagle",
            kind: "future",
        },
        {
            title: "Gemma E4B verifies",
            desc: "The high-tier target remains the final authority.",
            node: "nE4B",
            edge: "eEagleE4B",
            packet: "verify G4",
            cycle: "High-tier",
            phase: "e4b",
            kind: "future",
        },
        {
            title: "Final output committed",
            desc: "The response is committed after low-tier and high-tier checks.",
            node: "nFinal",
            edge: "eE4BFinal",
            packet: "final",
            cycle: "Done",
            phase: "final",
            kind: "ok",
        },
    ],
};

export const defaultPrompts = {
    lowTier:
        "Explain how speculative decoding works and why it can speed up inference.",
    fullStack:
        "Describe the hierarchical speculative decoding process and its advantages for multi-tier verification.",
};

export const data = {
    low: {
        baseline: benchmarkData.lowTier.baseline,
        arch: benchmarkData.lowTier.dflash,
    },
    full: {
        baseline: benchmarkData.fullStack.baseline,
        arch: benchmarkData.fullStack.htfsd,
    },
};

export const cycles = architectureFlowData.cycles;

export const metricDefs = metricDefinitions.map(({ label, description }) => [
    label,
    description,
]);
