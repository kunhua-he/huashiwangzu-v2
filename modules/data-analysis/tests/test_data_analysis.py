"""Tests for data-analysis module sandbox execution.

These tests exercise the core Python subprocess execution logic
independent of the FastAPI app/DB layer — verifying timeout, output
collection, chart image generation, and workspace isolation.
"""

import os
import sys
import json
import time
import textwrap
import subprocess
from pathlib import Path

import pytest

_TIMEOUT_SLOW = 30  # matplotlib imports can be slow even with cached fonts
_TIMEOUT_FAST = 10


_BUILD_EXEC_SCRIPT_PREAMBLE = textwrap.dedent("""\
import os, sys, io, json

os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use("Agg")

os.chdir({workspace_dir!r})
sys.path.insert(0, {workspace_dir!r})

""")


def _run_python(code: str, cwd: Path, timeout: int = _TIMEOUT_SLOW) -> subprocess.CompletedProcess:
    script = _BUILD_EXEC_SCRIPT_PREAMBLE.format(workspace_dir=str(cwd)) + code
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(cwd),
        "MPLBACKEND": "Agg",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
    }
    try:
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={k: v for k, v in env.items() if v is not None},
        )
    except subprocess.TimeoutExpired:
        raise


def _resolve_workspace_path(workspace_root: Path, relative_path: str) -> Path:
    cleaned = relative_path.strip()
    if not cleaned or cleaned == ".":
        return workspace_root
    target = (workspace_root / cleaned).resolve()
    if not str(target).startswith(str(workspace_root)):
        raise ValueError(f"Path escapes workspace boundary: {relative_path!r}")
    return target


# ── Tests ──

class TestBasicExecution:
    def test_simple_print(self, tmp_path: Path) -> None:
        proc = _run_python('print("hello from data-analysis")', tmp_path, _TIMEOUT_FAST)
        assert proc.returncode == 0
        assert "hello from data-analysis" in proc.stdout

    def test_pandas_create_dataframe(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
        import pandas as pd
        df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 15]})
        print(f"shape: {df.shape}")
        print(f"sum: {df['y'].sum()}")
        """)
        proc = _run_python(code, tmp_path, _TIMEOUT_SLOW)
        assert proc.returncode == 0
        assert "shape: (3, 2)" in proc.stdout
        assert "sum: 45" in proc.stdout

    def test_numpy_available(self, tmp_path: Path) -> None:
        code = 'import numpy as np; print(f"numpy {np.__version__}")'
        proc = _run_python(code, tmp_path, _TIMEOUT_FAST)
        assert proc.returncode == 0
        assert "numpy" in proc.stdout

    def test_matplotlib_agg_backend_and_chart(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
        import matplotlib
        assert matplotlib.get_backend() == "Agg"
        import matplotlib.pyplot as plt
        import numpy as np
        xs = np.linspace(0, 10, 100)
        ys = np.sin(xs)
        plt.plot(xs, ys)
        plt.savefig("sin_wave.png")
        print("Chart saved: sin_wave.png")
        """)
        proc = _run_python(code, tmp_path, _TIMEOUT_SLOW)
        assert proc.returncode == 0
        chart_file = tmp_path / "sin_wave.png"
        assert chart_file.exists()
        assert chart_file.stat().st_size > 500


class TestChartGeneration:
    def test_bar_chart_png(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        categories = ["A", "B", "C", "D"]
        values = [23, 45, 12, 67]
        plt.bar(categories, values, color="#2395bc")
        plt.title("Test Bar Chart")
        plt.tight_layout()
        plt.savefig("bar_chart.png", dpi=100)
        print("Saved bar_chart.png")
        """)
        proc = _run_python(code, tmp_path, _TIMEOUT_SLOW)
        assert proc.returncode == 0
        assert (tmp_path / "bar_chart.png").exists()

    def test_pie_chart_svg(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        labels = ["A", "B", "C"]
        sizes = [30, 50, 20]
        plt.pie(sizes, labels=labels, autopct="%1.1f%%")
        plt.savefig("pie_chart.svg", format="svg")
        print("Saved pie_chart.svg")
        """)
        proc = _run_python(code, tmp_path, _TIMEOUT_SLOW)
        assert proc.returncode == 0
        assert (tmp_path / "pie_chart.svg").exists()


class TestTimeout:
    def test_timeout_expiry(self, tmp_path: Path) -> None:
        code = textwrap.dedent("""\
        import time
        time.sleep(30)
        print("should not reach")
        """)
        start = time.time()
        with pytest.raises(subprocess.TimeoutExpired):
            _run_python(code, tmp_path, timeout=2)
        elapsed = time.time() - start
        assert elapsed < 15


class TestPathConstraint:
    """Test the application-layer path constraint logic (same as router)."""

    def test_path_within_workspace(self, tmp_path: Path) -> None:
        result = _resolve_workspace_path(tmp_path, "subdir/file.txt")
        assert result == (tmp_path / "subdir/file.txt").resolve()

    def test_path_dot_returns_workspace_root(self, tmp_path: Path) -> None:
        result = _resolve_workspace_path(tmp_path, ".")
        assert result == tmp_path

    def test_path_empty_returns_workspace_root(self, tmp_path: Path) -> None:
        result = _resolve_workspace_path(tmp_path, "")
        assert result == tmp_path

    def test_path_escape_with_dotdot(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Path escapes workspace"):
            _resolve_workspace_path(tmp_path, "../etc/passwd")

    def test_path_absolute_outside(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Path escapes workspace"):
            _resolve_workspace_path(tmp_path, "/tmp")

    def test_symlink_chain_cannot_escape(self, tmp_path: Path) -> None:
        inside = tmp_path / "inside"
        inside.mkdir()
        escape_target = tmp_path.parent / "escaped.txt"
        escape_target.write_text("evil", encoding="utf-8")
        link = inside / "link_out"
        link.symlink_to(escape_target)
        with pytest.raises(ValueError, match="Path escapes workspace"):
            _resolve_workspace_path(tmp_path, "inside/link_out")

    def test_preamble_sets_cwd_to_workspace(self, tmp_path: Path) -> None:
        """The preamble sets cwd to the workspace directory."""
        code = "import os; print(os.getcwd())"
        proc = _run_python(code, tmp_path, _TIMEOUT_FAST)
        assert proc.returncode == 0
        assert str(tmp_path) in proc.stdout.strip()


class TestStdoutTruncation:
    def test_large_output_produced(self, tmp_path: Path) -> None:
        code = 'print("X" * 500_000)'
        proc = _run_python(code, tmp_path, _TIMEOUT_FAST)
        assert proc.returncode == 0
        assert len(proc.stdout) > 0


class TestErrorHandling:
    def test_syntax_error(self, tmp_path: Path) -> None:
        code = "this is not valid python"
        proc = _run_python(code, tmp_path, _TIMEOUT_FAST)
        assert proc.returncode != 0
        assert proc.stderr

    def test_runtime_error(self, tmp_path: Path) -> None:
        code = "1 / 0"
        proc = _run_python(code, tmp_path, _TIMEOUT_FAST)
        assert proc.returncode != 0
        assert "ZeroDivisionError" in proc.stderr
