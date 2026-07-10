from __future__ import annotations

from ccdf.demo.contracts import RunRequest

def gsm8k_row_to_request(row: dict, condition: str, **kwargs) -> RunRequest:
    context = row.get("context", "")
    question = row.get("question", "")
    prompt = f"{context}\n\nQuestion: {question}".strip()
    
    metadata = kwargs.pop("metadata", {})
    metadata["context"] = context
    metadata["question"] = f"Question: {question}"
    
    return RunRequest(
        source_type="dataset",
        dataset="gsm8k",
        split=row.get("split", "test"),
        fixture_id=row.get("id"),
        condition=condition,
        prompt=prompt,
        prompt_profile="gsm8k_concise_final_answer_v1",
        reference_answer=row.get("expected_answer"),
        metadata=metadata,
        **kwargs
    )
