"""Workflow strategy injector: detect keywords and inject workflow guidance.

Contract: inject(messages, diagnosis, current_user_input) → (messages, diagnosis)
"""

from ..workflow_strategy import apply_workflow_injection as _apply_workflow_injection


def inject(
    messages: list[dict],
    diagnosis: dict,
    current_user_input: str,
) -> tuple[list[dict], dict]:
    """Inject project workflow constraints into the first system message."""
    wf_diag = _apply_workflow_injection(current_user_input, messages)
    diagnosis["workflow_injected"] = wf_diag.get("workflow_injected", False)
    if wf_diag.get("workflow_label"):
        diagnosis["workflow_label"] = wf_diag["workflow_label"]
    return messages, diagnosis
