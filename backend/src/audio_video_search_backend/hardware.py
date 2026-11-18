"""CPUs, thread default and a memory snapshot read from the cgroup (plan 05-04, RES-01, RES-05).

Standard library only, every path injectable so tests run against fake trees,
never raises on kernel files, logs nothing and reads no environment and no
settings. The readers come from ``memory_guard`` (Findling 1.6.4); this module
only adds cpu.max, the affinity, MemTotal and memory.swap.max.

Usable CPUs are the smaller of the affinity (``--cpuset-cpus``) and the CFS
quota of cpu.max (``--cpus``): ``os.process_cpu_count()`` sees only the
affinity. The engine gets half of them by default, capped, so Nextcloud and the
database keep the other half; nice alone does not protect them, because under
group scheduling it only weighs processes inside this container (pitfall 7).

Every amount is in bytes (pitfall 9); only the display turns them into GB.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from audio_video_search_backend.memory_guard import (
    CGROUP_ROOT,
    MEMINFO,
    _read,
    anon_bytes,
    headroom_bytes,
    meminfo_bytes,
    memory_limit,
)

__all__ = [
    "CGROUP_ROOT",
    "MEMINFO",
    "THREAD_CAP",
    "Snapshot",
    "default_threads",
    "effective_threads",
    "memory_total_bytes",
    "snapshot",
    "usable_cpus",
]

# Spike 3 measured only 2 threads; above 2 is unmeasured, phase 11 measures
# (assumption A6). CTranslate2 advises against more threads than physical cores.
THREAD_CAP: Final = 4

_CPU_MAX_FIELDS: Final = 2  # "$MAX $PERIOD"


def _affinity() -> int:
    """CPUs this process may run on; off Linux the CPU count, at least 1."""
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is not None:
        return len(getaffinity(0))
    return os.cpu_count() or 1


def _quota_cpus(root: Path) -> int | None:
    """Whole CPUs of the cpu.max quota, or None for "max", a missing file or garbage."""
    raw = _read(root / "cpu.max")
    if raw is None:
        return None
    fields = raw.split()
    if len(fields) != _CPU_MAX_FIELDS or not fields[0].isdigit() or not fields[1].isdigit():
        return None
    quota, period = int(fields[0]), int(fields[1])
    if period == 0:
        return None
    return quota // period  # --cpus=1.5 gives 1


def usable_cpus(root: Path = CGROUP_ROOT, affinity: int | None = None) -> int:
    """min(affinity, quota / period of cpu.max), never below 1."""
    allowed = _affinity() if affinity is None else affinity
    quota = _quota_cpus(root)
    if quota is not None:
        allowed = min(allowed, quota)
    return max(1, allowed)


def default_threads(cpus: int) -> int:
    """Half of the usable CPUs, at least 1, at most THREAD_CAP."""
    return max(1, min(THREAD_CAP, cpus // 2))


def effective_threads(admin_value: int | None, cpus: int) -> int:
    """The thread count for the engine: the admin value can only lower the default.

    A value below 1 is a ValueError with the field code "threads"; the caller
    rejects it before it is stored.
    """
    standard = default_threads(cpus)
    if admin_value is None:
        return standard
    if admin_value < 1:
        raise ValueError("threads")
    return min(admin_value, standard)


def memory_total_bytes(meminfo: Path = MEMINFO) -> int | None:
    """MemTotal of /proc/meminfo in bytes, or None."""
    return meminfo_bytes(meminfo, "MemTotal")


def _swap_max(root: Path) -> int | None:
    """memory.swap.max in bytes; 0 means no swap, None for "max", missing or garbage."""
    raw = _read(root / "memory.swap.max")
    if raw is None or not raw.isdigit():
        return None
    return int(raw)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """What the profile calculator sees, all amounts in bytes."""

    mem_total_bytes: int | None
    memory_max_bytes: int | None
    swap_max_bytes: int | None
    headroom_bytes: int | None
    cpus: int
    affinity: int


def snapshot(
    *,
    cgroup_root: Path = CGROUP_ROOT,
    meminfo: Path = MEMINFO,
    affinity: int | None = None,
) -> Snapshot:
    """Read the hardware once.

    A memory.max above MemTotal is room that does not exist, so MemTotal counts
    and the headroom is capped by MemTotal minus anon. Nothing readable gives a
    headroom of None, which admits no profile (fail closed, research pattern 6).
    """
    allowed = _affinity() if affinity is None else affinity
    total = memory_total_bytes(meminfo)
    limit = memory_limit(cgroup_root)
    headroom = headroom_bytes(cgroup_root=cgroup_root, meminfo=meminfo)
    if limit is not None and total is not None and limit > total:
        limit = total
        anon = anon_bytes(cgroup_root)
        if headroom is not None and anon is not None:
            headroom = min(headroom, max(0, total - anon))
    return Snapshot(
        mem_total_bytes=total,
        memory_max_bytes=limit,
        swap_max_bytes=_swap_max(cgroup_root),
        headroom_bytes=headroom,
        cpus=usable_cpus(cgroup_root, affinity=allowed),
        affinity=allowed,
    )
