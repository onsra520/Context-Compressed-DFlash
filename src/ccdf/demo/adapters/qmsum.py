from __future__ import annotations

from ccdf.demo.contracts import RunRequest

def qmsum_row_to_request(row: dict, condition: str, **kwargs) -> RunRequest:
    context = row.get("context", "")
    question = row.get("question", "")
    prompt = f"Meeting transcript:\n{context}\n\nQuestion: {question}".strip()
    
    metadata = kwargs.pop("metadata", {})
    metadata["context"] = f"Meeting transcript:\n{context}"
    metadata["question"] = f"Question: {question}"
    
    return RunRequest(
        source_type="dataset",
        dataset="qmsum",
        split=row.get("split", "test"),
        fixture_id=row.get("id"),
        condition=condition,
        prompt=prompt,
        prompt_profile="qmsum_demo_safe",
        reference_answer=row.get("expected_answer"),
        metadata=metadata,
        **kwargs
    )
