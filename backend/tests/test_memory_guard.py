"""The memory guard reads anon against memory.max, capped by MemAvailable (plan 03-10).

Copied from Findling's tests/test_memory_guard.py with the cases the plan names.
Every file is read from a fake tree under ``tmp_path``; no real /sys is touched.
Nothing readable means not admitted, so the engine child is never started blind.
"""

from pathlib import Path

from audio_video_search_backend import memory_guard
from audio_video_search_backend.memory_guard import (
    admits,
    anon_bytes,
    headroom_bytes,
    meminfo_bytes,
    memory_events,
    memory_limit,
)
from tests.conftest import BACKEND_ROOT

GIB = 1024**3
KIB = 1024


def _tree(
    root: Path,
    *,
    memory_max: str | None,
    anon: int | None = None,
    file_cache: int = 10 * GIB,
    events: str | None = None,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if events is not None:
        (root / "memory.events").write_text(events, encoding="ascii")
    if memory_max is not None:
        (root / "memory.max").write_text(memory_max + "\n", encoding="ascii")
    if anon is not None:
        (root / "memory.stat").write_text(
            f"anon {anon}\nfile {file_cache}\nkernel 1048576\nshmem 0\n",
            encoding="ascii",
        )
    # A value no reader may trust. If memory.current were ever read, every result below would be wrong.
    (root / "memory.current").write_text(f"{64 * GIB}\n", encoding="ascii")
    return root


def _meminfo(path: Path, available: int | None) -> Path:
    lines = ["MemTotal:       16000000 kB", "MemFree:         1000000 kB"]
    if available is not None:
        lines.append(f"MemAvailable:   {available // KIB} kB")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def test_the_limit_minus_anon_is_the_headroom(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max=str(4 * GIB), anon=1 * GIB, file_cache=10 * GIB)
    meminfo = _meminfo(tmp_path / "meminfo", 8 * GIB)

    assert headroom_bytes(cgroup_root=root, meminfo=meminfo) == 3 * GIB


def test_memavailable_caps_the_limit_headroom(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max=str(4 * GIB), anon=1 * GIB)
    meminfo = _meminfo(tmp_path / "meminfo", 2 * GIB)

    assert headroom_bytes(cgroup_root=root, meminfo=meminfo) == 2 * GIB


def test_max_means_no_limit_and_memavailable_alone(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max="max", anon=1 * GIB)
    meminfo = _meminfo(tmp_path / "meminfo", 5 * GIB)

    assert memory_limit(root) is None
    assert headroom_bytes(cgroup_root=root, meminfo=meminfo) == 5 * GIB


def test_missing_cgroup_files_give_memavailable(tmp_path: Path) -> None:
    meminfo = _meminfo(tmp_path / "meminfo", 3 * GIB)

    assert headroom_bytes(cgroup_root=tmp_path / "nowhere", meminfo=meminfo) == 3 * GIB


def test_a_missing_memory_stat_falls_back_to_memavailable(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max=str(4 * GIB))
    meminfo = _meminfo(tmp_path / "meminfo", 3 * GIB)

    assert headroom_bytes(cgroup_root=root, meminfo=meminfo) == 3 * GIB
    assert headroom_bytes(cgroup_root=root, meminfo=tmp_path / "absent") is None


def test_a_memory_stat_without_an_anon_line_falls_back_to_memavailable(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max=str(4 * GIB))
    (root / "memory.stat").write_text("file 1024\nkernel 2048\n", encoding="ascii")
    meminfo = _meminfo(tmp_path / "meminfo", 3 * GIB)

    assert anon_bytes(root) is None
    assert headroom_bytes(cgroup_root=root, meminfo=meminfo) == 3 * GIB


def test_a_limit_without_memavailable_is_the_limit_headroom(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max=str(4 * GIB), anon=1 * GIB)

    assert headroom_bytes(cgroup_root=root, meminfo=_meminfo(tmp_path / "bare", None)) == 3 * GIB


def test_nothing_readable_is_none(tmp_path: Path) -> None:
    assert headroom_bytes(cgroup_root=tmp_path / "nowhere", meminfo=tmp_path / "nothing") is None


def test_anon_above_the_limit_is_no_headroom_rather_than_negative(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max=str(1 * GIB), anon=2 * GIB)
    meminfo = _meminfo(tmp_path / "meminfo", 8 * GIB)

    assert headroom_bytes(cgroup_root=root, meminfo=meminfo) == 0


def test_garbage_is_unreadable(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max="lots", anon=None)
    (root / "memory.stat").write_text("anon many\n", encoding="ascii")
    info = tmp_path / "meminfo"
    info.write_text("MemAvailable:\nMemFree: x kB\n", encoding="ascii")

    assert memory_limit(root) is None
    assert anon_bytes(root) is None
    assert meminfo_bytes(info, "MemAvailable") is None
    assert meminfo_bytes(info, "MemFree") is None
    assert meminfo_bytes(info, "SwapTotal") is None
    assert (tmp_path / "neg").write_text("anon -5\n", encoding="ascii")
    assert anon_bytes(tmp_path.parent / tmp_path.name / "nowhere") is None


def test_a_negative_anon_is_unusable(tmp_path: Path) -> None:
    root = tmp_path / "cg"
    root.mkdir()
    (root / "memory.stat").write_text("anon -5\n", encoding="ascii")

    assert anon_bytes(root) is None


def test_admits_needs_a_readable_headroom_of_at_least_the_need() -> None:
    assert admits(None, need=1) is False
    assert admits(10, need=10) is True
    assert admits(9, need=10) is False


def test_the_counters_of_memory_events_are_read(tmp_path: Path) -> None:
    root = _tree(tmp_path / "cg", memory_max="max", events="low 0\nhigh 0\nmax 7\noom 0\noom_kill 1\nbad line here\n")

    assert memory_events(root) == {"low": 0, "high": 0, "max": 7, "oom": 0, "oom_kill": 1}
    assert memory_events(tmp_path / "nowhere") is None
    empty = _tree(tmp_path / "empty", memory_max="max", events="nothing\n")
    assert memory_events(empty) is None


def test_the_defaults_point_at_the_kernel_files() -> None:
    assert Path("/sys/fs/cgroup") == memory_guard.CGROUP_ROOT
    assert Path("/proc/meminfo") == memory_guard.MEMINFO


def test_no_address_space_limit_anywhere_in_the_guard() -> None:
    source = (BACKEND_ROOT / "src/audio_video_search_backend/memory_guard.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith("#"))
    assert "setrlimit" not in code
    assert "RLIMIT_AS" not in code
    assert "import resource" not in code
