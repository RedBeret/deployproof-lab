"""The GitHub workflow must run real entrypoints, the same rule .gitlab-ci.yml follows.

Without this the repository would carry a second, unenforced pipeline. tests/test_pipeline.py
only reads .gitlab-ci.yml, so a GitHub workflow could quietly grow build or validation logic
of its own and drift from what an operator runs.
"""

import argparse
from pathlib import Path
from typing import Any

import yaml

from deployproof.cli import parser

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# The static sequence CI must run. These are the commands the README documents as the
# workstation bootstrap sequence, and the GitLab static gate runs the same ones.
REQUIRED_COMMANDS = ("doctor", "test", "build", "render", "validate")

# Live certification creates a kind cluster and is written for a runner bound to the host
# Docker socket. It has never been exercised on a hosted runner, so it is not claimed here.
COMMANDS_NOT_CLAIMED_ON_HOSTED_RUNNERS = {
    "deploy",
    "certify",
    "smoke",
    "integration",
    "load",
    "verify-gate",
    "rollback-drill",
    "evidence",
    "clean-room",
}


def workflow() -> dict[str, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def run_steps() -> list[str]:
    steps = []
    for job in workflow()["jobs"].values():
        for step in job["steps"]:
            if "run" in step:
                steps.append(step["run"])
    return steps


def known_subcommands() -> set[str]:
    """Read the real subcommands off the argparse parser rather than a hand-kept list."""
    for action in parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("the deployctl parser exposes no subcommands")


def test_workflow_exists():
    assert WORKFLOW.is_file()


def test_every_required_command_runs():
    joined = "\n".join(run_steps())
    for command in REQUIRED_COMMANDS:
        assert f"./scripts/lab.sh {command}" in joined, f"CI does not run lab.sh {command}"


def test_the_static_sequence_matches_the_gitlab_static_gate():
    """Two pipelines running different static gates is the drift worth catching."""
    gitlab = yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    gitlab_static = [
        line.replace("./scripts/lab.sh ", "").strip()
        for line in gitlab["static gate"]["script"]
    ]
    actions_static = [
        step.replace("./scripts/lab.sh ", "").strip()
        for step in run_steps()
        if step.strip().startswith("./scripts/lab.sh ")
    ]
    assert actions_static == gitlab_static


def test_the_workflow_holds_no_logic_of_its_own():
    allowed = ("./scripts/lab.sh", "./scripts/bootstrap.sh")
    for step in run_steps():
        for line in (raw.strip() for raw in step.splitlines()):
            if not line or line.startswith("#"):
                continue
            assert line.startswith(allowed), f"workflow runs logic of its own: {line}"


def test_every_invoked_command_is_a_real_deployctl_subcommand():
    known = known_subcommands()
    assert known, "could not read subcommands off the parser"
    for step in run_steps():
        line = step.strip()
        if not line.startswith("./scripts/lab.sh "):
            continue
        command = line.replace("./scripts/lab.sh ", "").split()[0]
        assert command in known, f"{command} is not a deployctl subcommand"


def test_live_gates_are_not_claimed_on_a_hosted_runner():
    """They belong to .gitlab-ci.yml, which expects a host Docker socket. Recording the
    exclusion stops one being added here on the assumption it would work."""
    joined = "\n".join(run_steps())
    for command in COMMANDS_NOT_CLAIMED_ON_HOSTED_RUNNERS:
        assert f"./scripts/lab.sh {command}" not in joined, (
            f"{command} needs a kind cluster on a host Docker socket and is untested here"
        )


def test_no_run_step_interpolates_an_expression():
    """A run step containing an expression is how workflow injection happens."""
    for step in run_steps():
        assert "${{" not in step, f"run step interpolates an expression: {step}"


def test_permissions_are_least_privilege():
    assert workflow().get("permissions") == {"contents": "read"}


def test_rendered_manifests_are_published_and_an_empty_upload_is_an_error():
    steps = workflow()["jobs"]["static-gate"]["steps"]
    upload = [step for step in steps if "upload-artifact" in str(step.get("uses", ""))]
    assert upload, "rendered manifests are never published"
    assert upload[0]["with"]["if-no-files-found"] == "error"
