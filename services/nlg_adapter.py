# services/nlg_adapter.py
def build_emphetic_prompt(history_text: str, last_emotion: str) -> str:
    return (
        "You are a concise, empathetic assistant. "
        f"User emotion: {last_emotion}. "
        "Respond in 1-3 short sentences, supportive and non-intrusive.\n\n"
        f"Context:\n{history_text}\n---\nReply:"
    )

def rationale_for(action: str, policy_reason: str) -> str:
    mapping = {
        "hint": "You seemed quiet, so here's a gentle nudge.",
        "assist": "You sounded frustrated, this may help.",
        "recommend": "You seemed low, this may comfort you."
    }
    return mapping.get(action, policy_reason)
