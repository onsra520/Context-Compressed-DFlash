from __future__ import annotations

MVP_CONDITIONS = [
    {
        "name": "Baseline-AR",
        "compression": "none",
        "keep_rate": 1.0,
        "generation_mode": "autoregressive",
        "uses_dflash": False,
        "uses_draft": False,
        "uses_compression": False,
    },
    {
        "name": "DFlash-R1",
        "compression": "none",
        "keep_rate": 1.0,
        "generation_mode": "dflash",
        "uses_dflash": True,
        "uses_draft": True,
        "uses_compression": False,
    },
    {
        "name": "LLMLingua-AR-R2",
        "compression": "llmlingua",
        "keep_rate": 0.5,
        "generation_mode": "autoregressive",
        "uses_dflash": False,
        "uses_draft": False,
        "uses_compression": True,
    },
    {
        "name": "LLMLingua-AR-R3",
        "compression": "llmlingua",
        "keep_rate": 0.33,
        "generation_mode": "autoregressive",
        "uses_dflash": False,
        "uses_draft": False,
        "uses_compression": True,
    },
    {
        "name": "CC-LLM-R2",
        "compression": "llmlingua",
        "keep_rate": 0.5,
        "generation_mode": "dflash",
        "uses_dflash": True,
        "uses_draft": True,
        "uses_compression": True,
    },
    {
        "name": "CC-LLM-R3",
        "compression": "llmlingua",
        "keep_rate": 0.33,
        "generation_mode": "dflash",
        "uses_dflash": True,
        "uses_draft": True,
        "uses_compression": True,
    },
]

CONDITIONS = MVP_CONDITIONS
