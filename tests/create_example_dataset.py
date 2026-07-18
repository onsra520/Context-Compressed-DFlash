#!/usr/bin/env python3
from pathlib import Path
import json

rows = [
    {"id": "math-1", "dataset": "gsm8k", "prompt": "What is 17 multiplied by 6?"},
    {
        "id": "math-2",
        "dataset": "gsm8k",
        "prompt": "A shop sold 12 boxes with 8 items in each box. How many items were sold?",
    },
]
path = Path("data/benchmark/prompts.jsonl")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
print(path)
