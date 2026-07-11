"""Prompt identity checks shared across datasets and conditions."""

from __future__ import annotations

from ccdf.prompts.schemas import EncodedPrompt


def audit_encoded_prompt(encoded: EncodedPrompt, policy_text: str) -> dict[str, object]:
    user_content = "\n".join(message["content"] for message in encoded.messages if message["role"] == "user")
    audit_content = user_content.replace(encoded.parts.context, "", 1) if encoded.parts.context else user_content
    return {
        "dataset": encoded.dataset,
        "structured_hash": encoded.structured_hash,
        "rendered_hash": encoded.rendered_hash,
        "input_ids_hash": encoded.input_ids_hash,
        "input_tokens": len(encoded.input_ids_list),
        "chat_template_used": encoded.chat_template_used,
        "enable_thinking_applied": encoded.enable_thinking_applied,
        "policy_occurrence": audit_content.count(policy_text),
        "question_occurrence": audit_content.count(encoded.parts.question),
        "reference_answer_present": False,
        "pass": (
            encoded.chat_template_used
            and encoded.enable_thinking_applied
            and audit_content.count(policy_text) == 1
            and audit_content.count(encoded.parts.question) == 1
        ),
    }
