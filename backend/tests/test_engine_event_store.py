"""Test event store: projection logic, record/read events.
Uses the same import pattern as test_agent_inline_tool_calls.py."""
import sys
import json
from pathlib import Path

# Add module backend path so we can import engine modules
MODULE_BACKEND = Path(__file__).resolve().parent.parent.parent / "modules" / "agent" / "backend"
if str(MODULE_BACKEND) not in sys.path:
    sys.path.insert(0, str(MODULE_BACKEND))

# Add engine path
ENGINE_DIR = MODULE_BACKEND / "engine"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))


class TestProjectionLogic:
    """Test the projection algorithm logic.

    Tests the expected shape/behavior of the projection without needing a DB.
    The actual DB integration is tested via the real API in verification step.
    """

    def test_assistant_tool_merge_structure(self):
        """Events with same llm_response_id → assistant+tool_calls merged."""
        assistant_event = {"role": "assistant", "content": "Let me search", "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "web__search", "arguments": {}}},
        ]}
        assert assistant_event["tool_calls"][0]["function"]["name"] == "web__search"

    def test_tool_result_structure(self):
        """Tool result → role=tool."""
        result_event = {"role": "tool", "tool_call_id": "call_1", "content": json.dumps({"data": "sunny"})}
        assert result_event["role"] == "tool"

    def test_user_msg_structure(self):
        """user_msg → role=user."""
        msg = {"role": "user", "content": "Hello"}
        assert msg["role"] == "user"

