# H.T.F.S.D - Hierarchical Token-Feature Speculative Decoding

<!-- markdownlint-disable MD033 -->
<div align="center">

**Exploring hierarchical speculative decoding from lightweight token drafting to feature-level verification.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Version](https://img.shields.io/badge/version-0.1.0-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/status-IN%20PROGRESS-orange?style=flat-square)

</div>
<!-- markdownlint-enable MD033 -->

---

## What is HTFSD?

HTFSD is an experimental framework for hierarchical speculative decoding on
local hardware. It explores how smaller and larger language models can work
together, where lightweight tiers draft possible continuations and stronger
tiers verify the final output.

The project sits between token-level drafting and feature-level speculation,
with the long-term goal of accelerating local LLM inference without changing
the verified output. Current work focuses on MVP correctness, tracing,
fallback behavior, and benchmarkable experiments.
