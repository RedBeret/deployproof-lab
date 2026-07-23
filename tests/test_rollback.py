from __future__ import annotations

from typing import Any

import pytest

from deployproof import cli

BASELINE_REGION = "lab-west"
DECLARED_REVISION = 7
CHECK_NAMES = (
    "release.application",
    "configuration.values",
    "configuration.sha256",
    "kubernetes.configmap",
)


def report(*failures: str) -> dict[str, Any]:
    return {
        "passed": not failures,
        "checks": [{"name": name, "passed": name not in failures} for name in CHECK_NAMES],
    }


GREEN = report()
SUPERSEDED = report("configuration.values", "configuration.sha256", "kubernetes.configmap")


def install(
    monkeypatch,
    certifications: list[dict[str, Any]],
    *,
    smokes: list[dict[str, Any]] | None = None,
    baseline_region: str = BASELINE_REGION,
) -> list[str]:
    events: list[str] = []
    state = {"region": baseline_region}

    monkeypatch.setattr(cli, "ensure_cluster_identity", lambda: None)
    monkeypatch.setattr(cli, "wait_for_cluster_ready", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "wait_for_api_rollout", lambda: None)
    monkeypatch.setattr(cli, "helm_revision", lambda: DECLARED_REVISION)
    monkeypatch.setattr(cli, "configured_region", lambda: state["region"])

    certifications_left = iter(certifications)
    smokes_left = iter(smokes if smokes is not None else [GREEN, GREEN])

    def certify() -> dict[str, Any]:
        events.append("certify")
        return next(certifications_left)

    def smoke() -> dict[str, Any]:
        events.append("smoke")
        return next(smokes_left)

    def upgrade(region: str) -> None:
        events.append(f"upgrade:{region}")
        state["region"] = region

    def rollback(revision: int) -> None:
        events.append(f"rollback:{revision}")
        state["region"] = baseline_region

    monkeypatch.setattr(cli, "run_live_certification", certify)
    monkeypatch.setattr(cli, "run_smoke", smoke)
    monkeypatch.setattr(cli, "helm_release_region", upgrade)
    monkeypatch.setattr(cli, "helm_rollback", rollback)
    return events


def test_drill_supersedes_then_restores_the_declared_release(monkeypatch) -> None:
    events = install(monkeypatch, [GREEN, SUPERSEDED, GREEN])

    assert cli.rollback_drill() == 0
    assert events == [
        "certify",
        f"upgrade:{cli.ROLLBACK_DRILL_REGION}",
        "smoke",
        "certify",
        f"rollback:{DECLARED_REVISION}",
        "certify",
        "smoke",
    ]


def test_drill_refuses_a_baseline_that_is_not_green(monkeypatch) -> None:
    events = install(monkeypatch, [report("release.application")])

    with pytest.raises(RuntimeError, match="baseline is not green"):
        cli.rollback_drill()

    # Nothing was installed, so a red cluster is not disturbed further.
    assert events == ["certify"]


def test_drill_refuses_when_the_declared_release_already_uses_the_drill_region(monkeypatch) -> None:
    events = install(monkeypatch, [GREEN], baseline_region=cli.ROLLBACK_DRILL_REGION)

    with pytest.raises(RuntimeError, match="would change nothing"):
        cli.rollback_drill()

    assert events == ["certify"]


def test_drill_rolls_back_when_the_superseding_release_fails_the_wrong_checks(monkeypatch) -> None:
    # If the superseding release fails something other than the configuration checks, the
    # drill is not measuring what it claims, so it aborts. It must still restore the release.
    events = install(monkeypatch, [GREEN, report("database.row_counts")])

    with pytest.raises(RuntimeError, match="expected the superseding release to fail exactly"):
        cli.rollback_drill()

    assert f"rollback:{DECLARED_REVISION}" in events


def test_drill_rolls_back_when_the_superseding_release_is_not_serving(monkeypatch) -> None:
    # The drill only ever installs healthy releases. If the second one does not serve traffic,
    # that is a real defect, and the declared release is restored before reporting it.
    events = install(monkeypatch, [GREEN, GREEN], smokes=[report("smoke /health")])

    with pytest.raises(RuntimeError, match="not serving its declared endpoints"):
        cli.rollback_drill()

    assert f"rollback:{DECLARED_REVISION}" in events


def test_drill_reports_a_rollback_that_did_not_restore_configuration(monkeypatch) -> None:
    events = install(monkeypatch, [GREEN, SUPERSEDED])
    monkeypatch.setattr(cli, "helm_rollback", lambda revision: events.append("rollback:noop"))

    with pytest.raises(RuntimeError, match="rollback left region"):
        cli.rollback_drill()
