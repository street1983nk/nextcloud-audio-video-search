"""The two store archives: what goes in, how each is signed, which tag fits.

Since plan 01-10 one repository releases two apps (Findling pattern):

- ``audio_video_search``: the PHP app, staged out of ``php/`` with an include
  list (``appinfo lib templates js css img l10n`` plus ``LICENSE`` and
  ``CHANGELOG.md``), ``.gitkeep`` removed, code signed and release signed
  with ``APP_PRIVATE_KEY``.
- ``audio_video_search_backend``: the ExApp, whose archive carries
  ``backend/appinfo/info.xml`` byte for byte (``cmp``), because AppAPI reads the
  routes out of it, and is release signed with ``BACKEND_PRIVATE_KEY``.

Each certificate has its own pin in release.yml. The backend pin stays
``pending-certificate`` until app-certificate-requests PR 1417 is merged, and
the signing step stops with a sentence until then. docker.yml compares the
version of both info.xml and the image tag with the git tag.

The rules are read as text and, where a POSIX shell is at hand, run: the
staging subcommands are executed into a temporary directory and the result is
compared with the include list. Every rule has a counter sample that makes it
fire.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

SCRIPT = REPO_ROOT / "scripts" / "release" / "store-archive.sh"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
COMPANION = "audio_video_search"
BACKEND = "audio_video_search_backend"
COMPANION_DIRS = ("appinfo", "lib", "templates", "js", "css", "img", "l10n")
COMPANION_FILES = ("LICENSE", "CHANGELOG.md")
PENDING = "pending-certificate"
PENDING_MESSAGE = (
    "BACKEND_PRIVATE_KEY is not set; the backend certificate request "
    "(app-certificate-requests PR 1417) must be merged first."
)
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def function_body(script: str, name: str) -> str:
    """The body of one shell function, up to its closing brace in column one."""
    match = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}", script, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def env_value(source: str, key: str) -> str | None:
    match = re.search(rf"^  {key}: ['\"]?([^'\"\s]+)['\"]?\s*$", source, re.MULTILINE)
    return match.group(1) if match else None


def script_findings(script: str) -> list[str]:
    findings: list[str] = []
    companion = function_body(script, "stage_companion")
    backend = function_body(script, "stage_backend")
    if not companion:
        findings.append("store-archive.sh has no stage_companion")
    else:
        loop = re.search(r"for d in ([a-z0-9 ]+); do", companion)
        if loop is None or tuple(loop.group(1).split()) != COMPANION_DIRS:
            findings.append("stage_companion does not copy exactly the include list of php/")
        if '"php/${d}"' not in companion:
            findings.append("stage_companion does not copy out of php/")
        if f'/{COMPANION}"' not in companion:
            findings.append(f"stage_companion does not stage under {COMPANION}/")
        if not all(name in companion for name in COMPANION_FILES):
            findings.append("stage_companion does not take LICENSE and CHANGELOG.md along")
        if "-name '.gitkeep' -delete" not in companion:
            findings.append("stage_companion leaves .gitkeep files in the archive")
    if not backend:
        findings.append("store-archive.sh has no stage_backend")
    else:
        if f'/{BACKEND}"' not in backend:
            findings.append(f"stage_backend does not stage under {BACKEND}/")
        copies = re.findall(r"^\s*cp (?:-R )?(\S+)", backend, re.MULTILINE)
        if copies != ["backend/appinfo/info.xml", "LICENSE"]:
            findings.append("stage_backend copies more than backend/appinfo/info.xml, LICENSE and CHANGELOG.md")
        if not re.search(r"^\s*cmp backend/appinfo/info\.xml ", backend, re.MULTILINE):
            findings.append("stage_backend does not prove info.xml byte identical with cmp")
    for command in ("stage-companion)", "stage-backend)"):
        if command not in script:
            findings.append(f"store-archive.sh does not dispatch {command[:-1]}")
    return findings


def release_findings(release: str) -> list[str]:
    findings: list[str] = []
    companion_pin = env_value(release, "CERT_PUBKEY_SHA256")
    backend_pin = env_value(release, "BACKEND_CERT_PUBKEY_SHA256")
    if companion_pin is None or not SHA256_HEX.match(companion_pin):
        findings.append("release.yml has no sha256 pin CERT_PUBKEY_SHA256 for audio_video_search")
    if backend_pin is None or not (backend_pin == PENDING or SHA256_HEX.match(backend_pin)):
        findings.append("release.yml has no pin BACKEND_CERT_PUBKEY_SHA256 for audio_video_search_backend")
    if companion_pin is not None and companion_pin == backend_pin:
        findings.append("release.yml pins both certificates to the same key")
    if f'check {COMPANION} "${{CERT_PUBKEY_SHA256}}"' not in release:
        findings.append("release.yml does not check the companion certificate against its pin")
    if f'check {BACKEND} "${{BACKEND_CERT_PUBKEY_SHA256}}"' not in release:
        findings.append("release.yml does not check the backend certificate against its pin")
    if "${{ secrets.APP_PRIVATE_KEY }}" not in release:
        findings.append("release.yml does not sign with APP_PRIVATE_KEY")
    if "${{ secrets.BACKEND_PRIVATE_KEY }}" not in release:
        findings.append("release.yml does not sign with BACKEND_PRIVATE_KEY")
    if PENDING_MESSAGE not in release:
        findings.append("release.yml does not stop with the sentence about the pending backend certificate")
    for command in ("store-archive.sh stage-companion", "store-archive.sh stage-backend"):
        if command not in release:
            findings.append(f"release.yml does not run {command}")
    for archive in (f"dist/{COMPANION}.tar.gz.sig", f"dist/{BACKEND}.tar.gz.sig"):
        if "-sign " not in release or archive not in release:
            findings.append(f"release.yml does not produce {archive}")
    if "integrity:sign-app" not in release:
        findings.append("release.yml does not code sign the PHP app")
    return findings


def docker_findings(docker: str) -> list[str]:
    findings: list[str] = []
    tag_step = re.search(r"- name: The git tag.*?(?=\n      - name: )", docker, re.DOTALL)
    text = tag_step.group(0) if tag_step else ""
    for needle in ("php/appinfo/info.xml", "backend/appinfo/info.xml", "<image-tag>"):
        if needle not in text:
            findings.append(f"the tag check of docker.yml does not read {needle}")
    return findings


def submit_findings(submit: str) -> list[str]:
    findings: list[str] = []
    for app in (COMPANION, BACKEND):
        if f"- app: {app}\n" not in submit:
            findings.append(f"store-submit.yml does not submit {app}")
    if "IMAGE: ghcr.io/street1983nk/audio_video_search_backend\n" not in submit:
        findings.append("store-submit.yml checks the wrong image")
    return findings


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# -- the real files -------------------------------------------------------------


def test_the_archive_script_stages_both_apps() -> None:
    assert script_findings(read(SCRIPT)) == []


def test_the_release_workflow_builds_two_archives_with_two_pins() -> None:
    assert release_findings(read(WORKFLOWS / "release.yml")) == []


def test_the_image_workflow_checks_both_halves_against_the_tag() -> None:
    assert docker_findings(read(WORKFLOWS / "docker.yml")) == []


def test_the_store_submission_submits_both_archives() -> None:
    assert submit_findings(read(WORKFLOWS / "store-submit.yml")) == []


# -- counter samples ---------------------------------------------------------------


def test_the_include_list_rule_fires_on_an_extra_directory_and_a_kept_gitkeep() -> None:
    script = read(SCRIPT)
    broken = script.replace("img l10n; do", "img l10n tests; do").replace("-name '.gitkeep' -delete", "-name x")
    assert broken != script

    assert script_findings(broken) == [
        "stage_companion does not copy exactly the include list of php/",
        "stage_companion leaves .gitkeep files in the archive",
    ]


def test_the_backend_rule_fires_on_extra_content_and_a_missing_cmp() -> None:
    script = read(SCRIPT)
    broken = script.replace(
        "\tcp backend/appinfo/info.xml",
        '\tcp -R backend/l10n "${app}/l10n"\n\tcp backend/appinfo/info.xml',
    ).replace("\tcmp backend/appinfo/info.xml", "\ttrue backend/appinfo/info.xml")
    assert broken != script

    assert script_findings(broken) == [
        "stage_backend copies more than backend/appinfo/info.xml, LICENSE and CHANGELOG.md",
        "stage_backend does not prove info.xml byte identical with cmp",
    ]


def test_the_pin_rule_fires_on_a_missing_or_shared_pin() -> None:
    release = read(WORKFLOWS / "release.yml")
    companion_pin = env_value(release, "CERT_PUBKEY_SHA256")
    assert companion_pin is not None
    shared = re.sub(
        r"(?m)^  BACKEND_CERT_PUBKEY_SHA256: .*$", f"  BACKEND_CERT_PUBKEY_SHA256: {companion_pin}", release
    )
    assert release_findings(shared) == ["release.yml pins both certificates to the same key"]

    gone = re.sub(r"(?m)^  BACKEND_CERT_PUBKEY_SHA256: .*$", "  BACKEND_CERT_PUBKEY_SHA256: ''", release)
    assert release_findings(gone) == [
        "release.yml has no pin BACKEND_CERT_PUBKEY_SHA256 for audio_video_search_backend"
    ]


def test_the_signature_rule_fires_without_the_backend_key_or_its_sentence() -> None:
    release = read(WORKFLOWS / "release.yml")
    broken = release.replace("${{ secrets.BACKEND_PRIVATE_KEY }}", "${{ secrets.APP_PRIVATE_KEY }}").replace(
        PENDING_MESSAGE, "no key"
    )
    assert broken != release

    assert release_findings(broken) == [
        "release.yml does not sign with BACKEND_PRIVATE_KEY",
        "release.yml does not stop with the sentence about the pending backend certificate",
    ]


def test_the_tag_rule_fires_when_docker_yml_reads_one_half_only() -> None:
    docker = read(WORKFLOWS / "docker.yml")
    broken = docker.replace("php/appinfo/info.xml", "backend/appinfo/info.xml")
    assert broken != docker

    assert docker_findings(broken) == ["the tag check of docker.yml does not read php/appinfo/info.xml"]


def test_the_submission_rule_fires_on_a_single_app() -> None:
    submit = read(WORKFLOWS / "store-submit.yml")
    broken = submit.replace(f"- app: {BACKEND}\n", "")
    assert broken != submit

    assert submit_findings(broken) == [f"store-submit.yml does not submit {BACKEND}"]


# -- the staging run itself ------------------------------------------------------

SH = shutil.which("sh")
needs_sh = pytest.mark.skipif(SH is None, reason="no POSIX sh on this machine")


def stage(command: str, target: Path) -> None:
    assert SH is not None
    subprocess.run([SH, str(SCRIPT), command, str(target)], cwd=REPO_ROOT, check=True, capture_output=True)  # noqa: S603


def tree(root: Path) -> list[str]:
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file())


@needs_sh
def test_the_companion_stage_holds_the_include_list_and_nothing_else(tmp_path: Path) -> None:
    stage("stage-companion", tmp_path)

    assert [path.name for path in tmp_path.iterdir()] == [COMPANION]
    app = tmp_path / COMPANION
    assert sorted(path.name for path in app.iterdir()) == sorted(COMPANION_DIRS + COMPANION_FILES)
    files = tree(app)
    assert "appinfo/info.xml" in files
    assert not [name for name in files if name.endswith(".gitkeep") or name.startswith("tests/")]
    assert (app / "appinfo" / "info.xml").read_bytes() == (REPO_ROOT / "php" / "appinfo" / "info.xml").read_bytes()


@needs_sh
def test_the_backend_stage_carries_info_xml_byte_for_byte(tmp_path: Path) -> None:
    stage("stage-backend", tmp_path)

    app = tmp_path / BACKEND
    assert tree(app) == ["CHANGELOG.md", "LICENSE", "appinfo/info.xml"]
    assert (app / "appinfo" / "info.xml").read_bytes() == (REPO_ROOT / "backend" / "appinfo" / "info.xml").read_bytes()
