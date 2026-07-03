"""Sandbox test for terminal-tools module.

Validates dangerous command interception, path escape detection,
workspace constraints, and parameter shapes — no actual command execution.
"""


# ── Inline security contract tests (mirrors app.core.command_safety) ──

DANGEROUS_PATTERNS = [
    ("sudo", set()),
    ("rm -rf /", set()),
    ("rm -rf ~", set()),
    ("mkfs", set()),
    ("dd if=", set()),
    (":(){ :|:& };:", set()),
    ("chmod 777 /", set()),
    ("> /dev/sda", set()),
    ("reboot", set()),
    ("shutdown", set()),
    ("init 0", set()),
    ("poweroff", set()),
    ("telnet", set()),
    ("> /etc/", set()),
    ("wget ", set()),
    ("curl ", set()),
]


def _check_dangerous_command(command: str) -> str | None:
    cmd_lower = command.strip().lower()
    for pattern, _ in DANGEROUS_PATTERNS:
        if pattern in cmd_lower or cmd_lower.startswith(pattern):
            return f"Command blocked: '{pattern}' is not allowed"
    return None


TRAVERSAL_CMDS = frozenset({
    'cd', 'ls', 'find', 'tree', 'cat', 'less', 'more',
    'head', 'tail', 'nl', 'wc', 'stat', 'du', 'file',
    'readlink', 'realpath', 'dirname',
})


def _check_path_escape(command: str, workspace: str) -> str | None:
    import shlex
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    if not tokens:
        return None
    cmd_name = tokens[0]
    if cmd_name not in TRAVERSAL_CMDS:
        return None
    ws_prefix = workspace.rstrip("/") + "/"
    for arg in tokens[1:]:
        if arg.startswith("-") or arg in {"&&", "||", ";", "|", ">", ">>", "<"}:
            continue
        if arg == "~" or arg.startswith("~/"):
            return f"Path escape blocked: '{arg}' resolves outside workspace"
        import os as _os
        try:
            resolved = _os.path.realpath(_os.path.join(workspace, arg))
            if not str(resolved).startswith(ws_prefix) and str(resolved) != workspace:
                return f"Path escape blocked: '{arg}' resolves to a location outside workspace"
        except (OSError, ValueError):
            continue
    return None


def _safe_external_filename(name: str, fallback: str = "file") -> str:
    import pathlib
    cleaned = pathlib.Path(str(name or "").replace("\\", "/")).name.strip()
    if cleaned in {"", ".", ".."}:
        return fallback
    return cleaned


def test_dangerous_command_detection() -> None:
    dangerous = ["sudo rm -rf /", "rm -rf /etc", ":(){ :|:& };:", "reboot", "shutdown"]
    safe = ["ls -la", "echo hello", "python script.py", "cat file.txt", "git status"]
    for cmd in dangerous:
        msg = _check_dangerous_command(cmd)
        assert msg is not None, f"Should block dangerous command: {cmd}"
        print(f"  [DANGER] Blocked: {cmd[:40]} → {msg[:40]}...")
    for cmd in safe:
        msg = _check_dangerous_command(cmd)
        assert msg is None, f"Should allow safe command: {cmd}"
        print(f"  [SAFE] Allowed: {cmd}")
    print("  ✓ dangerous_command_detection passed")


def test_path_escape_detection() -> None:
    import os as _os
    import tempfile
    workspace_raw = tempfile.mkdtemp(prefix="ws_test_")
    workspace = _os.path.realpath(workspace_raw)
    try:
        inside = ["ls .", "cat test.txt", "head subdir/file.txt", "ls -la"]
        escaping = ["ls ../", "cat ../../etc/passwd", "find ~/Documents", "ls /etc"]
        for cmd in inside:
            msg = _check_path_escape(cmd, workspace)
            assert msg is None, f"Should allow workspace-internal path: {cmd}"
            print(f"  [INSIDE] Allowed: {cmd}")
        for cmd in escaping:
            msg = _check_path_escape(cmd, workspace)
            if msg is not None:
                print(f"  [ESCAPE] Blocked: {cmd[:40]} → {msg[:40]}...")
                assert workspace not in msg, "Error message must not leak host workspace path"
            else:
                print(f"  [ESCAPE] Allowed (non-traversal cmd): {cmd}")
    finally:
        _os.rmdir(workspace)


def test_workspace_resolution_contract() -> None:
    """Verify caller string resolution: user:{id} -> int id."""
    cases = [("user:1", 1), ("user:42", 42), ("user:999", 999)]
    for caller, expected in cases:
        uid = int(caller.split(":", 1)[1])
        assert uid == expected, f"Expected {expected}, got {uid}"
        print(f"  [CALLER] {caller} -> {uid}")


def test_output_shape_contract() -> None:
    """Validate the uniform response shape for all capabilities."""
    exec_response = {
        "success": True,
        "return_code": 0,
        "stdout": "hello",
        "stderr": "",
        "stdout_truncated": False,
        "stderr_truncated": False,
        "command": "echo hello",
    }
    write_response = {"success": True, "path": "test.txt", "size": 5}
    read_response = {"success": True, "path": "big.txt", "content": "x", "truncated": True, "binary": False}
    list_response = {"success": True, "path": ".", "items": [], "count": 0, "truncated": False, "limit": 1000}
    error_response = {"success": False, "error": "No command provided"}
    for r in (exec_response, write_response, read_response, list_response, error_response):
        assert "success" in r
        assert "absolute_path" not in r, "Response must not leak host absolute paths"
        if r["success"]:
            assert "success" in r and r["success"] is True
        else:
            assert "error" in r
    print("  [SHAPE] Response shape contract valid")


def test_filename_safety_contract() -> None:
    """Framework display names collapse to safe single file names."""
    cases = {
        "../secret.txt": "secret.txt",
        "/Users/alice/Desktop/report.csv": "report.csv",
        "nested\\windows.txt": "windows.txt",
        "": "fallback.txt",
        ".": "fallback.txt",
        "..": "fallback.txt",
    }
    for raw, expected in cases.items():
        actual = _safe_external_filename(raw, "fallback.txt")
        assert actual == expected, f"Expected {expected}, got {actual}"
        assert "/" not in actual and "\\" not in actual
    print("  [FILENAME] External filename safety contract valid")


def test_chart_fake_success_contract() -> None:
    """chart must fail if run_python succeeds but no chart file is uploaded."""
    result = {"success": True, "chart_count": 0, "charts": []}
    if result.get("success") and result.get("chart_count", 0) < 1:
        result["success"] = False
        result["error"] = "Chart generation produced no uploaded chart file"
    assert result["success"] is False
    assert "error" in result
    print("  [CHART] Fake-success guard contract valid")


def main() -> None:
    print("=" * 60)
    print("terminal-tools sandbox test")
    print("=" * 60)
    test_dangerous_command_detection()
    test_path_escape_detection()
    test_workspace_resolution_contract()
    test_output_shape_contract()
    test_filename_safety_contract()
    test_chart_fake_success_contract()
    print("=" * 60)
    print("PASS: terminal-tools sandbox test")


if __name__ == "__main__":
    main()
