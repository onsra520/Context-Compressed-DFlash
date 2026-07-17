"""CCDF Rec-2 standalone inference runtime."""

import os

# Torch 2.13's experimental native Triton overrides fail to load on this
# Python/CUDA host. Select the stable ATen kernels before Torch is imported.
os.environ.setdefault("TORCH_DISABLE_NATIVE_JIT", "1")
os.environ.setdefault("TRITON_CACHE_DIR", "/tmp/ccdf-rework-triton-cache")

from .config import Rec2Config, load_config

__all__ = ["Rec2Config", "load_config"]
__version__ = "0.1.0"
