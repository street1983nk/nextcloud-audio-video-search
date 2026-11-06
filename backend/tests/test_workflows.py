"""Triggers, size and secret reach of the workflows, read as text.

- Every workflow file stays under GitHub's 500 KB cap (Findling plan 41-08: a
  larger file is refused before any job starts).
- A push block names branches or tags, and every tag pattern is the release
  pattern, so no stray tag starts a workflow (Findling plan 31-01).
- release.yml and store-submit.yml have no pull_request trigger: that absence
  is what keeps the signing key and the store token away from forks.
- store-submit.yml runs by hand only.
- Only those two files name the signing key or the store token.
- The ExApp half lives in backend/: python.yml runs its gates there, docker.yml
  builds the image out of it, deploy-harp.yml builds the same context, and
  Dependabot watches the Dockerfile and the uv lock file there.
"""

import re
from pathlib import Path

from audio_video_search_backend import APP_ID
from tests.conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CAP_BYTES = 500 * 1024
RELEASE_TAG = "'v[0-9]+.[0-9]+.[0-9]+'"
SECRET_HOLDERS = frozenset({"release.yml", "store-submit.yml"})
REQUIRED = ("python.yml", "php.yml", "docker.yml", "release.yml", "store-submit.yml", "deploy-harp.yml", "security.yml")


def workflow_files() -> list[Path]:
    return sorted(WORKFLOWS.glob("*.yml"))


def on_block(source: str) -> str:
    """The text of the top level on: block."""
    match = re.search(r"^on:\n(.*?)(?=^\S)", source, re.MULTILINE | re.DOTALL)
    assert match is not None
    return match.group(1)


def tag_patterns(source: str) -> list[str]:
    block = on_block(source)
    tags = re.search(r"^ {4}tags:\n((?: {6}- .*\n)+)", block, re.MULTILINE)
    return [line.strip()[2:] for line in tags.group(1).splitlines()] if tags else []


def test_the_required_workflows_exist() -> None:
    names = {path.name for path in workflow_files()}

    assert set(REQUIRED) <= names


def test_every_workflow_is_under_the_size_cap() -> None:
    assert [path.name for path in workflow_files() if path.stat().st_size >= CAP_BYTES] == []


def test_push_blocks_name_branches_or_release_tags_only() -> None:
    for path in workflow_files():
        source = path.read_text(encoding="utf-8")
        block = on_block(source)
        if "  push:" not in block:
            continue
        assert re.search(r"^ {4}(branches|tags):", block, re.MULTILINE), path.name
        assert all(pattern == RELEASE_TAG for pattern in tag_patterns(source)), path.name


def test_the_signing_workflows_cannot_be_started_from_a_pull_request() -> None:
    for name in SECRET_HOLDERS:
        assert "pull_request" not in on_block((WORKFLOWS / name).read_text(encoding="utf-8")), name


def test_the_store_submission_runs_by_hand_only() -> None:
    block = on_block((WORKFLOWS / "store-submit.yml").read_text(encoding="utf-8"))

    assert re.findall(r"^ {2}(\w+):", block, re.MULTILINE) == ["workflow_dispatch"]


def test_only_the_signing_workflows_name_the_key_or_the_store_token() -> None:
    for path in workflow_files():
        source = path.read_text(encoding="utf-8")
        if path.name not in SECRET_HOLDERS:
            assert "APP_PRIVATE_KEY" not in source, path.name
            assert "APPSTORE_TOKEN" not in source, path.name


def test_the_signing_workflows_refuse_other_repositories() -> None:
    # One repository carries both halves; its name follows the PHP app.
    repository = "street1983nk/nextcloud-audio-video-search"
    for name in SECRET_HOLDERS:
        assert f'"{repository}"' in (WORKFLOWS / name).read_text(encoding="utf-8"), name


def test_the_store_submission_checks_the_image_before_it_submits() -> None:
    source = (WORKFLOWS / "store-submit.yml").read_text(encoding="utf-8")

    assert source.index("imagetools inspect") < source.index("api/v1/apps/releases")
    assert "docker logout ghcr.io" in source


def backend_findings(sources: dict[str, str]) -> list[str]:
    """Every place where a workflow or Dependabot misses the backend/ half."""
    findings = []
    python = sources.get("python.yml", "")
    if not re.search(r"^defaults:\n  run:\n    working-directory: backend$", python, re.MULTILINE):
        findings.append("python.yml does not run in backend/")
    docker = sources.get("docker.yml", "")
    if "context: backend\n" not in docker or "file: backend/Dockerfile\n" not in docker:
        findings.append("docker.yml does not build out of backend/")
    if f"IMAGE: ghcr.io/street1983nk/{APP_ID}\n" not in docker:
        findings.append("docker.yml does not push the backend image")
    harp = sources.get("deploy-harp.yml", "")
    if f"BACKEND_APP_ID: {APP_ID}\n" not in harp or "./app-src/backend\n" not in harp:
        findings.append("deploy-harp.yml does not deploy the backend")
    dependabot = sources.get("dependabot.yml", "")
    for ecosystem in ("docker", "uv"):
        if not re.search(rf'package-ecosystem: {ecosystem}\n(?:    #.*\n)*    directory: "/backend"', dependabot):
            findings.append(f"dependabot {ecosystem} does not watch /backend")
    return findings


