"""Workflow strategy: project-level behavior constraints injected at runtime.

Extracts the inline keyword-matching pattern from ``engine.py`` into a
configurable strategy that maps trigger keywords to structured workflow
instructions.  This reduces reliance on prompt text alone — the strategy
can be observed, tested, and extended without touching engine logic.
"""
import logging
from typing import Any

logger = logging.getLogger("v2.agent").getChild("engine.workflow_strategy")

# Workflow definitions are intentionally empty by default. Concrete project,
# enterprise, or team workflows should be stored as editable recipes/config,
# not compiled into the global Agent runtime.
WORKFLOW_DEFINITIONS: list[dict[str, Any]] = []


def match_workflow(user_input: str) -> dict | None:
    """Match user input against known workflow triggers.

    Returns the first matching workflow definition, or None if no trigger
    is detected.  Matching is case-insensitive substring match.
    """
    if not user_input:
        return None
    lower_input = user_input.lower()
    for wf in WORKFLOW_DEFINITIONS:
        for kw in wf["keywords"]:
            if kw.lower() in lower_input:
                logger.debug("Workflow triggered: '%s' by keyword '%s'", wf["label"], kw)
                return wf
    return None


def format_workflow_injection(workflow: dict | None = None) -> str | None:
    """Format workflow as prompt injection block.

    Args:
        workflow: A matched workflow definition dict, or None to use default.

    Returns:
        Formatted prompt injection string, or None if no workflow.
    """
    if workflow is None:
        return None

    steps = workflow.get("workflow_steps", [])
    lines = [f"<{workflow['label']}>"]
    lines.append(f"检测到 {workflow['label']} 相关任务，请遵循以下工作流：")
    for i, step in enumerate(steps, 1):
        lines.append(f"{i}. {step['action']} — {step['detail']}")
    lines.append(f"</{workflow['label']}>")
    return "\n".join(lines)


def get_all_workflows() -> list[dict[str, Any]]:
    """Return all registered workflow definitions (for admin / diagnostics)."""
    return [
        {
            "label": wf["label"],
            "keywords": wf["keywords"],
            "step_count": len(wf.get("workflow_steps", [])),
        }
        for wf in WORKFLOW_DEFINITIONS
    ]


def apply_workflow_injection(user_input: str, messages: list[dict]) -> dict:
    """Main entry: detect workflow trigger, inject prompt, return diagnosis.

    This replaces the inline code in ``engine.py`` assemble_context().

    Args:
        user_input: The current user input text.
        messages: The assembled messages list (mutated in place if injection).

    Returns:
        Diagnosis dict with keys:
            ``workflow_injected`` — bool or error string
            ``workflow_label`` — the matched workflow label (if any)
    """
    diagnosis = {"workflow_injected": False, "workflow_label": None}
    try:
        matched = match_workflow(user_input)
        if matched and messages:
            injection = format_workflow_injection(matched)
            for msg in messages:
                if msg["role"] == "system":
                    msg["content"] += "\n\n---\n\n" + injection
                    break
            diagnosis["workflow_injected"] = True
            diagnosis["workflow_label"] = matched["label"]
        return diagnosis
    except Exception as e:
        logger.warning("Workflow injection failed (non-fatal): %s", e)
        diagnosis["workflow_injected"] = f"降级: {e}"
        return diagnosis
