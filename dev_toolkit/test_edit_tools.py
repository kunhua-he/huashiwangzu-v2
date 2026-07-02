from __future__ import annotations

import asyncio
import json
from pathlib import Path

from dev_toolkit.edit_tools import batch_quick_fix, edit_recipe


async def _noop_run_command(*args, **kwargs):
    return {"success": True, "stdout": "", "stderr": "", "duration_seconds": 0.0}


def test_batch_preview_does_not_write(tmp_path: Path) -> None:
    target = tmp_path / "one.py"
    target.write_text("alpha = 1\n", encoding="utf-8")

    result = json.loads(
        asyncio.run(
            batch_quick_fix(
                _noop_run_command,
                tmp_path,
                "ruff",
                operations=[{"path": "one.py", "old_text": "alpha = 1\n", "new_text": "alpha = 2\n"}],
                apply=False,
            )
        )
    )

    assert result["success"] is True
    assert result["applied"] is False
    assert "+alpha = 2" in result["results"][0]["diff"]
    assert target.read_text(encoding="utf-8") == "alpha = 1\n"


def test_batch_apply_writes_independent_files(tmp_path: Path) -> None:
    first = tmp_path / "one.py"
    second = tmp_path / "two.py"
    first.write_text("alpha = 1\n", encoding="utf-8")
    second.write_text("beta = 1\n", encoding="utf-8")

    result = json.loads(
        asyncio.run(
            batch_quick_fix(
                _noop_run_command,
                tmp_path,
                "ruff",
                operations=[
                    {"path": "one.py", "old_text": "alpha = 1\n", "new_text": "alpha = 2\n"},
                    {"path": "two.py", "old_text": "beta = 1\n", "new_text": "beta = 2\n"},
                ],
                apply=True,
                max_workers=2,
            )
        )
    )

    assert result["success"] is True
    assert result["applied"] is True
    assert first.read_text(encoding="utf-8") == "alpha = 2\n"
    assert second.read_text(encoding="utf-8") == "beta = 2\n"


def test_batch_apply_rejects_duplicate_file_by_default(tmp_path: Path) -> None:
    target = tmp_path / "one.py"
    target.write_text("alpha = 1\nbeta = 1\n", encoding="utf-8")

    result = json.loads(
        asyncio.run(
            batch_quick_fix(
                _noop_run_command,
                tmp_path,
                "ruff",
                operations=[
                    {"path": "one.py", "old_text": "alpha = 1\n", "new_text": "alpha = 2\n"},
                    {"path": "one.py", "old_text": "beta = 1\n", "new_text": "beta = 2\n"},
                ],
                apply=True,
                max_workers=2,
            )
        )
    )

    assert result["success"] is False
    assert result["applied"] is False
    assert result["duplicate_paths"] == ["one.py"]
    assert target.read_text(encoding="utf-8") == "alpha = 1\nbeta = 1\n"


def test_replace_between_markers_recipe(tmp_path: Path) -> None:
    target = tmp_path / "demo.md"
    target.write_text("A\n<!-- start -->\nold\n<!-- end -->\nZ\n", encoding="utf-8")

    result = json.loads(
        asyncio.run(
            edit_recipe(
                _noop_run_command,
                tmp_path,
                "ruff",
                recipe="replace_between_markers",
                parameters={
                    "path": "demo.md",
                    "start_marker": "<!-- start -->\n",
                    "end_marker": "<!-- end -->",
                    "new_inner": "new\n",
                },
                apply=True,
            )
        )
    )

    assert result["success"] is True
    assert target.read_text(encoding="utf-8") == "A\n<!-- start -->\nnew\n<!-- end -->\nZ\n"
