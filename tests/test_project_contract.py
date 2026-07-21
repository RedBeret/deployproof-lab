import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_required_foundation_files_exist() -> None:
    for relative in (
        "scripts/bootstrap.sh",
        "scripts/lab.sh",
        "kind/cluster.yaml",
        "app/Dockerfile",
        "chart/deployproof/Chart.yaml",
        "chart/deployproof/values.yaml",
        "chart/deployproof/values.schema.json",
        "chart/deployproof/templates/deployment.yaml",
        "chart/deployproof/templates/migration-job.yaml",
        "policies/workload-security.yaml",
        "policies/release-images.yaml",
        "tests/fixtures/invalid-deployment.yaml",
        "tests/fixtures/policy-violation.yaml",
    ):
        assert (ROOT / relative).is_file(), relative


def test_kind_port_is_loopback_only() -> None:
    cluster = yaml.safe_load((ROOT / "kind/cluster.yaml").read_text(encoding="utf-8"))
    mapping = cluster["nodes"][0]["extraPortMappings"][0]

    assert mapping == {
        "containerPort": 30082,
        "hostPort": 18082,
        "listenAddress": "127.0.0.1",
        "protocol": "TCP",
    }


def test_values_schema_rejects_unknown_root_keys_and_latest_tag() -> None:
    schema = json.loads((ROOT / "chart/deployproof/values.schema.json").read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert schema["properties"]["image"]["properties"]["tag"]["not"] == {"const": "latest"}


def test_container_drops_root() -> None:
    dockerfile = (ROOT / "app/Dockerfile").read_text(encoding="utf-8")

    assert "USER 10001:10001" in dockerfile
    assert "PIP_NO_CACHE_DIR=1" in dockerfile


def test_external_images_are_digest_pinned() -> None:
    config = (ROOT / "src/deployproof/config.py").read_text(encoding="utf-8")
    values = yaml.safe_load((ROOT / "chart/deployproof/values.yaml").read_text(encoding="utf-8"))

    assert config.count("@sha256:") == 5
    assert "@sha256:" in values["postgresql"]["image"]


def test_postgresql_owns_its_data_directory() -> None:
    statefulset = (ROOT / "chart/deployproof/templates/postgresql-statefulset.yaml").read_text(
        encoding="utf-8"
    )

    assert "value: /var/lib/postgresql/data/database" in statefulset
    assert "subPath:" not in statefulset


def test_bootstrap_generates_credential_without_line_endings() -> None:
    bootstrap = (ROOT / "scripts/bootstrap.sh").read_text(encoding="utf-8")

    assert "sys.stdout.write(secrets.token_urlsafe(36))" in bootstrap
    assert "tr -d '\\r\\n'" in bootstrap


def test_generated_state_is_ignored() -> None:
    patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

    assert ".tools/" in patterns
    assert ".secrets/" in patterns
    assert ".kube/" in patterns
    assert "artifacts/*" in patterns
