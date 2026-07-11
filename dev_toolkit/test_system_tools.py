from __future__ import annotations

from collections import namedtuple
from types import SimpleNamespace

from dev_toolkit import system_tools


class FakeMemoryInfo:
    rss = 512 * 1024 * 1024


class FakePsutilProcess:
    def __init__(self, cpu_samples: list[float]) -> None:
        self.info = {
            "pid": 123,
            "name": "Python",
            "cmdline": [
                "python3.14",
                "/repo/dev_toolkit/server.py",
            ],
            "memory_info": FakeMemoryInfo(),
            "status": "running",
        }
        self._cpu_samples = list(cpu_samples)

    def cpu_percent(self, interval: float | None = None) -> float:
        return self._cpu_samples.pop(0) if self._cpu_samples else 0.0


class FakePsutil:
    NoSuchProcess = RuntimeError
    AccessDenied = PermissionError

    def __init__(self) -> None:
        self.process = FakePsutilProcess([0.0, 160.0])

    def cpu_count(self, logical: bool = True) -> int:
        return 8 if logical else 4

    def process_iter(self, attrs: list[str]):
        return [self.process]


def test_project_process_cpu_reports_scope_and_normalized_share(monkeypatch) -> None:
    monkeypatch.setattr(system_tools, "_import_psutil", lambda: FakePsutil())
    monkeypatch.setattr(system_tools.time, "sleep", lambda seconds: None)

    rows = system_tools._project_processes(system_tools.Path("/repo"), 4)

    assert rows[0]["cpu_percent"] == 160.0
    assert rows[0]["cpu_percent_scope"] == "process_single_logical_core"
    assert rows[0]["normalized_system_percent"] == 20.0


def test_snapshot_includes_metric_notes(monkeypatch) -> None:
    monkeypatch.setattr(system_tools, "_cpu_snapshot", lambda: {"percent": 22.0, "percent_scope": "whole_machine"})
    monkeypatch.setattr(system_tools, "_memory_snapshot", lambda: {"percent": 60.0})
    monkeypatch.setattr(system_tools, "_gpu_snapshot", lambda: {"available": False, "utilization_percent": None})
    monkeypatch.setattr(system_tools, "_project_processes", lambda repo_root, limit: [])

    snapshot = system_tools._snapshot(system_tools.Path("/repo"), 4)

    assert snapshot["metric_notes"]["cpu.percent"].startswith("whole-machine")
    assert "Multi-threaded processes can exceed 100" in snapshot["metric_notes"]["project_processes.cpu_percent"]


def test_cpu_snapshot_marks_whole_machine_scope(monkeypatch) -> None:
    fake_psutil = SimpleNamespace(
        cpu_percent=lambda interval: 22.0,
        cpu_count=lambda logical=True: 32 if logical else 16,
        getloadavg=lambda: (1.0, 2.0, 3.0),
    )
    monkeypatch.setattr(system_tools, "_import_psutil", lambda: fake_psutil)

    snapshot = system_tools._cpu_snapshot()

    assert snapshot["percent"] == 22.0
    assert snapshot["percent_scope"] == "whole_machine"
    assert snapshot["logical_cores"] == 32


def test_cpu_snapshot_falls_back_when_cpu_times_is_empty(monkeypatch) -> None:
    CpuTimes = namedtuple("CpuTimes", ["user", "system", "idle"])
    fake_psutil = SimpleNamespace(
        cpu_times_percent=lambda interval: CpuTimes(user=0.0, system=0.0, idle=0.0),
        cpu_percent=lambda interval: 23.5,
        cpu_count=lambda logical=True: 32 if logical else 16,
        getloadavg=lambda: (1.0, 2.0, 3.0),
    )
    monkeypatch.setattr(system_tools, "_import_psutil", lambda: fake_psutil)

    snapshot = system_tools._cpu_snapshot()

    assert snapshot["percent"] == 23.5
    assert snapshot["sample_method"] == "cpu_percent_after_empty_cpu_times"
