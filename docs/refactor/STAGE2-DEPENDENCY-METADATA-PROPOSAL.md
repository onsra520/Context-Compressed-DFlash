# Stage 2 dependency metadata proposal

The locked `CCDF` environment contains `llmlingua==0.2.2` and `tiktoken==0.13.0`, while
`pyproject.toml` does not declare LLMLingua. This task did not install, remove, update, or modify any
dependency metadata because the environment was explicitly frozen.

A separate metadata-only change should declare the tested LLMLingua/tiktoken compatibility range and
validate a clean installation. It must be reviewed independently because adding a project dependency can
change resolver output and is not evidence that the current runtime environment remained unchanged.
