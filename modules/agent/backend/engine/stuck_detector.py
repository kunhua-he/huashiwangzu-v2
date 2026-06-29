"""stuck_detector：检测重复工具调用、重复报错、空响应，打断循环。

抄 OpenHands stuck detector。维护最近若干轮的
(工具名+规范化参数指纹)和(报错指纹)。

持久化：文件存储 _round_history 确保跨 worker 一致。"""
import hashlib
import json
import logging
from pathlib import Path

from .file_state_lock import read_json_locked, update_json_locked

logger = logging.getLogger("v2.agent").getChild("engine.stuck_detector")

STUCK_WINDOW_SIZE = 5
STUCK_THRESHOLD = 3

# File-backed round history for cross-worker consistency
_STUCK_DATA_DIR = Path(__file__).resolve().parents[4] / "backend" / "data" / "agent"
_STUCK_DATA_FILE = _STUCK_DATA_DIR / "stuck_rounds.json"

_round_history: dict[str, list[dict]] = {}


def _load_history() -> dict[str, list[dict]]:
    try:
        data = read_json_locked(_STUCK_DATA_FILE, {})
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("stuck_detector: failed to load history file: %s", e)
        return {}


def _save_history(history: dict[str, list[dict]]) -> None:
    try:
        update_json_locked(_STUCK_DATA_FILE, {}, lambda _current: history)
    except (OSError, TypeError) as e:
        logger.warning("stuck_detector: failed to save history file: %s", e)


def _arg_fingerprint(args: dict) -> str:
    normalized = json.dumps(args, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(normalized.encode()).hexdigest()


def detect_stuck(
    tool_name: str | None,
    tool_args: dict | None,
    error_text: str | None,
    is_empty_response: bool,
    session_key: str = "default",
) -> dict:
    global _round_history

    entry = {
        "tool_name": tool_name,
        "arg_fingerprint": _arg_fingerprint(tool_args) if tool_args else None,
        "error_text": error_text[:100] if error_text else None,
        "is_empty": is_empty_response,
    }

    def _mutate(history_state: dict[str, list[dict]]) -> dict[str, list[dict]]:
        session_history = history_state.setdefault(session_key, [])
        session_history.append(entry)
        if len(session_history) > STUCK_WINDOW_SIZE:
            del session_history[:-STUCK_WINDOW_SIZE]
        return history_state

    _round_history = update_json_locked(_STUCK_DATA_FILE, {}, _mutate)
    history = _round_history.get(session_key, [])

    if len(history) < STUCK_THRESHOLD:
        return {"stuck": False, "reason": ""}

    recent = history[-STUCK_THRESHOLD:]

    all_same_tool = all(
        e["tool_name"] is not None and e["tool_name"] == recent[0]["tool_name"]
        and e["arg_fingerprint"] is not None and e["arg_fingerprint"] == recent[0]["arg_fingerprint"]
        for e in recent
    )
    if all_same_tool:
        logger.warning("stuck_detector命中: 连续 %d 次相同工具调用 %s", STUCK_THRESHOLD, recent[0]["tool_name"])
        reset(session_key)
        return {
            "stuck": True,
            "reason": f"检测到重复操作（连续{STUCK_THRESHOLD}次相同工具: {recent[0]['tool_name']}），已停止。请换个说法或拆小任务。",
        }

    all_same_error = all(
        e["error_text"] is not None and e["error_text"] == recent[0]["error_text"]
        for e in recent
    )
    if all_same_error:
        logger.warning("stuck_detector命中: 连续 %d 次相同错误 %s", STUCK_THRESHOLD, recent[0]["error_text"])
        reset(session_key)
        return {
            "stuck": True,
            "reason": f"检测到重复错误（连续{STUCK_THRESHOLD}次: {recent[0]['error_text']}），已停止。请换个说法或拆小任务。",
        }

    all_empty = all(e["is_empty"] for e in recent)
    if all_empty:
        logger.warning("stuck_detector命中: 连续 %d 次空响应", STUCK_THRESHOLD)
        reset(session_key)
        return {
            "stuck": True,
            "reason": f"检测到连续{STUCK_THRESHOLD}次空响应，已停止。请换个说法或拆小任务。",
        }

    return {"stuck": False, "reason": ""}


def reset(session_key: str = "default") -> None:
    global _round_history
    def _mutate(history_state: dict[str, list[dict]]) -> dict[str, list[dict]]:
        history_state.pop(session_key, None)
        return history_state

    _round_history = update_json_locked(_STUCK_DATA_FILE, {}, _mutate)
