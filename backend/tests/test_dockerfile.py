"""Static checks of the Dockerfile and the image scripts.

Images are not built on the development machine (RAM), so the rules a linter
such as hadolint would hold are held here as text, offline, on every run:
multi-stage, every base pinned by digest, a non-root user, a health check, no
ADD of a remote URL, apt lists removed, the app id in the entrypoint.
"""

import re

from audio_video_search_backend import APP_ID
from audio_video_search_backend.index.wordlist import SYSTEM_WORDLIST
from tests.conftest import BACKEND_ROOT

DOCKERFILE = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}")


def from_lines(source: str) -> list[str]:
    return [line.split()[1] for line in source.splitlines() if line.startswith("FROM ")]


def resolved_bases(source: str) -> list[str]:
    """Every FROM and COPY --from image, with ARG defaults substituted."""
    arguments = dict(re.findall(r"^ARG (\w+)=(\S+)$", source, re.MULTILINE))
    stages = set(re.findall(r"^FROM \S+ AS (\w+)", source, re.MULTILINE))
    images = [
        re.sub(r"\$\{(\w+)\}", lambda m: arguments.get(m.group(1), m.group(0)), ref) for ref in from_lines(source)
    ]
    images += [ref for ref in re.findall(r"COPY --from=(\S+)", source) if ref not in stages]
    return images


def unpinned(source: str) -> list[str]:
    return [image for image in resolved_bases(source) if not DIGEST.search(image)]


def test_the_build_is_multi_stage_with_a_runtime_stage_last() -> None:
    stages = re.findall(r"^FROM \S+ AS (\w+)", DOCKERFILE, re.MULTILINE)

    assert len(stages) >= 2
    assert stages[-1] == "runtime"


def test_every_base_image_is_pinned_by_digest() -> None:
    assert resolved_bases(DOCKERFILE)
    assert unpinned(DOCKERFILE) == []


def test_the_runtime_runs_as_a_fixed_non_root_user() -> None:
    runtime = DOCKERFILE.split(" AS runtime", 1)[1]
    users = re.findall(r"^USER (\S+)", runtime, re.MULTILINE)

    assert users == ["10001:10001"]


def test_health_check_entrypoint_and_app_module() -> None:
    assert (
        'HEALTHCHECK --interval=10s --timeout=5s --start-period=20s --retries=6 CMD ["/healthcheck.sh"]' in DOCKERFILE
    )
    assert f'"-m", "{APP_ID}.main"]' in DOCKERFILE
    assert f"/nc_app_{APP_ID}_data" in DOCKERFILE


def test_no_remote_add_and_apt_lists_are_removed() -> None:
    assert not re.search(r"^ADD\s+https?://", DOCKERFILE, re.MULTILINE)
    for block in re.findall(r"apt-get install[^\n]*(?:\n\s+[^\n]*)*", DOCKERFILE):
        assert "--no-install-recommends" in block
    assert DOCKERFILE.count("apt-get update") == DOCKERFILE.count("rm -rf /var/lib/apt/lists/*")


def test_the_frpc_download_is_checked_against_a_checksum() -> None:
    assert "sha256sum -c -" in DOCKERFILE
    assert len(re.findall(r"FRP_\w+_SHA256=[0-9a-f]{64}", DOCKERFILE)) == 2


def test_the_image_scripts_have_a_shebang_and_strict_mode() -> None:
    for name in ("entrypoint.sh", "healthcheck.sh", "start.sh"):
        text = (BACKEND_ROOT / "docker" / name).read_text(encoding="utf-8")
        assert text.startswith("#!/bin/"), name
        assert "set -e" in text, name
        assert "\r" not in text, name


def test_the_digest_rule_fires_on_a_tag() -> None:
    sample = "ARG BASE=python:3.13-slim\nFROM ${BASE} AS build\nCOPY --from=ghcr.io/astral-sh/uv:0.11 /uv /uv\n"

    assert unpinned(sample) == ["python:3.13-slim", "ghcr.io/astral-sh/uv:0.11"]


def runtime_stage(source: str) -> str:
    """The text of the last stage, the one that becomes the image."""
    return source[source.rindex("\nFROM ") :]


def test_the_german_word_list_is_installed_pinned_in_the_runtime_stage() -> None:
    # Owner 06.11.: the compound splitter needs /usr/share/dict/ngerman in the
    # image, otherwise "frist" never finds "Kündigungsfrist" (index/wordlist.py).
    runtime = runtime_stage(DOCKERFILE)

    assert "wngerman=20161207-15" in runtime
    assert "test -s /usr/share/dict/ngerman" in runtime
    # GPL-2+: the licence text travels with the image.
    assert f"/usr/local/share/{APP_ID}/COPYING.wngerman" in runtime


def test_the_word_list_path_of_the_image_is_the_one_the_code_reads() -> None:
    assert f"test -s {SYSTEM_WORDLIST.as_posix()}" in DOCKERFILE


def test_the_runtime_stage_rule_fires_on_a_list_in_the_build_stage() -> None:
    moved = "FROM base AS build\nRUN apt-get install wngerman=20161207-15\nFROM base AS runtime\nRUN true\n"

    assert "wngerman" not in runtime_stage(moved)


