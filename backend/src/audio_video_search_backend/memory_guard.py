"""How much memory the engine child could still take, read from the cgroup (plan 03-10).

Copied from Findling 1.6.4 (commit e5c1da70): ``findling/memory_guard.py`` lines
35 to 94 (anon_bytes, memory_events, headroom_bytes, admits) and the readers
memory_limit, meminfo_bytes, CGROUP_ROOT and MEMINFO from ``findling/hardware.py``.
Standard library only, every path injectable so tests run against fake trees,
never raises, logs nothing. No address space limit on purpose:
ONNX Runtime reserves far more virtual memory than it uses (STACK.md "What NOT
to Use"); the guard is the check before the start plus the kill of the child.

Why ``anon`` and not ``memory.current``: the tantivy index is memory mapped, and
its page cache is charged to the cgroup and shows in memory.current. The kernel
reclaims that cache under pressure, so counting it as used would refuse the
engine on exactly the boxes that have room for it.

Known limit: only cgroup v2 carries memory.max, an anon line and memory.events.
On a v1 host the limit is not read and the answer is MemAvailable, the same
fallback as a box without any limit. Off Linux nothing is readable and the
answer is None, which is never admitted.
"""

from pathlib import Path
from typing import Final

CGROUP_ROOT: Final = Path("/sys/fs/cgroup")
MEMINFO: Final = Path("/proc/meminfo")

_KIB: Final = 1024
_STAT_FIELDS: Final = 2  # "<name> <bytes>"


def _read(path: Path) -> str | None:
    """The stripped content of a small kernel file, or None if it cannot be read."""
    try:
        return path.read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return None


def _positive_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def memory_limit(root: Path) -> int | None:
    """The memory.max limit in bytes, or None for "max" or garbage."""
    return _positive_int(_read(root / "memory.max"))


def meminfo_bytes(path: Path, key: str) -> int | None:
    """One field of /proc/meminfo in bytes (the file speaks kB), or None."""
    raw = _read(path)
    if raw is None:
        return None
    for line in raw.splitlines():
        name, _, rest = line.partition(":")
        if name.strip() != key:
            continue
        fields = rest.split()
        if not fields:
            return None
        value = _positive_int(fields[0])
        return None if value is None else value * _KIB
    return None


def anon_bytes(root: Path = CGROUP_ROOT) -> int | None:
    """The ``anon`` bytes of memory.stat, or None when the file or the line is unusable."""
    try:
        raw = (root / "memory.stat").read_text(encoding="ascii")
    except (OSError, ValueError):
        return None
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) != _STAT_FIELDS or fields[0] != "anon":
            continue
        try:
            value = int(fields[1])
        except ValueError:
            return None
        return value if value >= 0 else None
    return None


def memory_events(root: Path = CGROUP_ROOT) -> dict[str, int] | None:
    """The counters of memory.events, or None on cgroup v1, at the root or when unreadable.

    Lines that are not "<name> <non negative integer>" are skipped; a file
    without a single usable line is None, never an empty mapping.
    """
    try:
        raw = (root / "memory.events").read_text(encoding="ascii")
    except (OSError, ValueError):
        return None
    counters: dict[str, int] = {}
    for line in raw.splitlines():
        fields = line.split()
        if len(fields) == _STAT_FIELDS and fields[1].isdigit():
            counters[fields[0]] = int(fields[1])
    return counters or None


def headroom_bytes(*, cgroup_root: Path = CGROUP_ROOT, meminfo: Path = MEMINFO) -> int | None:
    """Bytes a further process could take, or None when nothing usable is readable.

    With a limit and a readable anon: the limit minus anon, capped by
    MemAvailable when that is readable, because a limit above what the host
    still has is room that does not exist. Without a limit, or without a usable
    anon line, MemAvailable alone. Never negative.
    """
    available = meminfo_bytes(meminfo, "MemAvailable")
    limit = memory_limit(cgroup_root)
    if limit is None:
        return available
    # anon, not memory.current: the page cache of the mmap index is reclaimable
    # and must not count as used (see the module docstring).
    anon = anon_bytes(cgroup_root)
    if anon is None:
        return available
    within_limit = max(0, limit - anon)
    return within_limit if available is None else min(within_limit, available)


def admits(headroom: int | None, *, need: int) -> bool:
    """True when a readable headroom covers ``need``; unreadable is never admitted."""
    return headroom is not None and headroom >= need
