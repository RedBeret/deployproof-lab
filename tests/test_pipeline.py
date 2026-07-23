import argparse
import re
from pathlib import Path
from typing import Any

import yaml

from deployproof.cli import parser

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / ".gitlab-ci.yml"
SCRIPT_SECTIONS = ("before_script", "script", "after_script")
RESERVED_KEYS = {"stages", "default", "variables", "workflow", "include"}

# certify is not called by name because deploy ends by certifying the release it installed
# and evidence certifies again to produce its three reports. clean-room is a workstation
# proof: it requires a neighbouring kind cluster to show teardown is inert, and a CI runner
# has none, so the live job uses plain cluster delete to clean up instead.
COMMANDS_NOT_CALLED_IN_CI = {"certify", "clean-room"}


def pipeline() -> dict[str, Any]:
    return yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))


def jobs() -> dict[str, Any]:
    return {
        name: body
        for name, body in pipeline().items()
        if name not in RESERVED_KEYS and isinstance(body, dict)
    }


def sections(body: dict[str, Any]) -> list[str]:
    return [line for section in SCRIPT_SECTIONS for line in body.get(section, [])]


def script_lines() -> list[str]:
    document = pipeline()
    lines = sections(document.get("default", {}))
    for body in jobs().values():
        lines.extend(sections(body))
    return lines


def declared_commands() -> set[str]:
    for action in parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("the deployctl parser exposes no subcommands")


def invoked_commands() -> set[str]:
    invoked = set()
    for line in script_lines():
        fields = line.split()
        if fields[:1] == ["./scripts/lab.sh"]:
            invoked.add(fields[1])
    return invoked


def test_pipeline_runs_only_local_entrypoints() -> None:
    # The pipeline must hold no logic of its own, so every line is either the bootstrap
    # script or a real deployctl subcommand. Renaming a command fails this test.
    commands = declared_commands()
    for line in script_lines():
        fields = line.split()
        if fields == ["./scripts/bootstrap.sh"]:
            continue
        assert fields[0] == "./scripts/lab.sh", line
        assert fields[1] in commands, line


def test_pipeline_matches_the_documented_local_sequence() -> None:
    # The README tells an operator how to validate locally. The static stage must run that
    # exact sequence, so the two cannot describe different workflows.
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    block = re.search(r"```bash\n(.*?)```", readme, re.S)
    assert block is not None, "the README no longer documents a local validation sequence"
    documented = [line.strip() for line in block.group(1).strip().splitlines()]

    document = pipeline()
    actual = sections(document["default"]) + document["static gate"]["script"]

    assert actual == documented


def test_every_gate_command_runs_somewhere_in_the_pipeline() -> None:
    # A gate that exists locally but never runs in CI would let a release ship uncertified.
    expected = declared_commands() - COMMANDS_NOT_CALLED_IN_CI

    assert expected - invoked_commands() == set()


def test_live_job_publishes_the_junit_report_the_lab_writes() -> None:
    reports = pipeline()["live certification"]["artifacts"]["reports"]
    cli = (ROOT / "src/deployproof/cli.py").read_text(encoding="utf-8")

    assert reports["junit"] == "artifacts/evidence/certification.xml"
    assert 'directory / "certification.xml"' in cli


def test_live_job_removes_the_cluster_even_when_a_gate_fails() -> None:
    # after_script runs whether or not the gates passed, so a failed pipeline does not
    # strand a kind cluster on the runner.
    live = pipeline()["live certification"]

    assert live["after_script"] == ["./scripts/lab.sh cluster delete"]
    assert live["artifacts"]["when"] == "always"
