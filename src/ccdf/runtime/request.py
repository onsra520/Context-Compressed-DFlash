"""Public execution entrypoint for the unified real runtime."""

from ccdf.runtime.engine import RuntimeEngine
from ccdf.runtime.schemas import RuntimeRequest


def execute_request(request: RuntimeRequest) -> dict:
    engine = RuntimeEngine(request.resolved)
    try:
        return engine.execute(request)
    finally:
        engine.close()
