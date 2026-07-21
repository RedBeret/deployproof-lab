from __future__ import annotations

import json
from pathlib import Path

import pytest

from deployproof import cli
from deployproof.config import CLUSTER_NAME, KUBE_CONTEXT, NAMESPACE


def result(returncode: int = 0, stdout: str = "", stderr: str = "") -> object:
    return type("Result", (), {"returncode": returncode, "stdout": stdout, "stderr": stderr})()


def test_kubectl_wrapper_always_uses_isolated_context(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return result(stdout="{}")

    monkeypatch.setattr(cli, "run", fake_run)
    cli.kubectl(["get", "deployment", "deployproof-api"], capture=True)

    command = calls[0]
    assert command[:5] == [
        "kubectl",
        "--kubeconfig",
        str(cli.KUBECONFIG),
        "--context",
        KUBE_CONTEXT,
    ]
    assert command[5:7] == ["--namespace", NAMESPACE]


def test_cluster_readiness_retries_until_node_is_ready(monkeypatch) -> None:
    responses = iter(
        [
            result(returncode=1, stderr="starting"),
            result(
                stdout=json.dumps(
                    {"items": [{"status": {"conditions": [{"type": "Ready", "status": "True"}]}}]}
                )
            ),
        ]
    )

    monkeypatch.setattr(cli, "kubectl", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)

    cli.wait_for_cluster_ready(timeout_seconds=5)


def test_cluster_readiness_fails_when_no_node_becomes_ready(monkeypatch) -> None:
    monkeypatch.setattr(cli, "kubectl", lambda *args, **kwargs: result(stdout=json.dumps({})))
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="did not become ready"):
        cli.wait_for_cluster_ready(timeout_seconds=0)


def test_identity_check_refuses_a_missing_cluster(monkeypatch) -> None:
    monkeypatch.setattr(cli, "kind_clusters", lambda: {"kubedrift"})

    with pytest.raises(RuntimeError, match="does not exist"):
        cli.ensure_cluster_identity()


def present_kubeconfig(monkeypatch, tmp_path: Path) -> None:
    kubeconfig = tmp_path / "deployproof.yaml"
    kubeconfig.write_text("", encoding="utf-8")
    monkeypatch.setattr(cli, "KUBECONFIG", kubeconfig)


def test_identity_check_refuses_a_foreign_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "kind_clusters", lambda: {CLUSTER_NAME})
    present_kubeconfig(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "kubectl", lambda *args, **kwargs: result(stdout="kind-kubedrift\n"))

    with pytest.raises(RuntimeError, match="refusing context"):
        cli.ensure_cluster_identity()


def test_identity_check_refuses_a_foreign_docker_node(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "kind_clusters", lambda: {CLUSTER_NAME})
    present_kubeconfig(monkeypatch, tmp_path)
    monkeypatch.setattr(cli, "kubectl", lambda *args, **kwargs: result(stdout=f"{KUBE_CONTEXT}\n"))
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: result(stdout="kubedrift\n"))

    with pytest.raises(RuntimeError, match="cluster label"):
        cli.ensure_cluster_identity()


def test_delete_refuses_when_identity_check_fails(monkeypatch) -> None:
    deleted: list[str] = []

    def refuse() -> None:
        raise RuntimeError("refusing context 'kind-kubedrift'")

    monkeypatch.setattr(cli, "kind_clusters", lambda: {CLUSTER_NAME})
    monkeypatch.setattr(cli, "ensure_cluster_identity", refuse)
    monkeypatch.setattr(cli, "run", lambda *args, **kwargs: deleted.append("ran") or result())

    with pytest.raises(RuntimeError):
        cli.delete_cluster()

    assert deleted == []