def real_sources() -> dict[str, str]:
    sources = {path.name: path.read_text(encoding="utf-8") for path in workflow_files()}
    sources["dependabot.yml"] = (REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    return sources


def test_workflows_and_dependabot_work_on_the_backend_half() -> None:
    assert backend_findings(real_sources()) == []


def test_the_backend_rule_fires_on_the_old_root_layout() -> None:
    old = {
        name: source.replace("working-directory: backend", "working-directory: .")
        .replace("context: backend", "context: .")
        .replace("./app-src/backend", "./app-src")
        .replace('"/backend"', '"/"')
        for name, source in real_sources().items()
    }

    assert backend_findings(old) == [
        "python.yml does not run in backend/",
        "docker.yml does not build out of backend/",
        "deploy-harp.yml does not deploy the backend",
        "dependabot docker does not watch /backend",
        "dependabot uv does not watch /backend",
    ]


def test_the_tag_pattern_parser_sees_a_stray_pattern() -> None:
    sample = "on:\n  push:\n    tags:\n      - 'v[0-9]+.[0-9]+.[0-9]+'\n      - 'source-*'\njobs:\n"

    assert tag_patterns(sample) == [RELEASE_TAG, "'source-*'"]


# -- the integration proof: six legs, both apps, Playwright --------------------

HARP_LEGS = frozenset(
    (server, runner)
    for server in ("stable33", "stable34", "stable35")
    for runner in ("ubuntu-24.04", "ubuntu-24.04-arm")
)


def harp_source() -> str:
    return (WORKFLOWS / "deploy-harp.yml").read_text(encoding="utf-8")


def test_the_integration_proof_holds_every_rule() -> None:
    assert harp_findings(harp_source()) == []


def test_the_matrix_parser_reads_six_legs() -> None:
    assert set(matrix_legs(harp_source())) == HARP_LEGS


def test_the_rule_fires_on_a_missing_arm64_leg() -> None:
    source = harp_source()
    broken = source.replace(
        "          - server-version: stable35\n            php-version: '8.3'\n            runner: ubuntu-24.04-arm\n",
        "",
    )
    assert broken != source

    assert harp_findings(broken) == ["deploy-harp.yml misses the leg stable35 on ubuntu-24.04-arm"]


def test_the_rule_fires_on_a_missing_server_version() -> None:
    broken = harp_source().replace("server-version: stable34", "server-version: stable32")

    assert harp_findings(broken) == [
        "deploy-harp.yml misses the leg stable34 on ubuntu-24.04",
        "deploy-harp.yml misses the leg stable34 on ubuntu-24.04-arm",
        "deploy-harp.yml runs the unknown leg stable32 on ubuntu-24.04",
        "deploy-harp.yml runs the unknown leg stable32 on ubuntu-24.04-arm",
    ]


def test_the_rule_fires_when_the_runner_does_not_come_from_the_matrix() -> None:
    broken = harp_source().replace("runs-on: ${{ matrix.runner }}", "runs-on: ubuntu-24.04")

    assert harp_findings(broken) == ["deploy-harp.yml does not run on the runner of the matrix"]


def test_the_rule_fires_without_the_php_app() -> None:
    broken = harp_source().replace("./occ app:enable audio_video_search\n", "./occ app:list\n")

    assert harp_findings(broken) == ["deploy-harp.yml does not enable the PHP app"]


def test_the_rule_fires_without_a_playwright_run() -> None:
    broken = harp_source().replace("npx playwright test", "npx playwright --version")

    assert harp_findings(broken) == ["deploy-harp.yml runs no playwright test"]


def test_the_rule_fires_on_an_upload_without_if_always() -> None:
    source = harp_source()
    marker = "      - name: Upload the Playwright report and the screenshots\n        if: always()\n"
    assert marker in source
    broken = source.replace(marker, "      - name: Upload the Playwright report and the screenshots\n")

    assert harp_findings(broken) == [
        "deploy-harp.yml uploads without if: always() in 'Upload the Playwright report and the screenshots'"
    ]


def test_the_rule_fires_when_one_leg_stops_the_others() -> None:
    broken = harp_source().replace("fail-fast: false", "fail-fast: true")

    assert harp_findings(broken) == ["deploy-harp.yml stops every leg when one fails (fail-fast is not false)"]
