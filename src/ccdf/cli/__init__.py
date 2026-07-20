"""Public command-line entrypoint."""

from .commands import main
from .parser import build_parser

__all__ = ["build_parser", "main"]
