"""Wave 0 of phase 5: the Linux peak of the Parakeet child is measured in CI (plan 05-01, D-05-09).

The probe runs inside the image this run pushed, on amd64 and arm64, and is
never part of the image: it lives under ci/, the build context is backend/
(T-05-01). Neither the workflow nor the probe sets OMP_THREAD_LIMIT (PII 02-16:
a thread limit below what the library plans hung arm64). A phase branch builds
and measures but never moves the :dev tag.
"""

import json
import re

from audio_video_search_backend import measured
from tests.conftest import BACKEND_ROOT, REPO_ROOT

DOCKER_YML = REPO_ROOT / ".github" / "workflows" / "docker.yml"
PROBE = REPO_ROOT / "ci" / "measure" / "peak_probe.py"
RECORD = REPO_ROOT / "docs" / "measurements" / "parakeet-peak-2026-11.json"
MACHINES = {"amd64": "x86_64", "arm64": "aarch64"}
RUN_URL = re.compile(r"https://github\.com/street1983nk/nextcloud-audio-video-search/actions/runs/\d+")
COMMIT = re.compile(r"[0-9a-f]{40}")
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


def _record() -> dict:
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_the_record_carries_both_architectures_of_one_run() -> None:
    record = _record()

    assert RUN_URL.fullmatch(record["run_url"])
    assert COMMIT.fullmatch(record["sha"])
    for arch, machine in MACHINES.items():
        entry = record[arch]
        assert entry["arch"] == machine
        assert entry["code"] == "ok"  # the positive control of the probe: real speech was recognised
        assert entry["words"] > 0
        assert entry["ru_maxrss_kib"] > 0
        assert entry["vmhwm_kib"] > 0
        assert "OMP_THREAD_LIMIT" not in entry["threads_env"]


def test_the_constants_are_the_highest_value_on_record() -> None:
    record = _record()
    runs = (record, record["earlier_run"])

    assert set(measured.PARAKEET_PEAK_BYTES) == set(MACHINES)
    for arch in MACHINES:
        kib = max(max(run[arch]["ru_maxrss_kib"], run[arch]["vmhwm_kib"]) for run in runs)
        assert measured.PARAKEET_PEAK_BYTES[arch] == kib * 1024
        assert measured.PARAKEET_PEAK_BYTES[arch] > 0
    assert tuple(run["run_url"] for run in runs) == measured.MEASURED_RUNS


def test_the_record_holds_no_word_of_the_transcript() -> None:
    fields = {"arch", "ru_maxrss_kib", "vmhwm_kib", "code", "words", "seconds", "threads_env"}
    record = _record()

    assert set(record) == {*MACHINES, "run_url", "sha", "earlier_run"}
    assert set(record["earlier_run"]) == {*MACHINES, "run_url", "sha"}
    for entry in (*(record[arch] for arch in MACHINES), *(record["earlier_run"][arch] for arch in MACHINES)):
        assert set(entry) == fields
        assert isinstance(entry["words"], int)


def test_the_earlier_run_is_a_second_measurement_of_another_commit() -> None:
    record = _record()
    earlier = record["earlier_run"]

    assert RUN_URL.fullmatch(earlier["run_url"])
    assert earlier["run_url"] != record["run_url"]
    assert earlier["sha"] != record["sha"]
    for arch, machine in MACHINES.items():
        assert earlier[arch]["arch"] == machine
        assert earlier[arch]["code"] == "ok"
        assert earlier[arch]["words"] == record[arch]["words"]
