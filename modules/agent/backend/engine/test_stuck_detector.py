"""Tests for stuck_detector.py — DB-backed stuck detection (跨 worker 持久化)."""
import pytest

from app.database import AsyncSessionLocal
from .stuck_detector import detect_stuck, reset


OWNER_ID = 4  # admin 何焜华


async def _run(session_key: str, calls: list[dict]) -> dict:
    """跑一串 detect_stuck，返回最后一次结果。每个 session_key 独立隔离。"""
    async with AsyncSessionLocal() as db:
        await reset(db, session_key)
        result = {"stuck": False, "reason": ""}
        for c in calls:
            result = await detect_stuck(db, OWNER_ID, session_key=session_key, **c)
        await reset(db, session_key)  # 清理
        return result


@pytest.mark.asyncio
async def test_not_stuck_single_call():
    r = await _run("test_single", [
        dict(tool_name="search", tool_args={"q": "hello"}, error_text=None, is_empty_response=False),
    ])
    assert not r["stuck"]


@pytest.mark.asyncio
async def test_stuck_same_tool_3_times():
    r = await _run("test_same_tool", [
        dict(tool_name="search", tool_args={"q": "hello"}, error_text=None, is_empty_response=False),
    ] * 3)
    assert r["stuck"]
    assert "search" in r["reason"]


@pytest.mark.asyncio
async def test_stuck_same_error_3_times():
    r = await _run("test_same_error", [
        dict(tool_name=None, tool_args=None, error_text="timeout", is_empty_response=False),
    ] * 3)
    assert r["stuck"]
    assert "timeout" in r["reason"]


@pytest.mark.asyncio
async def test_stuck_empty_response_3_times():
    r = await _run("test_empty", [
        dict(tool_name=None, tool_args=None, error_text=None, is_empty_response=True),
    ] * 3)
    assert r["stuck"]


@pytest.mark.asyncio
async def test_not_stuck_different_tools():
    r = await _run("test_diff_tools", [
        dict(tool_name="search", tool_args={"q": "a"}, error_text=None, is_empty_response=False),
        dict(tool_name="fetch", tool_args={"url": "b"}, error_text=None, is_empty_response=False),
        dict(tool_name="search", tool_args={"q": "c"}, error_text=None, is_empty_response=False),
    ])
    assert not r["stuck"]


@pytest.mark.asyncio
async def test_reset_clears_history():
    async with AsyncSessionLocal() as db:
        await reset(db, "test_reset")
        for _ in range(3):
            await detect_stuck(db, OWNER_ID, tool_name="search", tool_args={"q": "x"}, error_text=None, is_empty_response=False, session_key="test_reset")
        await reset(db, "test_reset")
        r = await detect_stuck(db, OWNER_ID, tool_name="other", tool_args={"q": "y"}, error_text=None, is_empty_response=False, session_key="test_reset")
        await reset(db, "test_reset")
        assert not r["stuck"]
