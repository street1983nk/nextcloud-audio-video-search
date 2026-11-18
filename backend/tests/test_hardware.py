"""CPUs, thread default and the hardware snapshot from a fake cgroup tree (plan 05-04).

Every kernel file is written under ``tmp_path``; no real /sys or /proc is read.
The thread default leaves half of the CPUs to Nextcloud and the database and is
capped; the admin value can only lower it (RES-05, T-05-08).
"""

from pathlib import Path

import pytest
from audio_video_search_backend.hardware import (
    THREAD_CAP,
    Snapshot,
    default_threads,
    effective_threads,
    snapshot,
    usable_cpus,
)

from audio_video_search_backend import hardware

GIB = 1024**3
KIB = 1024


def _cpu_max(root: Path, raw: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "cpu.max").write_text(raw + "\n", encoding="ascii")
    return root


def _meminfo(path: Path, *, total_kib: int | None, available_kib: int | None) -> Path:
    lines = []
    if total_kib is not None:
        lines.append(f"MemTotal:       {total_kib} kB")
    lines.append("MemFree:         1000 kB")
    if available_kib is not None:
        lines.append(f"MemAvailable:   {available_kib} kB")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def _memory(root: Path, *, memory_max: str | None, anon: int | None, swap_max: str | None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    if memory_max is not None:
        (root / "memory.max").write_text(memory_max + "\n", encoding="ascii")
    if anon is not None:
        (root / "memory.stat").write_text(f"anon {anon}\nfile 0\n", encoding="ascii")
    if swap_max is not None:
        (root / "memory.swap.max").write_text(swap_max + "\n", encoding="ascii")
    return root


# --- usable_cpus ---------------------------------------------------------------


def test_quota_of_two_cpus_wins_over_larger_affinity(tmp_path: Path) -> None:
    assert usable_cpus(_cpu_max(tmp_path, "200000 100000"), affinity=8) == 2


def test_fractional_quota_rounds_down(tmp_path: Path) -> None:
    assert usable_cpus(_cpu_max(tmp_path, "150000 100000"), affinity=8) == 1


def test_max_quota_falls_back_to_affinity(tmp_path: Path) -> None:
    assert usable_cpus(_cpu_max(tmp_path, "max 100000"), affinity=6) == 6


def test_missing_cpu_max_falls_back_to_affinity(tmp_path: Path) -> None:
    assert usable_cpus(tmp_path, affinity=5) == 5


@pytest.mark.parametrize("raw", ["abc 100000", "100000 0", "100000", "", "-5 100000", "100000 abc"])
def test_broken_cpu_max_falls_back_to_affinity(tmp_path: Path, raw: str) -> None:
    assert usable_cpus(_cpu_max(tmp_path, raw), affinity=3) == 3


def test_quota_below_one_cpu_is_still_one(tmp_path: Path) -> None:
    assert usable_cpus(_cpu_max(tmp_path, "50000 100000"), affinity=8) == 1


def test_affinity_below_one_is_still_one(tmp_path: Path) -> None:
    assert usable_cpus(tmp_path, affinity=0) == 1


def test_affinity_is_read_from_the_process_when_not_given(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware.os, "sched_getaffinity", lambda _pid: {0, 1, 2}, raising=False)
    assert usable_cpus(tmp_path) == 3


def test_affinity_off_linux_is_the_cpu_count(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(hardware.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(hardware.os, "cpu_count", lambda: 7)
    assert usable_cpus(tmp_path) == 7


def test_unknown_cpu_count_off_linux_is_one(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delattr(hardware.os, "sched_getaffinity", raising=False)
    monkeypatch.setattr(hardware.os, "cpu_count", lambda: None)
    assert usable_cpus(tmp_path) == 1


def test_default_root_is_the_cgroup_root() -> None:
    assert Path("/sys/fs/cgroup") == hardware.CGROUP_ROOT


# --- default_threads and effective_threads -------------------------------------


def test_thread_cap_is_four() -> None:
    assert THREAD_CAP == 4


@pytest.mark.parametrize(("cpus", "threads"), [(1, 1), (2, 1), (4, 2), (8, 4), (64, 4)])
def test_default_threads_is_half_the_cpus_capped(cpus: int, threads: int) -> None:
    assert default_threads(cpus) == threads


def test_effective_threads_without_admin_value_is_the_default() -> None:
    assert effective_threads(None, 8) == 4


def test_admin_value_lowers() -> None:
    assert effective_threads(2, 8) == 2


def test_admin_value_never_raises() -> None:
    assert effective_threads(9, 8) == 4


@pytest.mark.parametrize("admin", [0, -1])
def test_admin_value_below_one_is_refused(admin: int) -> None:
    with pytest.raises(ValueError, match="threads"):
        effective_threads(admin, 8)


# --- snapshot -------------------------------------------------------------------


def test_snapshot_reads_every_value_in_bytes(tmp_path: Path) -> None:
    root = _memory(tmp_path / "cg", memory_max=str(4 * GIB), anon=GIB, swap_max="0")
    _cpu_max(root, "200000 100000")
    meminfo = _meminfo(tmp_path / "meminfo", total_kib=16 * GIB // KIB, available_kib=10 * GIB // KIB)

    snap = snapshot(cgroup_root=root, meminfo=meminfo, affinity=8)

    assert snap == Snapshot(
        mem_total_bytes=16 * GIB,
        memory_max_bytes=4 * GIB,
        swap_max_bytes=0,
        headroom_bytes=3 * GIB,
        cpus=2,
        affinity=8,
    )


def test_snapshot_without_limit_reports_none_and_meminfo_headroom(tmp_path: Path) -> None:
    root = _memory(tmp_path / "cg", memory_max="max", anon=GIB, swap_max="max")
    meminfo = _meminfo(tmp_path / "meminfo", total_kib=8 * GIB // KIB, available_kib=5 * GIB // KIB)

    snap = snapshot(cgroup_root=root, meminfo=meminfo, affinity=4)

    assert snap.memory_max_bytes is None
    assert snap.swap_max_bytes is None
    assert snap.headroom_bytes == 5 * GIB
    assert snap.cpus == 4


def test_limit_above_mem_total_counts_as_mem_total(tmp_path: Path) -> None:
    root = _memory(tmp_path / "cg", memory_max=str(64 * GIB), anon=GIB, swap_max=None)
    meminfo = _meminfo(tmp_path / "meminfo", total_kib=8 * GIB // KIB, available_kib=None)

    snap = snapshot(cgroup_root=root, meminfo=meminfo, affinity=2)

    assert snap.memory_max_bytes == 8 * GIB
    assert snap.headroom_bytes == 7 * GIB  # MemTotal minus anon, not the 63 GiB the limit promises
    assert snap.swap_max_bytes is None


def test_limit_without_mem_total_stays_the_limit(tmp_path: Path) -> None:
    root = _memory(tmp_path / "cg", memory_max=str(3 * GIB), anon=GIB, swap_max="garbage")
    meminfo = _meminfo(tmp_path / "meminfo", total_kib=None, available_kib=None)

    snap = snapshot(cgroup_root=root, meminfo=meminfo, affinity=2)

    assert snap.mem_total_bytes is None
    assert snap.memory_max_bytes == 3 * GIB
    assert snap.swap_max_bytes is None
    assert snap.headroom_bytes == 2 * GIB


def test_nothing_readable_is_fail_closed(tmp_path: Path) -> None:
    snap = snapshot(cgroup_root=tmp_path / "missing", meminfo=tmp_path / "no-meminfo", affinity=2)

    assert snap.mem_total_bytes is None
    assert snap.memory_max_bytes is None
    assert snap.swap_max_bytes is None
    assert snap.headroom_bytes is None


def test_snapshot_is_frozen(tmp_path: Path) -> None:
    snap = snapshot(cgroup_root=tmp_path, meminfo=tmp_path / "x", affinity=1)
    with pytest.raises(AttributeError):
        snap.cpus = 9  # type: ignore[misc]


def test_memory_total_bytes_reads_mem_total(tmp_path: Path) -> None:
    meminfo = _meminfo(tmp_path / "meminfo", total_kib=2 * GIB // KIB, available_kib=GIB // KIB)
    assert hardware.memory_total_bytes(meminfo) == 2 * GIB


def test_module_never_touches_thread_variables() -> None:
    source = Path(hardware.__file__).read_text(encoding="utf-8")
    assert "OMP_" not in source
    assert "environ" not in source
    assert "getenv" not in source
