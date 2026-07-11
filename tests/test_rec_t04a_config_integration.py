from __future__ import annotations

from ccdf.config import resolve_config
from ccdf.compression.schemas import CompressionConfig
from ccdf.paths import find_shared_root, find_worktree_root
import pytest

WORKTREE_ROOT = find_worktree_root()


@pytest.mark.skipif(
    not (WORKTREE_ROOT / "data/eval/qmsum/qmsum_n10.jsonl").is_file(),
    reason="resolved compression config requires frozen fixture identity",
)
def test_compression_uses_resolved_configuration() -> None:
    resolved = resolve_config(dataset="qmsum", condition_id="cc-dflash-r2")
    config = CompressionConfig(
        keep_rate=resolved.data["compression"]["keep_rate"],
        min_context_tokens=resolved.data["compression"]["min_context_tokens"],
        chunk_max_words=resolved.data["compression"]["chunk_max_words"],
        device_map=resolved.data["models"]["compression"]["device"],
    )
    shared = find_shared_root(WORKTREE_ROOT)
    assert resolved.data["models"]["compression"]["path"] == str(
        (shared / "models/llmlingua-2-bert-base-multilingual-cased-meetingbank").resolve()
    )
    assert config.keep_rate == 0.5
    assert config.chunk_max_words == 180