# The ffmpeg stage (plan 03-05). BtbN, last autobuild of October 2026, LGPL.
FFMPEG_AMD64 = "a64f3171e6ad1f7d358d28890a907ee478c331d1177ec696a93418f79ac3f1f3"
FFMPEG_ARM64 = "2ea30086a637e3f0ad0f49a1b38db34121422b85e93cc82df2e01d9ee5200809"
PYTHON_WORKFLOW = (BACKEND_ROOT.parent / ".github" / "workflows" / "python.yml").read_text(encoding="utf-8")


def stage(source: str, name: str) -> str:
    """The text of one build stage, from its FROM line up to the next FROM."""
    start = source.index(f" AS {name}\n")
    following = source.find("\nFROM ", start)
    return source[start : following if following != -1 else len(source)]


def ffmpeg_pins(source: str) -> dict[str, str]:
    """Release, build and amd64 checksum as written in a Dockerfile or a workflow."""
    pins: dict[str, str] = {}
    for key in ("FFMPEG_RELEASE", "FFMPEG_BUILD", "FFMPEG_AMD64_SHA256"):
        found = re.findall(rf"\b{key}=([\w.-]+)", source)
        pins[key] = found[0] if len(found) == 1 else f"<{len(found)} values>"
    return pins


def pin_mismatches(dockerfile: str, workflow: str) -> list[str]:
    image, ci = ffmpeg_pins(dockerfile), ffmpeg_pins(workflow)
    return [f"{key}: image {image[key]} != ci {ci[key]}" for key in image if image[key] != ci[key]]


def test_the_ffmpeg_stage_checks_both_checksums_and_refuses_a_gpl_build() -> None:
    ffmpeg = stage(DOCKERFILE, "ffmpeg")

    assert f"FFMPEG_AMD64_SHA256={FFMPEG_AMD64}" in ffmpeg
    assert f"FFMPEG_ARM64_SHA256={FFMPEG_ARM64}" in ffmpeg
    assert "FFMPEG_RELEASE=autobuild-2026-10-31-12-59" in ffmpeg
    assert 'echo "${FFMPEG_SHA256}  /tmp/ffmpeg.tar.xz" | sha256sum -c -' in ffmpeg
    assert "--proto '=https' --tlsv1.2" in ffmpeg
    assert "-lgpl-8.1" in ffmpeg
    assert "-gpl-" not in ffmpeg.replace("-lgpl-", "")
    # The licence check: a configuration line must be there, and it must not say GPL.
    assert '*"configuration: "*) ;;' in ffmpeg
    assert "*--enable-gpl*)" in ffmpeg
    assert "exit 1" in ffmpeg.split("*--enable-gpl*)", 1)[1].split(";;", 1)[0]


def test_only_ffmpeg_and_ffprobe_leave_the_ffmpeg_stage() -> None:
    copies = re.findall(r"^COPY --from=ffmpeg (\S+) (\S+)$", DOCKERFILE, re.MULTILINE)

    assert copies == [
        ("/usr/local/bin/ffmpeg", "/usr/local/bin/ffmpeg"),
        ("/usr/local/bin/ffprobe", "/usr/local/bin/ffprobe"),
    ]
    assert "COPY --from=ffmpeg" in runtime_stage(DOCKERFILE)
    # ffplay is in the archive too; it never leaves the stage.
    assert "ffplay" not in DOCKERFILE


def test_the_ci_job_installs_the_same_ffmpeg_as_the_image() -> None:
    assert pin_mismatches(DOCKERFILE, PYTHON_WORKFLOW) == []
    assert ffmpeg_pins(PYTHON_WORKFLOW)["FFMPEG_AMD64_SHA256"] == FFMPEG_AMD64
    assert "sha256sum -c -" in PYTHON_WORKFLOW
    assert 'echo "AVS_FFMPEG=' in PYTHON_WORKFLOW
    assert 'echo "AVS_FFPROBE=' in PYTHON_WORKFLOW
    # The install runs before the tests, or the tests never see it.
    assert PYTHON_WORKFLOW.index("Install the pinned LGPL ffmpeg") < PYTHON_WORKFLOW.index("- name: Tests")


def test_the_pin_comparison_fires_on_a_changed_checksum() -> None:
    changed = PYTHON_WORKFLOW.replace(FFMPEG_AMD64, "0" * 64)

    assert changed != PYTHON_WORKFLOW
    assert pin_mismatches(DOCKERFILE, changed) == [f"FFMPEG_AMD64_SHA256: image {FFMPEG_AMD64} != ci {'0' * 64}"]


def test_the_pin_comparison_fires_on_another_release_or_a_missing_pin() -> None:
    other = PYTHON_WORKFLOW.replace("autobuild-2026-10-31-12-59", "autobuild-2026-11-30-12-59")
    missing = re.sub(r"FFMPEG_BUILD=\S+", "", PYTHON_WORKFLOW)

    assert [m.split(":")[0] for m in pin_mismatches(DOCKERFILE, other)] == ["FFMPEG_RELEASE"]
    assert [m.split(":")[0] for m in pin_mismatches(DOCKERFILE, missing)] == ["FFMPEG_BUILD"]
