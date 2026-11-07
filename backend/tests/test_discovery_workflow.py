"""The acceptance workflow of phase 2 (D-02-07), read as text.

- "Discovery acceptance" exists, runs one leg per push and the six legs of
  deploy-harp.yml when started by hand with legs=all.
- The built-in PHP server runs with eight workers and a 120 s limit, so a
  download Samba lets hang (Findling A6) does not block the instance (T-02-03).
- The main legs build backend/ exactly as checked out (T-02-02).
- The control leg leak-control applies ci/leak-control/read-proof-off.patch to
  a copy under RUNNER_TEMP only, and its image never leaves the runner: no
  package permission, no registry login, no ghcr.io, no docker save, no image
  in an artifact, no cache export, no tag except the local leak-control tag
  (D-02-10, T-02-01). No other job and no other workflow names the patch.

Every rule has a self test on a broken copy, so a gate whose body went missing
does not stay green.
"""

import json
import re

from tests.conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "discovery-e2e.yml"
PATCH_NAME = "read-proof-off.patch"
LEAK_IMAGE = "localhost:5000/audio_video_search_backend:leak-control"
SIX_LEGS = frozenset(
    (server, runner)
    for server in ("stable33", "stable34", "stable35")
    for runner in ("ubuntu-24.04", "ubuntu-24.04-arm")
)
ONE_LEG = [("stable33", "ubuntu-24.04")]


