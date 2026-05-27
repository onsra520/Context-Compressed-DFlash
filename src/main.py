"""FastAPI entrypoint for serving the HTFSD UI mock demo.

Expected project layout:

project-root/
├─ src/
│  └─ main.py
└─ ui/
   ├─ index.html
   ├─ mocks/
   │  └─ mock-data.js
   ├─ scripts/
   └─ styles/

Run from project root:

    uvicorn src.main:app --reload

Then open:

    http://127.0.0.1:8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = PROJECT_ROOT / "ui"
INDEX_HTML = UI_DIR / "index.html"

app = FastAPI(
    title="HTFSD UI Mock Demo",
    description="Serves the static HTFSD UI demo with mocked frontend data.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check for local development."""
    return {"status": "ok"}


@app.get("/api/mock/status")
def mock_status() -> dict[str, object]:
    """Tiny mock API so the FastAPI app has at least one backend endpoint."""
    return {
        "status": "mock-ready",
        "ui_dir_exists": UI_DIR.exists(),
        "index_exists": INDEX_HTML.exists(),
        "mode": "static-ui-demo",
    }


@app.get("/")
def serve_index() -> Response:
    """Serve the UI entry page."""
    if not INDEX_HTML.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": "ui/index.html not found",
                "expected_path": str(INDEX_HTML),
                "hint": "Run uvicorn from the project root and make sure ui/index.html exists.",
            },
        )

    return FileResponse(INDEX_HTML)


# Mount after route definitions so `/` and `/health` stay explicit.
if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=UI_DIR, html=True), name="ui")
    app.mount("/styles", StaticFiles(directory=UI_DIR / "styles"), name="styles")
    app.mount("/scripts", StaticFiles(directory=UI_DIR / "scripts"), name="scripts")
    app.mount("/mocks", StaticFiles(directory=UI_DIR / "mocks"), name="mocks")
    app.mount("/assets", StaticFiles(directory=UI_DIR / "assets"), name="assets")
