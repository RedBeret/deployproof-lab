from deployproof_api import main


def test_live_does_not_depend_on_database(monkeypatch) -> None:
    def unavailable() -> None:
        raise ConnectionError

    monkeypatch.setattr(main, "database_facts", unavailable)

    assert main.live() == {"status": "alive"}


def test_configuration_fingerprint_is_stable(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENVIRONMENT", "certification")
    monkeypatch.setenv("CUSTOMER_REGION", "lab-west")
    monkeypatch.setenv("FEATURE_MODE", "standard")

    first = main.configuration_fingerprint()
    second = main.configuration_fingerprint()

    assert first == second
    assert len(first) == 64


def test_release_payload_contains_runtime_and_database_evidence(monkeypatch) -> None:
    monkeypatch.setattr(
        main,
        "database_facts",
        lambda: {
            "data_sha256": "d" * 64,
            "migration_version": "002",
            "row_counts": {"inventory_items": 6},
        },
    )

    payload = main.release_payload()

    assert payload["application"] == "deployproof-inventory"
    assert payload["migration_version"] == "002"
    assert payload["row_counts"] == {"inventory_items": 6}
    assert len(payload["configuration_sha256"]) == 64


def test_health_degrades_without_database(monkeypatch) -> None:
    def unavailable() -> None:
        raise ConnectionError

    monkeypatch.setattr(main, "database_facts", unavailable)

    response = main.health()

    assert response.status_code == 503
    assert b"ConnectionError" in response.body
