from __future__ import annotations

from ccdf.demo.contracts import RunRequest

def interactive_to_request(prompt: str, condition: str, **kwargs) -> RunRequest:
    return RunRequest(
        source_type="interactive",
        condition=condition,
        prompt=prompt,
        **kwargs
    )
