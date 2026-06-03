from __future__ import annotations

CONDITIONS = [
    {"name": "Baseline-AR", "compression": "passthrough", "keep_rate": 1.0},
    {"name": "DFlash-R1", "compression": "passthrough", "keep_rate": 1.0},
    {"name": "LLMLingua-AR", "compression": "llmlingua", "keep_rate": 0.5},
    {"name": "LLMLingua-AR-R3", "compression": "llmlingua", "keep_rate": 0.33},
    {"name": "CC-LLM-R2", "compression": "pipeline", "keep_rate": 0.5},
    {"name": "CC-LLM-R3", "compression": "pipeline", "keep_rate": 0.33},
    {"name": "CC-LLM-R4", "compression": "pipeline", "keep_rate": 0.25},
]