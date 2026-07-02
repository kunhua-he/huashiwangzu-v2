import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("mcp")

from dev_toolkit import server  # noqa: E402


@pytest.mark.parametrize(
    "query",
    [
        "select 1",
        "WITH rows AS (SELECT 1 AS id) SELECT * FROM rows",
        "EXPLAIN (FORMAT JSON) SELECT * FROM framework_file_items",
        "SHOW max_connections",
        "VALUES (1), (2)",
        "SELECT '; drop table x' AS literal",
        "SELECT '-- not a comment' AS literal",
    ],
)
def test_check_sql_readonly_allows_safe_read_queries(query: str) -> None:
    server._check_sql_readonly(query)


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1; DROP TABLE framework_file_items",
        "SELECT 1 -- hide the rest\n",
        "SELECT /* hide */ 1",
        "WITH deleted AS (DELETE FROM framework_file_items RETURNING *) SELECT * FROM deleted",
        "EXPLAIN UPDATE framework_file_items SET name = 'x'",
        "EXPLAIN (FORMAT JSON) CREATE TABLE audit_tmp(id int)",
        "INSERT INTO audit_tmp VALUES (1)",
        "SELECT * INTO audit_tmp FROM framework_file_items",
        "DO $$ BEGIN DELETE FROM framework_file_items; END $$",
        "SELECT 'unterminated",
    ],
)
def test_check_sql_readonly_rejects_writes_chains_and_comment_bypass(query: str) -> None:
    with pytest.raises(ValueError):
        server._check_sql_readonly(query)


def test_extract_prefixed_json_reads_machine_verdict_from_tail() -> None:
    output = 'human\nSMOKE_JSON: {"verdict": "PASS_WITH_DEBT", "counts": {"skipped": 1}}\n'
    assert server._extract_prefixed_json(output, "SMOKE_JSON:") == {
        "verdict": "PASS_WITH_DEBT",
        "counts": {"skipped": 1},
    }


def test_release_gate_response_does_not_map_debt_to_clean_success() -> None:
    output = 'human\nRELEASE_GATE_JSON: {"verdict": "PASS_WITH_DEBT", "has_debt": true}\n'
    result = server._build_release_gate_response(
        output=output,
        returncode=0,
        skip_ui=True,
        duration_seconds=1.2345,
    )

    assert result["success"] is False
    assert result["clean_pass"] is False
    assert result["release_safe"] is True
    assert result["has_debt"] is True
    assert result["verdict"] == "PASS_WITH_DEBT"


def test_normalize_pytest_targets_accepts_backend_prefixed_path() -> None:
    target = "backend/tests/test_agent_inline_tool_calls.py::TestFinalCleanContent"
    normalized = server._normalize_pytest_targets(target)
    assert normalized == ["tests/test_agent_inline_tool_calls.py::TestFinalCleanContent"]


def test_normalize_pytest_targets_accepts_repo_relative_path() -> None:
    target = "tests/test_agent_inline_tool_calls.py"
    normalized = server._normalize_pytest_targets(target)
    assert normalized == ["tests/test_agent_inline_tool_calls.py"]


def test_normalize_pytest_targets_accepts_absolute_backend_path() -> None:
    target_path = server.REPO_ROOT / "backend" / "tests" / "test_agent_inline_tool_calls.py"
    normalized = server._normalize_pytest_targets(str(target_path))
    assert normalized == ["tests/test_agent_inline_tool_calls.py"]


def test_resolve_repo_path_rejects_outside_repo(tmp_path: Path) -> None:
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="路径必须在仓库内"):
        server._resolve_repo_path(str(outside))


def test_tail_text_keeps_short_output() -> None:
    assert server._tail_text("abc", limit=10) == "abc"


def test_tail_text_truncates_from_end() -> None:
    assert server._tail_text("abcdef", limit=3) == "def"


def test_clear_log_keeps_state_files_and_clears_selected_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "LOG_DIR", tmp_path)
    monkeypatch.setattr(server, "_LOG_MAP", {"backend": "backend.log", "agent": "modules/agent.log"})

    backend_log = tmp_path / "backend.log"
    agent_log = tmp_path / "modules" / "agent.log"
    port_file = tmp_path / ".backend.port"
    pid_file = tmp_path / ".watchdog.pid"

    backend_log.parent.mkdir(parents=True, exist_ok=True)
    agent_log.parent.mkdir(parents=True, exist_ok=True)
    backend_log.write_text("one\ntwo\n", encoding="utf-8")
    agent_log.write_text("alpha\nbeta\n", encoding="utf-8")
    port_file.write_text("33000\n", encoding="utf-8")
    pid_file.write_text("12345\n", encoding="utf-8")

    result = server._clear_log(module="backend", all_logs=False, keep_state=True)

    assert result["success"] is True
    assert backend_log.read_text(encoding="utf-8") == ""
    assert agent_log.read_text(encoding="utf-8") == "alpha\nbeta\n"
    assert port_file.read_text(encoding="utf-8") == "33000\n"
    assert pid_file.read_text(encoding="utf-8") == "12345\n"
    assert "backend.log" in result["cleared"][0]
    assert result["preserved"] == [".backend.port", ".watchdog.pid"]


def test_clear_log_all_logs_truncates_every_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "LOG_DIR", tmp_path)

    first_log = tmp_path / "uvicorn.out"
    second_log = tmp_path / "modules" / "agent.log"
    second_log.parent.mkdir(parents=True, exist_ok=True)
    first_log.write_text("hello\n", encoding="utf-8")
    second_log.write_text("world\n", encoding="utf-8")

    result = server._clear_log(module="backend", all_logs=True, keep_state=False)

    assert result["success"] is True
    assert first_log.read_text(encoding="utf-8") == ""
    assert second_log.read_text(encoding="utf-8") == ""
    assert result["preserved"] == []
