# Real LLMLingua CPU Smoke Report

## Result

PASS

## Real Model Load Status

- Real LLMLingua-2 model loaded successfully on CPU
- Model name: `microsoft/llmlingua-2-xlm-roberta-large-meetingbank`
- Device: `cpu`
- First run downloaded model files: yes

## Exact Command

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
import json
from pathlib import Path

from ccdf.compression.llmlingua import LLMLinguaCompressor

context = (
    "The city library bought 48 new math books and 16 science books. "
    "A local donor later added 12 more math books. "
    "The building also has old newspapers, chairs, posters, and unrelated historical notes. "
    "Only the book counts matter for answering the question."
)
question = "How many math books does the library have now?"
keep_rate = 0.5
model_name = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank"

comp = LLMLinguaCompressor(model_name=model_name, device_map="cpu")
merged, info = comp.compress(context=context, question=question, keep_rate=keep_rate)

payload = {
    "model_name": model_name,
    "device": "cpu",
    "keep_rate": keep_rate,
    "context_word_count": len(context.split()),
    "merged_word_count": len(merged.split()),
    "question": question,
    "question_preserved": question in merged,
    "merged": merged,
    "info": info,
}
Path("results").mkdir(exist_ok=True)
Path("results/llmlingua_cpu_smoke.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(payload, indent=2, ensure_ascii=False))
assert merged.strip()
assert question in merged
assert info["N_compressed"] <= info["N_original"]
assert info["R_actual"] >= 1.0
PY
```

## Sample Input Summary

- context: one short synthetic paragraph with counts, entities, and irrelevant filler
- question: `How many math books does the library have now?`
- keep_rate: `0.5`
- original context word count: `42`

## Sample Compression Output Summary

- merged output was non-empty
- compressed output kept the key counts and question-relevant terms
- merged output word count: `30`
- saved artifact: `results/llmlingua_cpu_smoke.json`

Compressed output summary:

`city library bought 48 math 16 science local donor added 12 math building old newspapers chairs posters notes book counts question`

## Info Dict Values

- `t_compress_ms`: `1004.4160070028738`
- `R_actual`: `2.2`
- `N_original`: `52`
- `N_compressed`: `24`
- `keep_rate`: `0.5`
- `strategy`: `llmlingua-2`

## Protected-Question Validation

PASS

- final merged prompt contains the original question unchanged
- `question_preserved`: `true`
- `N_compressed <= N_original`: true
- `R_actual >= 1.0`: true

## Tests And Verification

- `python3 -m compileall src tests scripts`: PASS
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_compression.py -q`: `5 passed`
- `PYTHONPATH=src .venv/bin/python scripts/synthetic_probe.py --config config.yml --dry-run`: `DRY-RUN-PASS`
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_dflash_core.py -q`: `7 passed`
- real CPU compression smoke command: PASS

## DFlash Baseline Control Path

Confirmed unchanged.

- No DFlash generation logic was modified
- No DFlash-R1 baseline behavior was modified
- `results/dflash_r1_n20.jsonl` remains the control artifact

## Next Step

CC-LLM-R2/R3 smoke comparison using the same JSONL schema.
