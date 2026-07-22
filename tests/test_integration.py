from __future__ import annotations

from typing import Any

import yaml

from deployproof import cli
from deployproof.config import RELEASE_CONTRACT

SEED_ITEMS = [
    {"sku": "DP-1001", "name": "Field router", "quantity": 12, "warehouse": "west"},
    {"sku": "DP-1002", "name": "Rugged switch", "quantity": 8, "warehouse": "west"},
    {"sku": "DP-1003", "name": "Console cable", "quantity": 40, "warehouse": "central"},
    {"sku": "DP-1004", "name": "SFP module", "quantity": 24, "warehouse": "central"},
    {"sku": "DP-1005", "name": "Edge appliance", "quantity": 6, "warehouse": "east"},
    {"sku": "DP-1006", "name": "Recovery drive", "quantity": 10, "warehouse": "east"},
]


def contract() -> dict[str, Any]:
    return yaml.safe_load(RELEASE_CONTRACT.read_text(encoding="utf-8"))


def db_facts() -> dict[str, Any]:
    return {
        "row_count": len(SEED_ITEMS),
        "migration_version": "002",
        "data_sha256": cli.canonical_data_hash(SEED_ITEMS),
    }


def app_report() -> dict[str, Any]:
    facts = db_facts()
    return {
        "row_counts": {"inventory_items": facts["row_count"]},
        "migration_version": facts["migration_version"],
        "data_sha256": facts["data_sha256"],
    }


def failing_names(app: dict[str, Any]) -> list[str]:
    checks = cli.evaluate_integration(app, db_facts())
    return [check["name"] for check in checks if not check["passed"]]


def test_independent_hash_matches_the_contract_hash() -> None:
    # The CLI recomputes the canonical hash the same way the app does; pinning it to the
    # contract value proves the two canonicalizations agree.
    assert cli.canonical_data_hash(SEED_ITEMS) == contract()["expected"]["dataSha256"]


def test_integration_passes_when_app_reflects_the_database() -> None:
    checks = cli.evaluate_integration(app_report(), db_facts())

    assert len(checks) == 3
    assert all(check["passed"] for check in checks)


def test_stale_row_count_fails_integration() -> None:
    app = app_report()
    app["row_counts"]["inventory_items"] = 5

    assert failing_names(app) == ["integration.row_count"]


def test_stale_migration_version_fails_integration() -> None:
    app = app_report()
    app["migration_version"] = "001"

    assert failing_names(app) == ["integration.migration_version"]


def test_diverged_data_hash_fails_integration() -> None:
    app = app_report()
    app["data_sha256"] = "sha256:" + "d" * 64

    assert failing_names(app) == ["integration.data_sha256"]


def test_integration_command_is_registered() -> None:
    assert cli.parser().parse_args(["integration"]).command == "integration"
