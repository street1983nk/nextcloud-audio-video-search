"""Wave 0 of phase 5: the Linux peak of the Parakeet child is measured in CI (plan 05-01, D-05-09).

The probe runs inside the image this run pushed, on amd64 and arm64, and is
never part of the image: it lives under ci/, the build context is backend/
(T-05-01). Neither the workflow nor the probe sets OMP_THREAD_LIMIT (PII 02-16:
a thread limit below what the library plans hung arm64). A phase branch builds
and measures but never moves the :dev tag.
"""

import re

from tests.conftest import BACKEND_ROOT, REPO_ROOT

DOCKER_YML = REPO_ROOT / ".github" / "workflows" / "docker.yml"
PROBE = REPO_ROOT / "ci" / "measure" / "peak_probe.py"
JOB_HEADER = re.compile(r"^  ([a-z][a-z0-9-]*):\s*$", re.MULTILINE)


def _job(source: str, name: str) -> str:
    """The text of one job of a workflow, from its header to the next job header."""
    headers = list(JOB_HEADER.finditer(source[source.index("\njobs:") :]))
    offset = source.index("\njobs:")
    for index, header in enumerate(headers):
        if header.group(1) == name:
            start = offset + header.start()
            end = offset + headers[index + 1].start() if index + 1 < len(headers) else len(source)
            return source[start:end]
    raise AssertionError(f"job {name} missing")


def _uncommented(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_the_peak_job_runs_on_both_architectures_with_a_deadline() -> None:
    job = _job(DOCKER_YML.read_text(encoding="utf-8"), "peak-measure")

    assert "needs: build" in job
    assert "runner: ubuntu-24.04\n" in job
    assert "runner: ubuntu-24.04-arm\n" in job
    assert re.search(r"^    timeout-minutes: \d+$", job, re.MULTILINE)
    assert "peak_probe.py" in job
    assert "name: peak-${{ matrix.arch }}" in job


def test_the_probe_is_mounted_read_only_and_reads_the_pinned_clip() -> None:
    job = _job(DOCKER_YML.read_text(encoding="utf-8"), "peak-measure")

    assert '-v "${PWD}/ci/measure:/probe:ro"' in job
    assert "fetch_speech.py" in job
    assert "--memory" not in _uncommented(job)


def test_the_probe_lives_under_ci_only() -> None:
    assert PROBE.is_file()
    assert not (BACKEND_ROOT / "ci").exists()
    for path in BACKEND_ROOT.rglob("*.py"):
        if ".venv" in path.parts or path == BACKEND_ROOT / "tests" / "test_peak_measurement.py":
            continue
        assert "peak_probe" not in path.read_text(encoding="utf-8"), path


def test_the_probe_reports_children_rusage_and_only_a_word_count() -> None:
    source = PROBE.read_text(encoding="utf-8")

    assert "RUSAGE_CHILDREN" in source
    assert "VmHWM" in source
    assert '"words": sum(window.n_words for window in windows)' in source
    assert ".text" not in source  # no word of the transcript leaves the probe


def test_nothing_sets_a_thread_limit() -> None:
    for path in (DOCKER_YML, PROBE):
        assert "OMP_THREAD_LIMIT" not in _uncommented(path.read_text(encoding="utf-8")), path


def test_a_phase_branch_never_moves_the_dev_tag() -> None:
    source = DOCKER_YML.read_text(encoding="utf-8")
    merge = _job(source, "merge")

    assert "- 'phase-*'" in source
    assert "if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/tags/v')" in merge
