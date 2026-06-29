"""Tests for model_client inline DSML tool-call fallback."""

from modules.agent.backend.services.model_client import (
    final_clean_content,
    parse_inline_tool_calls,
)

DSML_TOOL_CALL = (
    '<｜｜DSML｜｜tool_calls>\n'
    '<｜｜DSML｜｜invoke name="skill_use">\n'
    '<｜｜DSML｜｜parameter name="name" string="true">web-tools__search</｜｜DSML｜｜parameter>\n'
    '<｜｜DSML｜｜parameter name="args" string="false">{"query":"巨量千川 创意灵感 对标视频 行业视频 在哪里找"}</｜｜DSML｜｜parameter>\n'
    '</｜｜DSML｜｜invoke>\n'
    '</｜｜DSML｜｜tool_calls>'
)


def test_parse_dsml_tool_calls_container():
    clean, calls = parse_inline_tool_calls(DSML_TOOL_CALL)

    assert clean == ""
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "skill_use"
    assert calls[0]["function"]["arguments"] == {
        "name": "web-tools__search",
        "args": {"query": "巨量千川 创意灵感 对标视频 行业视频 在哪里找"},
    }


def test_final_clean_content_strips_dsml_tool_calls():
    cleaned = final_clean_content(f"回复前{DSML_TOOL_CALL}回复后")

    assert cleaned == "回复前回复后"
    assert "DSML" not in cleaned
    assert "tool_calls" not in cleaned
    assert "invoke" not in cleaned
