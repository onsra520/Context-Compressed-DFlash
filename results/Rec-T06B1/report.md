# Rec-T06B1 trusted benchmark contract repair

All six workers used task identity `Rec-T06B1`, benchmark mode, matching
resolved condition hashes, matching fixture order, and distinct PIDs. Because
the requested n3 runs are limited, every run and manifest is correctly
`canonical: false`; no canonical result is claimed.

Evaluation recomputed GSM8K and QMSum quality from raw generated text and the
stored reference answer, without loading models or calling `RuntimeEngine`.
GSM8K `wrong_numeric` behavior remains delegated to the existing evaluator;
QMSum semantic correctness remains `NOT_CLAIMED`.

Artifact, worker-manifest, config, fixture, evaluator, and summary hashes pass
verification. Weighted effective tau and draft acceptance are computed from
raw totals. Current RSS uses `/proc/self/statm`; `ru_maxrss` is retained only
as a separate peak field. Unsupported GPU composition deltas remain explicit
null fields.

No n10/n30, worktree, push, Rec-T06C, or Rec-T06D activity occurred.
