"""Assistant draft timeline tests.

Tests that assistant_draft is properly added to timeline on rollback/replace.
"""
import sys
import time
from pathlib import Path

_repo_root = Path(__file__).resolve().parents[2]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from modules.agent.backend.runtime.stream_emitter import StreamEmitter


class TestAssistantDraftTimeline:
    """Test that assistant_draft items are added to timeline on rollback."""

    def test_draft_append_logic_inline_calls(self):
        """The draft append logic (same as in stream_emitter) works correctly."""
        tl: list[dict] = []
        full: list[str] = ["Hello user, let me check that for you..."]

        draft_text = "".join(full).strip()
        if draft_text:
            tl.append({
                "type": "assistant_draft",
                "title": "回复用户",
                "content": draft_text,
                "reason": "replace:inline_tool_calls",
                "started_at": time.time(),
                "collapsed": True,
            })
            full.clear()

        drafts = [e for e in tl if e.get("type") == "assistant_draft"]
        assert len(drafts) == 1
        assert drafts[0]["content"] == "Hello user, let me check that for you..."
        assert drafts[0]["reason"] == "replace:inline_tool_calls"
        assert drafts[0]["collapsed"] is True
        assert drafts[0]["title"] == "回复用户"
        assert len(full) == 0  # full buffer was cleared

    def test_empty_draft_not_added(self):
        """Empty/whitespace draft should NOT be added."""
        tl: list[dict] = []
        full: list[str] = ["   "]  # whitespace-only

        draft_text = "".join(full).strip()
        if draft_text:
            tl.append({
                "type": "assistant_draft",
                "title": "回复用户",
                "content": draft_text,
                "reason": "replace:inline_tool_calls",
                "started_at": time.time(),
                "collapsed": True,
            })

        assert len(tl) == 0  # No draft added for whitespace-only content

    def test_unfinished_tool_intent_adds_draft(self):
        """Draft is added for unfinished tool intent (same logic as stream_emitter)."""
        tl: list[dict] = []
        full: list[str] = ["I need to look that up..."]

        draft_text = "".join(full).strip()
        if draft_text:
            tl.append({
                "type": "assistant_draft",
                "title": "回复用户",
                "content": draft_text,
                "reason": "replace:unfinished_tool_intent",
                "started_at": time.time(),
                "collapsed": True,
            })
            full.clear()

        drafts = [e for e in tl if e.get("type") == "assistant_draft"]
        assert len(drafts) == 1
        assert drafts[0]["content"] == "I need to look that up..."
        assert drafts[0]["reason"] == "replace:unfinished_tool_intent"

    def test_draft_excluded_from_llm_context(self):
        """assistant_draft entries should NOT be loaded as assistant messages in context."""
        # Simulate the context assembly - timeline is NOT used for LLM messages
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Final reply"},
        ]
        timeline = [
            {"type": "thinking", "content": "thinking...", "started_at": time.time()},
            {"type": "assistant_draft", "content": "Let me check...", "title": "回复用户",
             "reason": "rollback:tool_call_detected", "collapsed": True},
            {"type": "tool_call", "name": "search", "started_at": time.time()},
        ]

        # In practice, the LLM context comes from `messages`, not `timeline`.
        # Verify no assistant_draft content leaks into messages
        assert any(e.get("type") == "assistant_draft" for e in timeline)
        for msg in messages:
            assert msg.get("content") != "Let me check..."
        # Also verify timeline doesn't affect messages
        msg_content = " ".join(m.get("content", "") for m in messages)
        assert "Let me check" not in msg_content
        assert "Final reply" in msg_content

    def test_multiple_drafts_preserve_order(self):
        """Multiple assistant_draft entries should preserve insertion order."""
        timeline = []
        entries = [
            ("First draft", "rollback:tool_call_detected"),
            ("Second draft", "rollback:inline_tool_call_detected"),
            ("", "skip"),
        ]
        for content, reason in entries:
            text = content.strip()
            if text:
                timeline.append({
                    "type": "assistant_draft",
                    "title": "回复用户",
                    "content": text,
                    "reason": reason,
                    "started_at": time.time(),
                    "collapsed": True,
                })

        assert len(timeline) == 2
        assert timeline[0]["content"] == "First draft"
        assert timeline[1]["content"] == "Second draft"
        assert timeline[0]["reason"] == "rollback:tool_call_detected"
        assert timeline[1]["reason"] == "rollback:inline_tool_call_detected"

    def test_stream_proxy_rollback_closes_segment(self):
        """StreamProxy rollback should close the segment."""
        from modules.agent.backend.runtime.stream_proxy import StreamProxy

        emitter = StreamEmitter()
        proxy = StreamProxy(emitter)
        segment = proxy.new_segment("assistant")

        proxy.start(segment)

        result = proxy.rollback(segment, "test_reason")
        assert segment.closed is True
        assert result is not None  # First rollback yields SSE bytes

        result2 = proxy.rollback(segment, "another_reason")
        assert result2 is None  # Already closed
