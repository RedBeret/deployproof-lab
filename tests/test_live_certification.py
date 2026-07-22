from __future__ import annotations

import json
from typing import Any

import yaml

from deployproof import cli
from deployproof.config import RELEASE_CONTRACT

IMAGE_DIGEST = "sha256:" + "a" * 64


def contract() -> dict[str, Any]:
    return yaml.safe_load(RELEASE_CONTRACT.read_text(encoding="utf-8"))


def healthy_observations() -> dict[str, Any]:
    expected = contract()
    return {
        "release": {
            "application": expected["release"]["application"],
            "application_version": expected["release"]["applicationVersion"],
            "source_revision": "abc123",
            "configuration": {
                "customer_region": expected["configuration"]["customerRegion"],
                "environment": expected["configuration"]["environment"],
                "feature_mode": expected["configuration"]["featureMode"],
            },
            "configuration_sha256": expected["expected"]["configurationSha256"],
            "migration_version": expected["expected"]["migrationVersion"],
            "row_counts": expected["expected"]["rowCounts"],
            "data_sha256": expected["expected"]["dataSha256"],
        },
        "deployment": {
            "spec": {
                "template": {"spec": {"containers": [{"image": expected["release"]["image"]}]}}
            },
            "status": {"availableReplicas": 1},
        },
        "statefulset": {"status": {"readyReplicas": 1}},
        "configmap": {
            "data": {
                "APP_ENVIRONMENT": expected["configuration"]["environment"],
                "CUSTOMER_REGION": expected["configuration"]["customerRegion"],
                "FEATURE_MODE": expected["configuration"]["featureMode"],
            }
        },
        "jobs": {"items": [{"status": {"succeeded": 1}}]},
        "pods": {
            "items": [{"status": {"containerStatuses": [{"name": "api", "imageID": IMAGE_DIGEST}]}}]
        },
    }


def failed_check_names(observations: dict[str, Any]) -> list[str]:
    checks = cli.certification_checks(contract(), observations, "abc123", IMAGE_DIGEST)
    return [check["name"] for check in checks if not check["passed"]]


def test_matching_live_state_passes_every_comparison() -> None:
    checks = cli.certification_checks(contract(), healthy_observations(), "abc123", IMAGE_DIGEST)

    assert len(checks) == 14
    assert all(check["passed"] for check in checks)


def test_incomplete_data_load_fails_certification() -> None:
    observations = healthy_observations()
    observations["release"]["row_counts"] = {"inventory_items": 5}

    assert failed_check_names(observations) == ["database.row_counts"]


def test_extra_row_fails_exactly_the_gate_drift_checks() -> None:
    observations = healthy_observations()
    observations["release"]["row_counts"] = {"inventory_items": 7}
    observations["release"]["data_sha256"] = "sha256:" + "c" * 64

    assert set(failed_check_names(observations)) == cli.GATE_DRIFT_FAILURES


def test_verify_gate_is_a_registered_command() -> None:
    assert cli.parser().parse_args(["verify-gate"]).command == "verify-gate"


def test_wrong_configuration_fails_certification() -> None:
    observations = healthy_observations()
    observations["configmap"]["data"]["CUSTOMER_REGION"] = "lab-east"

    assert failed_check_names(observations) == ["kubernetes.configmap"]


def test_unexpected_image_fails_certification() -> None:
    observations = healthy_observations()
    containers = observations["deployment"]["spec"]["template"]["spec"]["containers"]
    containers[0]["image"] = "deployproof-api:0.0.9"

    assert failed_check_names(observations) == ["kubernetes.deployment_image"]


def test_stale_running_image_fails_on_digest() -> None:
    observations = healthy_observations()
    running = observations["pods"]["items"][0]["status"]["containerStatuses"][0]
    running["imageID"] = "sha256:" + "b" * 64

    assert failed_check_names(observations) == ["kubernetes.image_digest"]


def test_missing_running_pod_fails_on_digest() -> None:
    observations = healthy_observations()
    observations["pods"] = {"items": []}

    assert failed_check_names(observations) == ["kubernetes.image_digest"]


def test_unrecorded_expected_digest_fails_even_when_running_matches() -> None:
    checks = cli.certification_checks(contract(), healthy_observations(), "abc123", None)
    digest = next(check for check in checks if check["name"] == "kubernetes.image_digest")

    assert digest["expected"] is None
    assert not digest["passed"]


def test_running_image_id_strips_repository_prefix() -> None:
    prefixed = f"docker.io/library/deployproof-api@{IMAGE_DIGEST}"

    assert cli.normalize_image_id(prefixed) == IMAGE_DIGEST
    assert cli.normalize_image_id(IMAGE_DIGEST) == IMAGE_DIGEST
    assert cli.normalize_image_id(None) is None


def test_unfinished_migration_fails_certification() -> None:
    observations = healthy_observations()
    observations["jobs"] = {"items": [{"status": {}}]}

    assert failed_check_names(observations) == ["kubernetes.completed_migration_jobs"]


def test_unavailable_api_replica_fails_certification() -> None:
    observations = healthy_observations()
    observations["deployment"]["status"] = {}

    assert failed_check_names(observations) == ["kubernetes.api_replicas"]


def test_missing_observations_are_failures_not_implicit_passes() -> None:
    checks = cli.certification_checks(contract(), {}, "abc123")

    assert len(checks) == 14
    assert not any(check["passed"] for check in checks)


def test_contract_resolves_the_git_head_revision_sentinel() -> None:
    assert contract()["release"]["sourceRevision"] == "git-head"

    checks = cli.certification_checks(contract(), healthy_observations(), "abc123")
    revision = next(check for check in checks if check["name"] == "release.source_revision")

    assert revision["expected"] == "abc123"
    assert revision["passed"]


def test_certification_report_records_expected_and_observed_values() -> None:
    observations = healthy_observations()
    observations["release"]["migration_version"] = "001"
    checks = cli.certification_checks(contract(), observations, "abc123")
    migration = next(check for check in checks if check["name"] == "database.migration_version")

    assert migration["expected"] == "002"
    assert migration["observed"] == "001"
    assert not migration["passed"]


def test_certification_report_contains_no_credential_material() -> None:
    checks = cli.certification_checks(contract(), healthy_observations(), "abc123")
    serialized = json.dumps(checks).lower()

    assert "password" not in serialized
    assert "secret" not in serialized
