"""Public configuration loading and validation surface."""

from .loader import load_config
from .model import Rec2Config

__all__ = ["Rec2Config", "load_config"]
