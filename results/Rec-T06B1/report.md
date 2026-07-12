# Rec-T06B1 final trusted-benchmark repair

The B1 n3 validation uses one explicit parent canonical decision: all limited
rows, worker manifests, benchmark manifests, and resolved config identities
are noncanonical with the identical reason. Task identity is carried as data,
so the same benchmark path supports future trusted task IDs including
`Rec-T06D` without source edits.

Evaluation recomputes quality from raw generated text and stored references;
it never loads models or instantiates `RuntimeEngine`. Artifacts validate row
condition-file binding, fixture order, worker/config/task/mode identity,
canonical reason/value, exact unique trusted condition matrix, LF-only CSV,
and every declared hash. The evaluator inventory includes fixture and dataset
manifests, resolved-config file/hash, per-condition configs, run files,
workers, evaluator dependencies, and produced summaries. DFlash metrics are
globally weighted from raw totals, including correction and bonus tokens.

The existing n3 evidence has been metadata-repaired from its parent manifest
without regenerating model outputs: every row and worker now binds the same
source commit, dirty flag, tracked diff hash, and relevant untracked
source/config inventory. Any absent or mismatched source-state field is
rejected. The n3 evidence remains noncanonical because it is a limited n3
validation, not a complete trusted run.
GSM8K quality reports strict-correct, wrong-numeric, no-final-answer, invalid,
and empty-output counts recomputed from stored raw outputs.

GSM8K CC-DFlash is accurately reported as `target + drafter; compressor
bypassed and not loaded`. QMSum CC-DFlash loads the CPU compressor, records a
current-RSS delta, and reports compression-inclusive warm E2E. QMSum semantic
correctness remains **NOT_CLAIMED**.

No n10, n30, worktree, push, Rec-T06C, or Rec-T06D run occurred.
