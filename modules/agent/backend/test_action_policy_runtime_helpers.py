"""Regression tests for agent action policy and runtime helper contracts."""

from modules.agent.backend.services.action_policy import (
    _match_sensitive,
    _serialize_tool_args_for_approval,
)


def test_terminal_exec_is_not_outbound_approval_action() -> None:
    assert _match_sensitive("terminal-tools__exec") is False


def test_im_send_is_outbound_approval_action() -> None:
    assert _match_sensitive("im__send") is True


def test_approval_args_are_serialized_and_redacted() -> None:
    payload = _serialize_tool_args_for_approval({"command": "ls", "api_key": "secret-value"})
    assert "ls" in payload
    assert "secret-value" not in payload
    assert "[REDACTED]" in payload
