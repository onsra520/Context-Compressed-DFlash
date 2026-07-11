# Rec-T06A2 blocker

Efficient cached DFlash correctly uses one target forward per proposed block and
demonstrates target-forward savings, but it is not exactly token-equivalent for
the locked NF4 target. The original QMSum fixture diverges at token 16 despite
consistent verifier positions, correction index, and cache crop state.

No oracle fallback was applied: doing so would violate the production-path
requirements. No Rec-T06B/C/D, quality, n30, or performance claim was run.
