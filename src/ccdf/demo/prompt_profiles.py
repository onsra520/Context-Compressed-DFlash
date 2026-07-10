from __future__ import annotations

PROMPT_PROFILES = {
    "raw": None,
    "gsm8k_concise_final_answer_v1": "End with exactly one line:\nFinal answer: <number>",
    "qmsum_demo_safe": (
        "Answer only the question using the meeting context.\n"
        "First focus on the exact evidence in the context that answers the question.\n"
        "Include the concrete names, numbers, organizations, decisions, reasons, constraints, and supporting details that are needed for the answer.\n"
        "Do not answer from the general topic of the meeting.\n"
        "Do not replace specific evidence with broad summaries.\n"
        "Do not say the information is missing or not discussed unless the meeting context clearly lacks the answer.\n"
        "Do not repeat the full meeting context.\n"
        "Use 3-7 concise sentences."
    ),
}

def apply_prompt_profile(prompt: str, profile: str) -> str:
    if profile not in PROMPT_PROFILES:
        raise ValueError(f"Unknown prompt profile: {profile}")
    suffix = PROMPT_PROFILES[profile]
    if not suffix:
        return prompt
    prompt = prompt.strip()
    if prompt.endswith(suffix):
        return prompt
    if not prompt:
        return suffix
    return f"{prompt}\n\n{suffix}"
