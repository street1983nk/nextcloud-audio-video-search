"""Triggers, size and secret reach of the workflows, read as text.

- Every workflow file stays under GitHub's 500 KB cap (Findling plan 41-08: a
  larger file is refused before any job starts).
- A push block names branches or tags, and every tag pattern is the release
  pattern, so no stray tag starts a workflow (Findling plan 31-01).
- release.yml and store-submit.yml have no pull_request trigger: that absence
  is what keeps the signing key and the store token away from forks.
- store-submit.yml runs by hand only.
- Only those two files name the signing key or the store token.
"""

import re
from pathlib import Path

from audio_video_search_backend import APP_ID
from tests.conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CAP_BYTES = 500 * 1024
RELEASE_TAG = "'v[0-9]+.[0-9]+.[0-9]+'"
SECRET_HOLDERS = frozenset({"release.yml", "store-submit.yml"})
REQUIRED = ("python.yml", "docker.yml", "release.yml", "store-submit.yml", "deploy-harp.yml", "security.yml")


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
    repository = f"street1983nk/nextcloud-{APP_ID.replace('_', '-')}"
    for name in SECRET_HOLDERS:
        assert f'"{repository}"' in (WORKFLOWS / name).read_text(encoding="utf-8"), name


def test_the_store_submission_checks_the_image_before_it_submits() -> None:
    source = (WORKFLOWS / "store-submit.yml").read_text(encoding="utf-8")

    assert source.index("imagetools inspect") < source.index("api/v1/apps/releases")
    assert "docker logout ghcr.io" in source


def test_the_tag_pattern_parser_sees_a_stray_pattern() -> None:
    sample = "on:\n  push:\n    tags:\n      - 'v[0-9]+.[0-9]+.[0-9]+'\n      - 'source-*'\njobs:\n"

    assert tag_patterns(sample) == [RELEASE_TAG, "'source-*'"]
