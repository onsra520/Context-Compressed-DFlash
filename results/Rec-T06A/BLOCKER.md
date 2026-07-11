# Rec-T06A Blocker - Deterministic DFlash Token Parity

Status: BLOCKED_AT_PARITY_GATE

The shared chat-template prompt repair improved visible behavior, but it did not satisfy the required deterministic target-token equivalence gate.

Evidence from QMSum fixture `qmsum_test_meeting0000_specific_02_86570dc2` at temperature `0.0`, equal prompt IDs, equal max-new-token smoke cap `128`, and EOS stopping:

- Baseline-AR emitted 88 target tokens and stopped at EOS.
- DFlash-R1 emitted 80 tokens and stopped at EOS.
- The first token-ID mismatch is index 61.

The original cache-based verifier showed 3/3 GSM8K and 2/3 QMSum parity at the smoke cap. A correctness-first full-prefix target verifier repaired the QMSum failure but then diverged on GSM8K fixtures 0 and 1; fixture 0 first differed at token 116. Therefore neither available target verification state is equivalent to the Baseline-AR cache path across both datasets. Per the Rec-T06 stop condition, no Rec-T06B/C/D metrics, optimization, n10, or n30 work may proceed until this correctness defect is repaired and both datasets pass parity.
