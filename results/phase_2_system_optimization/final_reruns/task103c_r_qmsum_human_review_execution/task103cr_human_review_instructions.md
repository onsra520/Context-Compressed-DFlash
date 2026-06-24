# Task103C-R Human Review Instructions

Fill `task103cr_human_labels_input.csv` using the same columns as the review sheet.

Allowed `human_label` values:

- `correct_supported`, `partially_correct_or_incomplete`, `unsupported_or_wrong`, `cannot_determine_from_available_context`

Allowed `confidence` values: empty, `low`, `medium`, `high`.

Boolean columns may be empty, `true`, or `false`.

Use only the packet content. Do not use external knowledge. If the available context is insufficient, use `cannot_determine_from_available_context`.

This task does not run an LLM judge and does not infer labels automatically.
