# Stage 2 selection-policy analysis

## Final decision

The production selection policy is unchanged. Proposal rows use strict target argmax. The existing
one-ULP/lower-token-ID rule remains restricted to correction-row selection. No candidate policy was
accepted and its production activation count is therefore zero.

## Final mismatch

On safeguarded `mock-04`, C3 and C4 have identical prompt IDs, prefix, position 131, cache position 131,
cache length 131, and logical context. The mismatch is the first correction row after zero proposals are
accepted. Baseline's one-query SDPA forward selects token 353 at logit 39.0625 over token 9 at 39.03125.
The block-query target forward selects token 9 at 39.25 over token 353 at 38.96875. The block margin is
0.28125, outside the one-ULP rule, so widening that rule would be an arbitrary epsilon.

## Rejected diagnostics

- Fixed block sizes 2, 4, 8, and 16 all reproduce the mismatch at index 1.
- An explicit all-allowed Baseline decode mask does not change the winner.
- A fair eager backend fixes `mock-04` and preserves quality, but creates new proposal-row mismatches on
  `mock-05`; it is rejected even though aggregate DFlash speed was competitive.
- FP32 attention variants either emit EOS immediately or move the mismatch and produce an incorrect $20.
- Oracle replay, per-token target replay, sequentially disguised block verification, prompt/token rules,
  workload changes, and output substitution were not implemented.

Because no generic candidate preserved the accepted-proposal contract across canonical inputs, R4/R5
were not authorized and Stage 3 remains closed.
