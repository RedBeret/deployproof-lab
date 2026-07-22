from __future__ import annotations

from typing import Any

from deployproof import cli

GENERATED_AT = "2026-07-22T00:00:00+00:00"


def sample_checks() -> list[dict[str, Any]]:
    return [
        {"name": "release.application", "expected": "app", "observed": "app", "passed": True},
        {
            "name": "kubernetes.configmap",
            "expected": {"CUSTOMER_REGION": "lab-west"},
            "observed": {"CUSTOMER_REGION": "lab-east"},
            "passed": False,
        },
        {"name": "database.row_counts", "expected": 6, "observed": 6, "passed": True},
    ]


def evidence() -> dict[str, Any]:
    return cli.build_evidence(sample_checks(), GENERATED_AT)


def test_build_evidence_counts_and_outcome() -> None:
    doc = evidence()

    assert doc["counts"] == {"total": 3, "passed": 2, "failed": 1}
    assert doc["outcome"] == "failed"


def test_all_passing_checks_report_passed() -> None:
    checks = [dict(check, passed=True) for check in sample_checks()]

    assert cli.build_evidence(checks, GENERATED_AT)["outcome"] == "passed"


def test_markdown_reports_outcome_counts_and_every_check() -> None:
    markdown = cli.render_markdown(evidence())

    assert "- Outcome: failed" in markdown
    assert "2 passed, 1 failed, 3 total" in markdown
    for check in sample_checks():
        assert check["name"] in markdown
    assert markdown.count("| FAIL |") == 1
    assert markdown.count("| PASS |") == 2


def test_junit_reports_counts_and_marks_only_the_failure() -> None:
    # The generated XML is asserted as text; parsing self-generated XML with a stdlib
    # parser is the pattern security tooling flags, and there is nothing untrusted to parse.
    xml = cli.render_junit(evidence())

    assert xml.startswith("<testsuite ")
    assert 'tests="3"' in xml
    assert 'failures="1"' in xml
    assert xml.count("<failure ") == 1
    assert 'name="kubernetes.configmap"' in xml


def test_three_formats_agree_on_outcome_and_counts() -> None:
    doc = evidence()
    xml = cli.render_junit(doc)
    markdown = cli.render_markdown(doc)
    counts = doc["counts"]

    assert f'tests="{counts["total"]}"' in xml
    assert f'failures="{counts["failed"]}"' in xml
    assert (
        f"{counts['passed']} passed, {counts['failed']} failed, {counts['total']} total" in markdown
    )
    assert f"- Outcome: {doc['outcome']}" in markdown


def test_evidence_contains_no_secret_material() -> None:
    doc = evidence()
    rendered = (cli.render_markdown(doc) + cli.render_junit(doc)).lower()

    assert "password" not in rendered
    assert "secret" not in rendered


def test_evidence_command_is_registered() -> None:
    assert cli.parser().parse_args(["evidence"]).command == "evidence"
