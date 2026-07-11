from __future__ import annotations

from ccdf.config import resolve_config
from ccdf.compression.schemas import CompressionConfig


def test_compression_uses_resolved_configuration() -> None:
    resolved = resolve_config(dataset="qmsum", condition_id="cc-dflash-r2")
    config = CompressionConfig(
        keep_rate=resolved.data["compression"]["keep_rate"],
        min_context_tokens=resolved.data["compression"]["min_context_tokens"],
        chunk_max_words=resolved.data["compression"]["chunk_max_words"],
        device_map=resolved.data["models"]["compression"]["device"],
    )
    assert resolved.data["models"]["compression"]["path"].startswith("models/")
    assert config.keep_rate == 0.5
    assert config.chunk_max_words == 180