def source() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def job_text(text: str, job: str) -> str:
    """The text of one top level job, up to the next job or the end."""
    match = re.search(rf"^  {job}:\n(.*?)(?=^  [\w-]+:\n|\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def job_names(text: str) -> list[str]:
    jobs = re.search(r"^jobs:\n(.*)\Z", text, re.MULTILINE | re.DOTALL)
    return re.findall(r"^  ([\w-]+):\n", jobs.group(1), re.MULTILINE) if jobs else []


def steps_of(text: str) -> list[tuple[str, str]]:
    """(name, text) of every named step."""
    chunks = re.split(r"^      - name: ", text, flags=re.MULTILINE)[1:]
    return [(chunk.split("\n", 1)[0].strip(), chunk) for chunk in chunks]


def legs(text: str) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(legs for legs=all, legs otherwise) out of the include expression."""
    match = re.search(r"include: \$\{\{ fromJSON\(inputs\.legs == 'all' && '(\[.*?\])' \|\| '(\[.*?\])'\) \}\}", text)
    if match is None:
        return [], []

    def parse(raw: str) -> list[tuple[str, str]]:
        return [(entry["server-version"], entry["runner"]) for entry in json.loads(raw)]

    return parse(match.group(1)), parse(match.group(2))


def workflow_findings(text: str) -> list[str]:
    """Every place where the workflow falls short of the main legs' rules."""
    findings: list[str] = []
    if not re.search(r"^name: Discovery acceptance$", text, re.MULTILINE):
        findings.append("the workflow is not named Discovery acceptance")
    if not re.search(r"^  workflow_dispatch:\n    inputs:\n      legs:\n", text, re.MULTILINE):
        findings.append("workflow_dispatch has no input legs")
    if not re.search(r"^  push:\n    branches:\n      - '\*\*'$", text, re.MULTILINE):
        findings.append("the workflow does not run on every push")
    if job_names(text) != ["discovery", "leak-control"]:
        findings.append(f"the jobs are {job_names(text)}, not discovery and leak-control")
    every, default = legs(text)
    if set(every) != SIX_LEGS or len(every) != len(SIX_LEGS):
        findings.append("legs=all does not run the six legs")
    if default != ONE_LEG:
        findings.append("the default is not one leg stable33 on ubuntu-24.04")
    for job in ("discovery", "leak-control"):
        body = job_text(text, job)
        if "PHP_CLI_SERVER_WORKERS=8 php -d max_execution_time=120 -S " not in body:
            findings.append(f"{job} does not start php -S with 8 workers and max_execution_time=120")
        if "composer run serve" in body:
            findings.append(f"{job} starts the server through composer run serve")
    discovery = job_text(text, "discovery")
    guard = discovery.find("git -C app-src diff --quiet -- backend/")
    build = discovery.find("docker build ")
    if guard < 0 or build < 0 or guard > build:
        findings.append("discovery builds the image without git diff --quiet -- backend/ first")
    if "if: always()" not in discovery or "actions/upload-artifact@" not in discovery:
        findings.append("discovery uploads no logs with if: always()")
    for name, step in steps_of(text):
        if "actions/upload-artifact@" in step and not re.search(r"^ {8}if: always\(\)$", step, re.MULTILINE):
            findings.append(f"the upload '{name}' runs without if: always()")
    return findings


def leak_findings(text: str, others: dict[str, str]) -> list[str]:
    """Every way the control image or the patch could leave the control leg."""
    findings: list[str] = []
    leak = job_text(text, "leak-control")
    if not leak:
        return ["the workflow has no job leak-control"]
    if not re.search(r"^    permissions:\n      contents: read\n    env:", leak, re.MULTILINE):
        findings.append("leak-control does not hold contents: read as its only permission")
    for word in ("packages: write", "docker login", "ghcr.io", "docker save", "cache-to", "docker tag", "--output"):
        if word in leak:
            findings.append(f"leak-control contains {word}")
    if f"LEAK_IMAGE: {LEAK_IMAGE}\n" not in leak:
        findings.append("leak-control does not name the local leak-control image")
    if "LEAK_ROOT: ${{ runner.temp }}/" not in leak:
        findings.append("leak-control does not keep its copy under RUNNER_TEMP")
    for line in re.findall(r"^.*\bdocker (?:build|push)\b.*$", leak, re.MULTILINE):
        if '"${LEAK_IMAGE}"' not in line:
            findings.append(f"leak-control builds or pushes another image: {line.strip()}")
    applies = re.findall(r"^.*\bgit\b.*\bapply\b.*$", leak, re.MULTILINE)
    if not applies:
        findings.append("leak-control does not apply the patch")
    for line in applies:
        if not line.strip().startswith('git -C "${LEAK_ROOT}" apply'):
            findings.append(f"leak-control applies the patch outside RUNNER_TEMP: {line.strip()}")
    if PATCH_NAME not in leak:
        findings.append("leak-control does not name the patch")
    for name, step in steps_of(leak):
        if "actions/upload-artifact@" in step and re.search(r"\.tar|leak-backend|LEAK_ROOT|image", step):
            findings.append(f"leak-control uploads the image in '{name}'")
    for job in job_names(text):
        if job != "leak-control" and PATCH_NAME in job_text(text, job):
            findings.append(f"the job {job} names the patch")
    findings += [f"{name} names the patch" for name, other in sorted(others.items()) if PATCH_NAME in other]
    return findings


def other_workflows() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml") if path != WORKFLOW}


def test_the_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_the_main_legs_hold_every_rule() -> None:
    assert workflow_findings(source()) == []


def test_the_control_leg_holds_every_rule() -> None:
    assert leak_findings(source(), other_workflows()) == []


def test_the_leg_parser_reads_both_lists() -> None:
    every, default = legs(source())

    assert set(every) == SIX_LEGS
    assert default == ONE_LEG


def test_the_rule_fires_on_a_missing_leg_or_a_second_default_leg() -> None:
    text = source()
    arm35 = ',{"server-version":"stable35","php-version":"8.3","runner":"ubuntu-24.04-arm"}]'
    assert arm35 in text
    broken = text.replace(arm35, "]")
    default = '|| \'[{"server-version":"stable33","php-version":"8.2","runner":"ubuntu-24.04"}]\''
    assert default in broken
    broken = broken.replace(
        default,
        default.replace(
            'ubuntu-24.04"}]',
            'ubuntu-24.04"},{"server-version":"stable34","php-version":"8.2","runner":"ubuntu-24.04"}]',
        ),
    )

    assert workflow_findings(broken) == [
        "legs=all does not run the six legs",
        "the default is not one leg stable33 on ubuntu-24.04",
    ]


def test_the_rule_fires_on_the_default_server_settings() -> None:
    broken = source().replace("PHP_CLI_SERVER_WORKERS=8 php -d max_execution_time=120 -S ", "php -S ", 1)

    assert workflow_findings(broken) == ["discovery does not start php -S with 8 workers and max_execution_time=120"]


def test_the_rule_fires_without_the_clean_backend_guard() -> None:
    broken = source().replace("git -C app-src diff --quiet -- backend/\n", "")

    assert workflow_findings(broken) == ["discovery builds the image without git diff --quiet -- backend/ first"]


def test_the_rule_fires_without_the_dispatch_input_or_the_name() -> None:
    broken = (
        source()
        .replace("name: Discovery acceptance", "name: Discovery")
        .replace("    inputs:\n      legs:", "    inputs:\n      lanes:")
    )

    assert workflow_findings(broken) == [
        "the workflow is not named Discovery acceptance",
        "workflow_dispatch has no input legs",
    ]


def test_the_leak_rule_fires_on_docker_save() -> None:
    text = source()
    marker = '          docker push "${LEAK_IMAGE}"\n'
    assert marker in text
    broken = text.replace(marker, marker + '          docker save "${LEAK_IMAGE}" -o leak.tar\n')

    assert leak_findings(broken, {}) == ["leak-control contains docker save"]


def test_the_leak_rule_fires_on_packages_write() -> None:
    broken = source().replace(
        "    permissions:\n      contents: read\n    env:\n      SERVER_VERSION: stable33",
        "    permissions:\n      contents: read\n      packages: write\n    env:\n      SERVER_VERSION: stable33",
    )

    assert leak_findings(broken, {}) == [
        "leak-control does not hold contents: read as its only permission",
        "leak-control contains packages: write",
    ]


def test_the_leak_rule_fires_on_a_registry_login_and_a_second_tag() -> None:
    text = source()
    marker = '          docker push "${LEAK_IMAGE}"\n'
    login = "          docker login ghcr.io\n"
    push = "          docker push ghcr.io/street1983nk/audio_video_search_backend:leak\n"
    broken = text.replace(marker, marker + login + push)

    assert leak_findings(broken, {}) == [
        "leak-control contains docker login",
        "leak-control contains ghcr.io",
        "leak-control builds or pushes another image: docker push ghcr.io/street1983nk/audio_video_search_backend:leak",
    ]


def test_the_leak_rule_fires_on_a_patch_applied_to_the_checkout() -> None:
    text = source()
    line = '          git -C "${LEAK_ROOT}" apply "${GITHUB_WORKSPACE}/app-src/ci/leak-control/read-proof-off.patch"\n'
    assert line in text
    broken = text.replace(line, "          git -C app-src apply ci/leak-control/read-proof-off.patch\n")

    assert leak_findings(broken, {}) == [
        "leak-control applies the patch outside RUNNER_TEMP: git -C app-src apply ci/leak-control/read-proof-off.patch"
    ]


def test_the_leak_rule_fires_on_the_patch_in_another_job_or_workflow() -> None:
    text = source()
    marker = "        run: bash app-src/ci/discovery/topology.sh samba\n"
    assert marker in text
    broken = text.replace(marker, marker.replace("samba\n", "samba ci/leak-control/read-proof-off.patch\n"), 1)

    assert leak_findings(broken, {"other.yml": "git apply read-proof-off.patch"}) == [
        "the job discovery names the patch",
        "other.yml names the patch",
    ]


def test_the_leak_rule_fires_on_an_image_artifact_or_a_cache_export() -> None:
    text = source()
    broken = text.replace(
        "          name: leak-control-logs\n          path: logs/\n",
        "          name: leak-control-logs\n          path: leak.tar\n",
    )
    broken = broken.replace(
        'docker build -t "${LEAK_IMAGE}" "${LEAK_ROOT}/backend"',
        'docker build -t "${LEAK_IMAGE}" --cache-to type=gha "${LEAK_ROOT}/backend"',
    )

    assert leak_findings(broken, {}) == [
        "leak-control contains cache-to",
        "leak-control uploads the image in 'Upload the logs'",
    ]


# -- the topology (plan 02-01, task 2) ------------------------------------------

TOPOLOGY = REPO_ROOT / "ci" / "discovery" / "topology.sh"
OPERATIONS = (
    "upload_new",
    "overwrite",
    "copy_in_home",
    "rename_in_home",
    "tag_file",
    "move_home_to_team",
    "trash_file",
    "restore_file",
    "access_control",
    "exclude_user_after",
    "exclude_storage_after",
    "exclude_after",
    "revoke_cem",
    "vanish_cem",
    "delete_dan",
    "foreign_change",
    "reattach",
)
SUBCOMMANDS = ("samba", "part-a", "part-b", "control")
TOPOLOGY_WORDS = (
    "amazons3",
    " local ",
    "password::sessioncredentials",
    "password::logincredentials",
    "smbcacls",
    "acl_xattr",
    "groupfolders:permissions",
    "workflowengine",
    "timeout=20",
    "files_external_allow_create_new_local",
    "oc_credentials",
)


def topology_findings(script: str) -> list[str]:
    """Every case of D-02-07 the topology script does not build."""
    findings: list[str] = []
    if not script.startswith("#!/usr/bin/env bash\n") or "\nset -euo pipefail\n" not in script:
        findings.append("topology.sh is not a strict bash script")
    findings += [
        f"topology.sh has no function {name}"
        for name in OPERATIONS
        if not re.search(rf"^{name}\(\) \{{$", script, re.MULTILINE)
    ]
    operations = re.search(r"^OPERATIONS=\((.*?)\)$", script, re.MULTILINE | re.DOTALL)
    listed = set(operations.group(1).split()) if operations else set()
    findings += [f"topology.sh does not dispatch {name}" for name in OPERATIONS if name not in listed]
    findings += [f"topology.sh has no subcommand {name}" for name in SUBCOMMANDS if f"\t\t{name}) cmd_" not in script]
    findings += [f"topology.sh does not use {word.strip()}" for word in TOPOLOGY_WORDS if word not in script]
    for user in ("ana", "ben", "cem", "dan", "eva", "fritz"):
        if not re.search(rf"^NC_USERS=\(.*\b{user}\b.*\)$", script, re.MULTILINE):
            findings.append(f"topology.sh does not create the user {user}")
    for exclusion in ("--user=eva", "--group=extern", "--folder=privat"):
        if f"exclude {exclusion}\n" not in script:
            findings.append(f"topology.sh does not exclude {exclusion} before the first run")
    return findings


def test_the_topology_builds_every_case() -> None:
    assert topology_findings(TOPOLOGY.read_text(encoding="utf-8")) == []


def test_the_topology_rule_fires_on_a_missing_operation_and_backend() -> None:
    script = TOPOLOGY.read_text(encoding="utf-8")
    broken = script.replace("vanish_cem() {", "vanish() {").replace("amazons3", "s3")

    assert topology_findings(broken) == [
        "topology.sh has no function vanish_cem",
        "topology.sh does not use amazons3",
    ]


def test_the_topology_rule_fires_on_a_missing_exclusion_and_dispatch() -> None:
    script = TOPOLOGY.read_text(encoding="utf-8")
    broken = script.replace("\texclude --group=extern\n", "").replace("\tvanish_cem delete_dan", "\tdelete_dan")

    assert topology_findings(broken) == [
        "topology.sh does not dispatch vanish_cem",
        "topology.sh does not exclude --group=extern before the first run",
    ]
