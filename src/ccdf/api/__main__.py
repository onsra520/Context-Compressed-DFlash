"""Run the live demo backend with ``python -m ccdf.api``."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "ccdf.api.app:app",
        host=os.environ.get("CCDF_DEMO_HOST", "127.0.0.1"),
        port=int(os.environ.get("CCDF_DEMO_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
