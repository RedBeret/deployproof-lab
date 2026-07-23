from __future__ import annotations

import pytest

from deployproof import cli
from deployproof.config import CLUSTER_NAME

NEIGHBOUR = {"kubedrift": {"kubedrift-control-plane": "running"}}
BEFORE = {CLUSTER_NAME: {f"{CLUSTER_NAME}-control-plane": "running"}, **NEIGHBOUR}


def result(stdout: str = "") -> object:
    return type("Result", (), {"returncode": 0, "stdout": stdout, "stderr": ""})()


def failures(checks: list[dict]) -> set[str]:
    return {check["name"] for check in checks if not check["passed"]}


def test_survey_groups_node_containers_by_their_kind_cluster(monkeypatch) -> None:
    lines = (
        "deployproof-control-plane\tdeployproof\trunning\n"
        "kubedrift-control-plane\tkubedrift\trunning\n"
    )
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: result(lines))

    assert cli.kind_node_survey() == BEFORE


def test_survey_ignores_containers_without_a_cluster_label(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: result("some-container\t\trunning\n"))

    assert cli.kind_node_survey() == {}


def test_clean_teardown_passes_every_check() -> None:
    checks = cli.evaluate_clean_room(BEFORE, NEIGHBOUR, {"kubedrift"}, kubeconfig_present=False)

    assert failures(checks) == set()


def test_a_surviving_project_container_fails() -> None:
    after = {CLUSTER_NAME: {f"{CLUSTER_NAME}-control-plane": "exited"}, **NEIGHBOUR}
    checks = cli.evaluate_clean_room(BEFORE, after, {"kubedrift"}, kubeconfig_present=False)

    # A stopped container is still a container left behind, so "exited" is not a pass.
    assert failures(checks) == {"clean_room.project_containers"}


def test_a_still_registered_cluster_or_kubeconfig_fails() -> None:
    checks = cli.evaluate_clean_room(
        BEFORE, NEIGHBOUR, {"kubedrift", CLUSTER_NAME}, kubeconfig_present=True
    )

    assert failures(checks) == {
        "clean_room.project_cluster_registered",
        "clean_room.isolated_kubeconfig_present",
    }


def test_removing_a_neighbouring_cluster_fails() -> None:
    # This is the KubeDrift safety contract: teardown must be inert for other clusters.
    checks = cli.evaluate_clean_room(BEFORE, {}, set(), kubeconfig_present=False)

    assert failures(checks) == {"clean_room.neighbour_nodes_unchanged"}


def test_stopping_a_neighbouring_node_fails() -> None:
    after = {"kubedrift": {"kubedrift-control-plane": "exited"}}
    checks = cli.evaluate_clean_room(BEFORE, after, {"kubedrift"}, kubeconfig_present=False)

    assert failures(checks) == {
        "clean_room.neighbour_nodes_unchanged",
        "clean_room.neighbour_nodes_running",
    }


def test_teardown_is_refused_when_there_is_nothing_to_tear_down(monkeypatch) -> None:
    deleted: list[str] = []
    monkeypatch.setattr(cli, "kind_node_survey", lambda: NEIGHBOUR)
    monkeypatch.setattr(cli, "delete_cluster", lambda: deleted.append("ran"))

    with pytest.raises(RuntimeError, match="prove nothing"):
        cli.run_clean_room()

    assert deleted == []


def test_teardown_is_refused_without_a_neighbouring_cluster(monkeypatch) -> None:
    # With nothing else running, a passing report would not show isolation at all.
    deleted: list[str] = []
    monkeypatch.setattr(
        cli,
        "kind_node_survey",
        lambda: {CLUSTER_NAME: {f"{CLUSTER_NAME}-control-plane": "running"}},
    )
    monkeypatch.setattr(cli, "delete_cluster", lambda: deleted.append("ran"))

    with pytest.raises(RuntimeError, match="other clusters running"):
        cli.run_clean_room()

    assert deleted == []
