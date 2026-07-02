"""Tests for worktree boundary matching helpers."""

from dev_toolkit.worktree_tools import path_matches_forbidden, path_matches_prefix


def test_path_matches_prefix_only_matches_rooted_prefix() -> None:
    assert path_matches_prefix("modules/knowledge/router.py", "modules/knowledge")
    assert not path_matches_prefix("modules/foo/backend/file.py", "backend")


def test_path_matches_forbidden_matches_nested_directory_names() -> None:
    assert path_matches_forbidden("modules/foo/__pycache__/x.pyc", "__pycache__")
    assert path_matches_forbidden("__pycache__/x.pyc", "__pycache__")
    assert not path_matches_forbidden("modules/foo/cache.py", "__pycache__")


def test_path_matches_forbidden_keeps_path_prefixes_strict() -> None:
    assert path_matches_forbidden("backend/.venv/lib/site.py", "backend/.venv")
    assert not path_matches_forbidden("modules/foo/backend/.venv/site.py", "backend/.venv")
