from __future__ import annotations

from typing import Any

import yaml

from deployproof import cli
from deployproof.config import RELEASE_CONTRACT, ROOT


def load_config() -> dict[str, Any]:
    return yaml.safe_load(RELEASE_CONTRACT.read_text(encoding="utf-8"))["load"]


def sample_summary() -> dict[str, Any]:
    return {
        "metrics": {
            "http_req_duration": {"p(95)": 41.2, "avg": 12.0},
            "http_req_failed": {"value": 0.0, "passes": 0, "fails": 250},
            "checks": {"passes": 250, "fails": 0},
        }
    }


def test_contract_declares_load_thresholds() -> None:
    config = load_config()

    for key in ("path", "vus", "duration", "maxErrorRate", "maxP95Millis", "minCheckRate"):
        assert key in config, key


def test_k6_script_reads_every_threshold_from_the_environment() -> None:
    script = (ROOT / "load/liveness.js").read_text(encoding="utf-8")

    for token in ("MAX_ERROR_RATE", "MAX_P95_MILLIS", "MIN_CHECK_RATE", "thresholds"):
        assert token in script, token


def test_summarize_load_extracts_observed_metrics() -> None:
    report = cli.summarize_load(sample_summary(), load_config(), passed=True)

    assert report["passed"] is True
    assert report["observed"] == {"p95Millis": 41.2, "errorRate": 0.0, "checkRate": 1.0}
    assert report["thresholds"]["maxP95Millis"] == load_config()["maxP95Millis"]


def test_summarize_load_reports_the_exit_verdict_not_its_own() -> None:
    # The verdict comes from k6's exit code; summarize_load only records it alongside the
    # observed metrics, so a breached run is reported as failed even with a summary present.
    report = cli.summarize_load(sample_summary(), load_config(), passed=False)

    assert report["passed"] is False


def test_summarize_load_tolerates_a_missing_summary() -> None:
    report = cli.summarize_load({}, load_config(), passed=False)

    assert report["observed"] == {"p95Millis": None, "errorRate": None, "checkRate": None}
    assert report["passed"] is False


def test_load_command_is_registered() -> None:
    assert cli.parser().parse_args(["load"]).command == "load"
