from __future__ import annotations

from typing import Any

import yaml

from deployproof import cli
from deployproof.config import RELEASE_CONTRACT


def smoke_specs() -> list[dict[str, Any]]:
    return yaml.safe_load(RELEASE_CONTRACT.read_text(encoding="utf-8"))["smoke"]


def healthy_responses() -> dict[str, tuple[int | None, Any]]:
    return {
        "/": (200, {"application": "deployproof-inventory", "project": "DeployProof Lab"}),
        "/live": (200, {"status": "alive"}),
        "/health": (200, {"status": "healthy"}),
        "/release-info": (200, {"application": "deployproof-inventory", "source_revision": "abc"}),
    }


def failing_names(responses: dict[str, tuple[int | None, Any]]) -> list[str]:
    checks = cli.evaluate_smoke(smoke_specs(), responses)
    return [check["name"] for check in checks if not check["passed"]]


def test_smoke_passes_when_every_endpoint_matches() -> None:
    checks = cli.evaluate_smoke(smoke_specs(), healthy_responses())

    assert len(checks) == 4
    assert all(check["passed"] for check in checks)


def test_degraded_health_fails_smoke() -> None:
    responses = healthy_responses()
    responses["/health"] = (503, {"status": "degraded"})

    assert failing_names(responses) == ["smoke /health"]


def test_wrong_body_field_fails_smoke() -> None:
    responses = healthy_responses()
    responses["/"] = (200, {"application": "someone-elses-app", "project": "DeployProof Lab"})

    assert failing_names(responses) == ["smoke /"]


def test_unreachable_endpoint_fails_smoke() -> None:
    responses = healthy_responses()
    responses["/release-info"] = (None, None)

    assert failing_names(responses) == ["smoke /release-info"]


def test_smoke_records_expected_and_observed_without_key_collision() -> None:
    responses = healthy_responses()
    responses["/live"] = (200, {"status": "starting"})
    checks = cli.evaluate_smoke(smoke_specs(), responses)
    live = next(check for check in checks if check["name"] == "smoke /live")

    # The HTTP status and the body's "status" field must not clobber each other.
    assert live["expected"] == {"status": 200, "body": {"status": "alive"}}
    assert live["observed"] == {"status": 200, "body": {"status": "starting"}}
    assert not live["passed"]


def test_smoke_command_is_registered() -> None:
    assert cli.parser().parse_args(["smoke"]).command == "smoke"
