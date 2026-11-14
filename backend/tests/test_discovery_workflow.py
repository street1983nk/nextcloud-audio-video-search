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
- No workflow reads the runner context in a workflow or job env block: GitHub
  rejects the whole file there (push 1 of phase 2, line 414), so the run never
  starts. Step env and run lines may read it.
- The S3 server never takes a port of the leg (push 2: its volume server took
  8080 from Nextcloud), and the phases run only after a successful setup, with
  a bounded wait and a step limit (push 2 waited two hours for nothing).
- The cron loop of both jobs starts only after the apps are enabled: a
  cron.php that began earlier removed the jobs of the app (push 7, plan 02-17b).

Every rule has a self test on a broken copy, so a gate whose body went missing
does not stay green.
"""

import json
import re

import pytest

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
    # The PHP app is moved out of the checkout before, so only backend/ can be clean.
    applied = max((leak.find(line) for line in applies), default=-1)
    guard = leak.find("git -C app-src diff --quiet -- backend/\n")
    build = leak.find("docker build ")
    if guard < 0 or guard < applied or build < 0 or guard > build:
        findings.append("leak-control builds the image without git diff --quiet -- backend/ after the patch")
    if re.search(r"^ *git -C app-src diff --quiet$", leak, re.MULTILINE):
        findings.append("leak-control asks for a clean checkout although the PHP app was moved out of it")
    for name, step in steps_of(leak):
        if "actions/upload-artifact@" in step and re.search(r"\.tar|leak-backend|LEAK_ROOT|image", step):
            findings.append(f"leak-control uploads the image in '{name}'")
    for job in job_names(text):
        if job != "leak-control" and PATCH_NAME in job_text(text, job):
            findings.append(f"the job {job} names the patch")
    findings += [f"{name} names the patch" for name, other in sorted(others.items()) if PATCH_NAME in other]
    return findings


def runner_env_findings(name: str, text: str) -> list[str]:
    """Workflow and job env entries that read the runner context."""
    findings: list[str] = []
    block: int | None = None
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if block is not None and stripped and indent <= block:
            block = None
        if stripped == "env:" and indent in (0, 4):
            block = indent
            continue
        if block is not None and re.search(r"\$\{\{[^}]*\brunner\.", line):
            findings.append(f"{name}:{number} reads the runner context in a {'job' if block else 'workflow'} env")
    return findings


def port_findings(text: str) -> list[str]:
    """The S3 server of the discovery leg never takes a port another service of the leg uses."""
    findings: list[str] = []
    discovery = job_text(text, "discovery")
    volume = re.search(r"^  S3_VOLUME_PORT: '(\d+)'$", text, re.MULTILINE)
    if volume is None:
        return ["the workflow names no S3_VOLUME_PORT"]
    if '-volume.port="${S3_VOLUME_PORT}"' not in discovery:
        findings.append("weed server starts without -volume.port, so its volume server takes 8080")
    taken = set(re.findall(r"-S 0\.0\.0\.0:(\d+)", discovery))
    taken |= set(re.findall(r"listen (\d+);", discovery))
    taken |= set(re.findall(r"-p (\d+):\d+", discovery))
    taken |= set(re.findall(r"^  S3_PORT: '(\d+)'$", text, re.MULTILINE))
    if volume.group(1) in taken:
        findings.append(f"S3_VOLUME_PORT {volume.group(1)} is taken by another service of the leg")
    return findings


def phase_guard_findings(text: str) -> list[str]:
    """The phases run only after the setup succeeded, with a bounded wait and a step limit."""
    findings: list[str] = []
    steps = dict(steps_of(job_text(text, "discovery")))
    setup = steps.get("Topology part B, after the backend is registered", "")
    if "\n        id: setup\n" not in setup:
        findings.append("the last setup step has no id setup")
    phases = steps.get("Run the phases", "")
    if "if: ${{ !cancelled() && steps.setup.outcome == 'success' }}" not in phases:
        findings.append("the phases do not wait for a successful setup")
    if not re.search(r"^        timeout-minutes: \d+$", phases, re.MULTILINE):
        findings.append("the phases step has no timeout-minutes")
    if not re.search(r"^          WAIT_LIMIT: '\d+'$", phases, re.MULTILINE):
        findings.append("the phases step does not bound WAIT_LIMIT")
    return findings


def other_workflows() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml") if path != WORKFLOW}


def test_the_workflow_exists() -> None:
    assert WORKFLOW.is_file()


def test_the_main_legs_hold_every_rule() -> None:
    assert workflow_findings(source()) == []


def test_the_control_leg_holds_every_rule() -> None:
    assert leak_findings(source(), other_workflows()) == []


def test_no_workflow_reads_the_runner_context_in_a_workflow_or_job_env() -> None:
    texts = {path.name: path.read_text(encoding="utf-8") for path in sorted(WORKFLOWS.glob("*.yml"))}

    assert [finding for name, text in texts.items() for finding in runner_env_findings(name, text)] == []


def test_the_runner_env_rule_fires_on_a_job_and_a_workflow_env() -> None:
    text = source()
    job_env = "      LEAK_IMAGE: localhost:5000/audio_video_search_backend:leak-control\n"
    assert job_env in text
    broken = text.replace(job_env, job_env + "      LEAK_ROOT: ${{ runner.temp }}/leak-backend\n", 1)
    broken = "env:\n  TOOLS: ${{ runner.tool_cache }}\n" + broken

    findings = runner_env_findings("discovery-e2e.yml", broken)

    assert len(findings) == 2
    assert findings[0] == "discovery-e2e.yml:2 reads the runner context in a workflow env"
    assert findings[1].endswith("reads the runner context in a job env")
    assert runner_env_findings("discovery-e2e.yml", text) == []


def test_the_s3_server_keeps_off_the_ports_of_the_leg() -> None:
    assert port_findings(source()) == []


def test_the_port_rule_fires_without_the_volume_port_or_on_a_taken_one() -> None:
    text = source()
    flag = '-volume.port="${S3_VOLUME_PORT}" '
    assert flag in text
    assert port_findings(text.replace(flag, "")) == [
        "weed server starts without -volume.port, so its volume server takes 8080"
    ]
    assert port_findings(text.replace("  S3_VOLUME_PORT: '8380'", "  S3_VOLUME_PORT: '8080'")) == [
        "S3_VOLUME_PORT 8080 is taken by another service of the leg"
    ]


def test_the_phases_wait_for_the_setup() -> None:
    assert phase_guard_findings(source()) == []


def test_the_phase_guard_fires_on_the_old_condition_and_without_limits() -> None:
    broken = (
        source()
        .replace("if: ${{ !cancelled() && steps.setup.outcome == 'success' }}", "if: ${{ !cancelled() }}")
        .replace("        timeout-minutes: 90\n", "")
        .replace("          WAIT_LIMIT: '300'\n", "")
        .replace("        id: setup\n", "")
    )

    assert phase_guard_findings(broken) == [
        "the last setup step has no id setup",
        "the phases do not wait for a successful setup",
        "the phases step has no timeout-minutes",
        "the phases step does not bound WAIT_LIMIT",
    ]


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


def test_the_leak_rule_fires_on_a_guard_over_the_whole_checkout() -> None:
    text = source()
    leak = job_text(text, "leak-control")
    guard = "          git -C app-src diff --quiet -- backend/\n"
    assert guard in leak
    broken = text.replace(leak, leak.replace(guard, guard.replace(" -- backend/", "")))

    assert leak_findings(broken, {}) == [
        "leak-control builds the image without git diff --quiet -- backend/ after the patch",
        "leak-control asks for a clean checkout although the PHP app was moved out of it",
    ]


def test_the_leak_rule_fires_on_a_guard_before_the_patch() -> None:
    text = source()
    leak = job_text(text, "leak-control")
    guard = "          git -C app-src diff --quiet -- backend/\n"
    copy = '          cp -a app-src/backend "${LEAK_ROOT}/backend"\n'
    assert guard in leak
    assert copy in leak
    broken = text.replace(leak, leak.replace(guard, "").replace(copy, copy + guard))

    assert leak_findings(broken, {}) == [
        "leak-control builds the image without git diff --quiet -- backend/ after the patch"
    ]


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
    "oc_storages_credentials",
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


# -- the verdict: truth, ledger, comparison and controls (plan 02-04) -------------

DISCOVERY = REPO_ROOT / "ci" / "discovery"
VERDICT_SCRIPTS = ("common.sh", "truth.sh", "ledger.sh", "compare.sh", "controls.sh")
PHASES = (
    "initial",
    "read-proof",
    "shares",
    "access-control",
    "upload",
    "overwrite",
    "copy",
    "rename",
    "tag",
    "move-cross",
    "trash",
    "restore",
    "exclude-user-after",
    "exclude-storage-after",
    "exclude-after",
    "reprove",
    "vanish",
    "delete-user",
    "reattach",
    "foreign-change",
)
# (shift in the expectation, the one check it has to make fail on its own)
SELF_TEST_SHIFTS = (
    ("'.N_active += 1'", "files_count"),
    ("'.Y += 1'", "contents"),
    ('"$((transcribed + 1))"', "transcribed"),
    ('>> "${log}"', "never_in_log"),
    ('>> "${foreign}"', "session_shared_readers"),
)
# The order of the verdict in the job discovery, as plain substrings.
VERDICT_ORDER = (
    "controls.sh samba",
    "topology.sh part-a",
    "app_api:app:register",
    "topology.sh part-b",
    "compare.sh --self-test",
    "compare.sh wait",
    "controls.sh access-log",
    "- name: Run the phases",
    "- name: The verdict of all phases",
)


# Phases whose effect only the reconcile of the container brings (plan 02-20):
# the renewed proof, a storage that left the mount list, a deleted user. The
# loop of the container runs every 300 s, compare.sh wait may return before
# it, so the phase starts one round at once (owner 14.11.2026).
RECONCILE_AFTER = {
    "reprove": 'bash "${d}/topology.sh" revoke_cem && ./occ audio_video_search:reconcile --reprove',
    "vanish": 'bash "${d}/topology.sh" vanish_cem && ./occ audio_video_search:reconcile',
    "delete-user": 'bash "${d}/topology.sh" delete_dan && ./occ audio_video_search:reconcile',
}

# Phases whose rule only SchedulerJob turns into work (plan 02-18): a user, a
# storage or a folder excluded after the first crawl. The job runs every
# 300 s, and compare.sh wait cannot see a rule that is not applied yet: run
# 43561950802 judged all three phases 0 s after the rule, with no
# exclude_storage or exclude row ever created. So the phase runs the job and
# every clearing job it plans at once.
EXCLUSIONS_AFTER = {
    "exclude-user-after": 'bash "${d}/topology.sh" exclude_user_after && bash "${d}/compare.sh" exclusions',
    "exclude-storage-after": 'bash "${d}/topology.sh" exclude_storage_after && bash "${d}/compare.sh" exclusions',
    "exclude-after": 'bash "${d}/topology.sh" exclude_after && bash "${d}/compare.sh" exclusions',
}
# What compare.sh exclusions has to contain: its subcommand, the forced run and
# the two jobs of the app it runs.
EXCLUSIONS_RUN = (
    "exclusions) cmd_exclusions ;;",
    "background-job:execute --force-execute",
    "OCA\\AudioVideoSearch\\BackgroundJobs\\SchedulerJob",
    "OCA\\AudioVideoSearch\\BackgroundJobs\\ExclusionClearJob",
)


def code_lines(script: str) -> list[str]:
    """The lines of a bash script that are not comments."""
    return [line for line in script.splitlines() if not line.lstrip().startswith("#")]


def script_findings(scripts: dict[str, str]) -> list[str]:
    """The truth stays free of app code, the comparison and the controls can fail."""
    findings: list[str] = []
    for name in ("common.sh", "truth.sh", "ledger.sh", "controls.sh"):
        code = "\n".join(code_lines(scripts[name]))
        findings += [f"{name} contains {word}" for word in ("audio_video_search_backend", "php -r") if word in code]
    # truth.sh sources common.sh, so both stay free of the app.
    for name in ("common.sh", "truth.sh"):
        code = "\n".join(code_lines(scripts[name]))
        findings += [f"{name} contains {word}" for word in ("audio_video_search:", "docker exec") if word in code]
    phases = re.search(r"^PHASES=\((.*?)\)$", scripts["common.sh"], re.MULTILINE | re.DOTALL)
    if phases is None or tuple(phases.group(1).split()) != PHASES:
        findings.append("common.sh does not list the phases of plan 02-04 in order")

    compare = scripts["compare.sh"]
    if "--self-test) cmd_self_test ;;" not in compare:
        findings.append("compare.sh has no --self-test")
    for shift, check in SELF_TEST_SHIFTS:
        if shift not in compare:
            findings.append(f"the self test of compare.sh does not shift {check}")
        if not re.search(rf"^\s*shift_one \S+ {check} ", compare, re.MULTILINE):
            findings.append(f"the self test of compare.sh does not expect {check} to fail on its own")
    if "GET /ocs/v2.php/apps/audio_video_search/files/${never}" not in compare:
        findings.append("the self test of compare.sh does not inject a gateway line for a never fetched file")
    if 'fail "compare self-test did not fail"' not in compare:
        findings.append("the self test of compare.sh does not stop the run")
    if 'check transcribed "${expected}"' not in compare:
        findings.append("compare.sh does not check transcribed for equality with the ledger")
    # A mount with session credentials may lie on a storage that a mount with
    # stored credentials captures (M2 and M1 of ana): those ids are fetched, so
    # they cannot be "never fetched"; who fetched them is checked instead.
    truth = "\n".join(code_lines(scripts["truth.sh"]))
    if re.search(r'media_ids_below \S+ \S*SMB-Sitzung\S* >> "\$\{NEVER\}"', truth):
        findings.append("truth.sh takes every id of the session mount for never fetched")
    if "session_mount ana /ana/files/SMB-Sitzung/" not in truth:
        findings.append("truth.sh does not split the ids of the session mount by their other ways")
    if 'echo "${id}" >> "${NEVER}"' not in truth:
        findings.append("truth.sh keeps no id of the session mount as never fetched")
    if "sessionShared:" not in truth:
        findings.append("truth.sh does not write sessionShared")
    if "check session_shared_readers '' " not in compare:
        findings.append("compare.sh does not check who fetched the ids shared with the session mount")
    if ".dueWork == 0" not in compare:
        findings.append("compare.sh wait does not wait for dueWork")
    if "((.crawl.finished + .crawl.open) > 0)" not in compare:
        findings.append("compare.sh wait takes a stock without any first crawl for complete")
    if 'echo "PHASE PASS ${PHASE}"' not in compare:
        findings.append("compare.sh does not write PHASE PASS")
    compare_code = "\n".join(code_lines(compare))
    if any(part not in compare_code for part in EXCLUSIONS_RUN):
        findings.append("compare.sh exclusions does not run SchedulerJob and its clearing jobs")

    controls = scripts["controls.sh"]
    if 'echo "LEAK CONTROL SHOWED THE LEAK"' not in controls:
        findings.append("controls.sh does not write LEAK CONTROL SHOWED THE LEAK")
    for command, function in (("samba", "cmd_samba"), ("access-log", "cmd_access_log"), ("leak", "cmd_leak")):
        if f"\t{command}) {function} ;;" not in controls:
            findings.append(f"controls.sh has no subcommand {command}")
    for message in ("samba positive control failed, run invalid", "access log positive control failed, run invalid"):
        if message not in controls:
            findings.append(f"controls.sh does not say '{message}'")
    return findings


def flow_findings(workflow: str) -> list[str]:
    """The workflow runs the controls, the self tests and every phase in order."""
    findings: list[str] = []
    discovery = job_text(workflow, "discovery")
    loop = re.search(r"for phase in (.*?); do", discovery, re.DOTALL)
    listed = tuple(loop.group(1).replace("\\", " ").split()) if loop else ()
    if listed != PHASES:
        findings.append("the job discovery does not run the phases of plan 02-04 in order")
    places = [discovery.find(part) for part in VERDICT_ORDER]
    if any(place < 0 for place in places) or places != sorted(places):
        findings.append("the job discovery does not run the verdict in the order of plan 02-04")
    verdict = dict(steps_of(discovery)).get("The verdict of all phases", "")
    if not re.search(r"^ {8}if: always\(\)$", verdict, re.MULTILINE) or "PHASE FAIL" not in verdict:
        findings.append("the verdict step does not run with if: always() over the phase results")
    if "bash app-src/ci/discovery/controls.sh leak" not in job_text(workflow, "leak-control"):
        findings.append("the job leak-control does not run controls.sh leak")
    for phase, operation in RECONCILE_AFTER.items():
        if not re.search(rf"^\s*{re.escape(phase)}\) {re.escape(operation)} ;;$", discovery, re.MULTILINE):
            findings.append(f"the phase {phase} does not start a reconcile right after its operation")
    for phase, operation in EXCLUSIONS_AFTER.items():
        if not re.search(rf"^\s*{re.escape(phase)}\) {re.escape(operation)} ;;$", discovery, re.MULTILINE):
            findings.append(f"the phase {phase} does not apply its exclusion right after its operation")
    return findings


def verdict_scripts() -> dict[str, str]:
    return {name: (DISCOVERY / name).read_text(encoding="utf-8") for name in VERDICT_SCRIPTS}


def test_the_verdict_is_independent_and_able_to_fail() -> None:
    assert script_findings(verdict_scripts()) == []


def test_the_workflow_runs_the_verdict_in_order() -> None:
    assert flow_findings(source()) == []


def test_the_script_rule_fires_on_app_code_in_the_truth() -> None:
    scripts = verdict_scripts()
    scripts["truth.sh"] += '\nocc audio_video_search:files --json --all\ndocker exec "${C}" true\n'

    assert script_findings(scripts) == [
        "truth.sh contains audio_video_search:",
        "truth.sh contains docker exec",
    ]


def test_the_script_rule_ignores_comments_but_not_the_backend_module() -> None:
    scripts = verdict_scripts()
    scripts["truth.sh"] += "\n# occ audio_video_search:files is what compare.sh reads\n"
    scripts["ledger.sh"] += "\npython3 -m audio_video_search_backend.store\n"

    assert script_findings(scripts) == ["ledger.sh contains audio_video_search_backend"]


def test_the_script_rule_fires_on_a_wait_before_the_first_crawl() -> None:
    scripts = verdict_scripts()
    planned = "((.crawl.finished + .crawl.open) > 0)"
    assert planned in scripts["compare.sh"]
    scripts["compare.sh"] = scripts["compare.sh"].replace(planned, "true")

    assert script_findings(scripts) == ["compare.sh wait takes a stock without any first crawl for complete"]


def test_the_script_rule_fires_on_a_session_mount_taken_for_never_fetched() -> None:
    scripts = verdict_scripts()
    split = "\tsession_mount ana /ana/files/SMB-Sitzung/\n"
    assert split in scripts["truth.sh"]
    scripts["truth.sh"] = scripts["truth.sh"].replace(
        split, '\tmedia_ids_below ana /ana/files/SMB-Sitzung/ >> "${NEVER}"\n'
    )

    assert script_findings(scripts) == [
        "truth.sh takes every id of the session mount for never fetched",
        "truth.sh does not split the ids of the session mount by their other ways",
    ]


def test_the_script_rule_fires_on_a_session_mount_that_is_never_never_fetched() -> None:
    scripts = verdict_scripts()
    never = 'echo "${id}" >> "${NEVER}"'
    assert never in scripts["truth.sh"]
    scripts["truth.sh"] = scripts["truth.sh"].replace(never, "true").replace("sessionShared:", "shared:")

    assert script_findings(scripts) == [
        "truth.sh keeps no id of the session mount as never fetched",
        "truth.sh does not write sessionShared",
    ]


def test_the_script_rule_fires_on_unchecked_readers_of_the_shared_ids() -> None:
    scripts = verdict_scripts()
    check = "check session_shared_readers '' "
    assert check in scripts["compare.sh"]
    compare = scripts["compare.sh"].replace(check, "echo ")
    scripts["compare.sh"] = compare.replace('>> "${foreign}"', '> "${foreign}"')

    assert script_findings(scripts) == [
        "the self test of compare.sh does not shift session_shared_readers",
        "compare.sh does not check who fetched the ids shared with the session mount",
    ]


def test_the_script_rule_fires_on_a_missing_self_test_shift() -> None:
    scripts = verdict_scripts()
    assert "'.Y += 1'" in scripts["compare.sh"]
    compare = scripts["compare.sh"].replace("'.Y += 1'", "'.Y += 0'")
    scripts["compare.sh"] = re.sub(
        r"^(\s*)shift_one (\S+) transcribed ", r"\1shift_one \2 contents ", compare, flags=re.MULTILINE
    )

    assert script_findings(scripts) == [
        "the self test of compare.sh does not shift contents",
        "the self test of compare.sh does not expect transcribed to fail on its own",
    ]


def test_the_script_rule_fires_on_a_weak_transcribed_check_and_no_leak_line() -> None:
    scripts = verdict_scripts()
    scripts["compare.sh"] = scripts["compare.sh"].replace(
        'check transcribed "${expected}"', 'check_le transcribed "${expected}"'
    )
    scripts["controls.sh"] = scripts["controls.sh"].replace('echo "LEAK CONTROL SHOWED THE LEAK"', 'echo "leak shown"')

    assert script_findings(scripts) == [
        "compare.sh does not check transcribed for equality with the ledger",
        "controls.sh does not write LEAK CONTROL SHOWED THE LEAK",
    ]


def test_the_flow_rule_fires_on_a_missing_phase() -> None:
    text = source()
    assert " reattach foreign-change; do" in text
    broken = text.replace(" reattach foreign-change; do", " foreign-change; do")

    assert flow_findings(broken) == ["the job discovery does not run the phases of plan 02-04 in order"]


@pytest.mark.parametrize("phase", sorted(RECONCILE_AFTER))
def test_the_flow_rule_fires_without_the_reconcile_after_its_operation(phase: str) -> None:
    text = source()
    line = f"{phase}) {RECONCILE_AFTER[phase]} ;;"
    operation = RECONCILE_AFTER[phase].split(" && ")[0]
    assert text.count(line) == 1
    broken = text.replace(line, f"{phase}) {operation} ;;")

    assert flow_findings(broken) == [f"the phase {phase} does not start a reconcile right after its operation"]


@pytest.mark.parametrize("phase", sorted(EXCLUSIONS_AFTER))
def test_the_flow_rule_fires_without_applying_the_exclusion_after_its_operation(phase: str) -> None:
    text = source()
    line = f"{phase}) {EXCLUSIONS_AFTER[phase]} ;;"
    operation = EXCLUSIONS_AFTER[phase].split(" && ")[0]
    assert text.count(line) == 1
    broken = text.replace(line, f"{phase}) {operation} ;;")

    assert flow_findings(broken) == [f"the phase {phase} does not apply its exclusion right after its operation"]


@pytest.mark.parametrize("part", EXCLUSIONS_RUN)
def test_the_script_rule_fires_when_compare_does_not_run_the_exclusion_jobs(part: str) -> None:
    scripts = verdict_scripts()
    assert part in scripts["compare.sh"]
    scripts["compare.sh"] = scripts["compare.sh"].replace(part, "true")

    assert script_findings(scripts) == ["compare.sh exclusions does not run SchedulerJob and its clearing jobs"]


def test_the_script_rule_ignores_the_exclusion_jobs_in_a_comment_only() -> None:
    scripts = verdict_scripts()
    commented = "\n".join(f"# {part}" for part in EXCLUSIONS_RUN)
    scripts["compare.sh"] = "\n".join(
        line for line in scripts["compare.sh"].splitlines() if not any(part in line for part in EXCLUSIONS_RUN)
    )
    scripts["compare.sh"] += f"\n{commented}\n"

    assert script_findings(scripts) == ["compare.sh exclusions does not run SchedulerJob and its clearing jobs"]


def test_the_flow_rule_fires_when_the_access_log_control_comes_first() -> None:
    text = source()
    marker = "run: bash app-src/ci/discovery/controls.sh access-log"
    assert text.count(marker) == 1
    broken = text.replace(marker, "run: true").replace(
        "run: bash app-src/ci/discovery/compare.sh --self-test",
        "run: bash app-src/ci/discovery/controls.sh access-log && bash app-src/ci/discovery/compare.sh --self-test",
    )

    assert flow_findings(broken) == ["the job discovery does not run the verdict in the order of plan 02-04"]


# -- cron after the apps (plan 02-17b) ----------------------------------------------
#
# A cron.php that begins before ./occ app:enable audio_video_search cannot
# build the jobs of the app, and JobList::buildJob removes their rows (run
# 43387183622: the control leg never got its first crawl). So the cron loop of
# both jobs starts only after the apps are enabled; ./occ background:cron only
# switches the mode and may come earlier.

CRON_LOOP = "do php cron.php;"
APP_API_ENABLED = "./occ app:enable -vvv -f app_api\n"
APPS_BEFORE_CRON = {
    "discovery": (
        "./occ app:enable audio_video_search",
        "./occ app:enable files_external",
        "./occ app:install files_accesscontrol",
    ),
    "leak-control": (
        "./occ app:enable audio_video_search",
        "./occ app:enable files_external",
    ),
}


def _code_offset(body: str, needle: str) -> int:
    """The offset of the first line holding needle that is no YAML or shell comment, or -1."""
    offset = 0
    for line in body.splitlines(keepends=True):
        if needle in line and not line.lstrip().startswith("#"):
            return offset
        offset += len(line)
    return -1


def cron_order_findings(text: str) -> list[str]:
    """Every job whose cron loop starts before one of its apps is enabled."""
    findings: list[str] = []
    for job, apps in APPS_BEFORE_CRON.items():
        body = job_text(text, job)
        cron = _code_offset(body, CRON_LOOP)
        if cron < 0:
            findings.append(f"the job {job} runs no cron loop")
            continue
        for app in apps:
            enabled = _code_offset(body, app)
            if enabled < 0:
                findings.append(f"the job {job} does not enable {app}")
            elif cron < enabled:
                findings.append(f"the job {job} starts cron before the app is enabled: {app}")
    return findings


def _cron_moved_up(text: str, job: str) -> str:
    """The workflow with the cron loop of one job back right after app_api, as it was at 25d241b."""
    body = job_text(text, job)
    lines = body.splitlines(keepends=True)
    loop = [line for line in lines if CRON_LOOP in line and not line.lstrip().startswith("#")]
    assert len(loop) == 1, f"{job} holds {len(loop)} cron loops"
    assert body.count(APP_API_ENABLED) == 1, f"{job} no longer enables app_api once"
    moved = body.replace(loop[0], "", 1).replace(APP_API_ENABLED, APP_API_ENABLED + loop[0], 1)
    return text.replace(body, moved, 1)


def test_cron_starts_after_the_apps_are_enabled() -> None:
    assert cron_order_findings(source()) == []


def test_the_cron_rule_fires_in_each_job_on_its_own() -> None:
    text = source()
    discovery = _cron_moved_up(text, "discovery")
    assert cron_order_findings(discovery) == [
        "the job discovery starts cron before the app is enabled: ./occ app:enable audio_video_search",
        "the job discovery starts cron before the app is enabled: ./occ app:enable files_external",
        "the job discovery starts cron before the app is enabled: ./occ app:install files_accesscontrol",
    ]
    control = _cron_moved_up(text, "leak-control")
    assert cron_order_findings(control) == [
        "the job leak-control starts cron before the app is enabled: ./occ app:enable audio_video_search",
        "the job leak-control starts cron before the app is enabled: ./occ app:enable files_external",
    ]


def test_the_cron_rule_reads_the_order_of_25d241b_as_too_early() -> None:
    # The lines of the control leg at 25d241b, word for word.
    old_control = (
        "jobs:\n  leak-control:\n    steps:\n      - name: Install\n        run: |\n"
        "          ./occ app:enable -vvv -f app_api\n"
        "          ./occ background:cron\n"
        '          (while true; do php cron.php; sleep 15; done) > "${RUNNER_TEMP}/cron.log" 2>&1 &\n'
        "          ./occ app:enable files_external\n"
        "          mv app-src/php apps/audio_video_search\n"
        "          ./occ app:enable audio_video_search\n"
    )
    assert [finding for finding in cron_order_findings(old_control) if "leak-control" in finding] == [
        "the job leak-control starts cron before the app is enabled: ./occ app:enable audio_video_search",
        "the job leak-control starts cron before the app is enabled: ./occ app:enable files_external",
    ]


def test_the_cron_rule_ignores_a_comment_and_fires_without_a_loop() -> None:
    text = source()
    commented = text.replace(
        "      - name: Install Nextcloud in debug mode and enable AppAPI\n",
        "      # (while true; do php cron.php; sleep 15; done)\n"
        "      - name: Install Nextcloud in debug mode and enable AppAPI\n",
    )
    assert cron_order_findings(commented) == []
    body = job_text(text, "leak-control")
    loop = next(line for line in body.splitlines(keepends=True) if CRON_LOOP in line)
    assert cron_order_findings(text.replace(body, body.replace(loop, ""), 1)) == [
        "the job leak-control runs no cron loop"
    ]
