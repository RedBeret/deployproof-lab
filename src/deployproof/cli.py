from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml

from deployproof import __version__
from deployproof.config import (
    APP_IMAGE_REPOSITORY,
    APP_VERSION,
    ARTIFACTS,
    CLUSTER_CONFIG,
    CLUSTER_NAME,
    FIXTURES,
    HELM_IMAGE,
    HOST_PORT,
    IMAGE_DIGEST_FILE,
    KIND_NODE_IMAGE,
    KUBE_CONTEXT,
    KUBECONFIG,
    KUBECONFORM_IMAGE,
    KUBERNETES_VERSION,
    KYVERNO_IMAGE,
    NAMESPACE,
    POLICIES,
    RELEASE_CONTRACT,
    RELEASE_NAME,
    ROLLOUT_TIMEOUT,
    ROOT,
    SECRETS,
    TOOLS_BIN,
)


def run(
    command: list[str],
    *,
    capture: bool = False,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=capture,
        input=input_text,
    )


def docker_tool(
    image: str,
    arguments: list[str],
    *,
    check: bool = True,
    host_network: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = ["docker", "run", "--rm"]
    if host_network:
        command.extend(["--network", "host"])
    command.extend(
        [
            "--volume",
            f"{ROOT}:/workspace",
            "--workdir",
            "/workspace",
            image,
            *arguments,
        ]
    )
    return run(
        command,
        capture=True,
        check=check,
    )


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def helm_lint() -> None:
    result = docker_tool(HELM_IMAGE, ["lint", "chart/deployproof"])
    print(result.stdout, end="")


def helm_render() -> Path:
    result = docker_tool(
        HELM_IMAGE,
        [
            "template",
            "deployproof",
            "chart/deployproof",
            "--namespace",
            "deployproof",
        ],
    )
    output = ARTIFACTS / "rendered" / "release.yaml"
    write_atomic(output, result.stdout)
    print(output.relative_to(ROOT))
    return output


def git_revision() -> str:
    return run(["git", "rev-parse", "HEAD"], capture=True).stdout.strip()


def image_digest(image: str) -> str:
    return run(["docker", "inspect", "--format", "{{.Id}}", image], capture=True).stdout.strip()


def record_image_digest(image: str) -> str:
    digest = image_digest(image)
    if not digest.startswith("sha256:"):
        raise RuntimeError(f"unexpected image digest for {image!r}: {digest!r}")
    write_atomic(IMAGE_DIGEST_FILE, f"{digest}\n")
    return digest


def normalize_image_id(image_id: str | None) -> str | None:
    if not image_id:
        return None
    return image_id.rsplit("@", 1)[-1]


def running_api_image_id(observations: dict[str, Any]) -> str | None:
    for pod in nested(observations, "pods", "items") or []:
        for status in nested(pod, "status", "containerStatuses") or []:
            if status.get("name") == "api":
                return normalize_image_id(status.get("imageID"))
    return None


def live_release_overrides(image_digest_value: str) -> list[str]:
    return [
        "--set-string",
        f"image.tag={APP_VERSION}",
        "--set-string",
        "image.pullPolicy=Never",
        "--set-string",
        f"application.imageDigest={image_digest_value}",
    ]


def helm_render_live(image_digest_value: str) -> Path:
    result = docker_tool(
        HELM_IMAGE,
        [
            "template",
            RELEASE_NAME,
            "chart/deployproof",
            "--namespace",
            NAMESPACE,
            *live_release_overrides(image_digest_value),
        ],
    )
    output = ARTIFACTS / "rendered" / "live-release.yaml"
    write_atomic(output, result.stdout)
    print(output.relative_to(ROOT))
    return output


def helm_cluster(arguments: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return docker_tool(
        HELM_IMAGE,
        [
            *arguments,
            "--kubeconfig",
            "/workspace/.kube/deployproof.yaml",
            "--kube-context",
            KUBE_CONTEXT,
        ],
        host_network=True,
        check=check,
    )


def kubectl(
    arguments: list[str],
    *,
    namespace: bool = True,
    capture: bool = False,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        "kubectl",
        "--kubeconfig",
        str(KUBECONFIG),
        "--context",
        KUBE_CONTEXT,
    ]
    if namespace:
        command.extend(["--namespace", NAMESPACE])
    command.extend(arguments)
    return run(command, capture=capture, check=check, input_text=input_text)


def project_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def print_process(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def require_result(
    result: subprocess.CompletedProcess[str], label: str, *, should_pass: bool
) -> None:
    if should_pass:
        print_process(result)
        if result.returncode != 0:
            raise RuntimeError(f"{label} failed with exit code {result.returncode}")
        print(f"ok {label}")
        return

    combined = f"{result.stdout}\n{result.stderr}"
    if result.returncode == 0:
        raise RuntimeError(f"{label} unexpectedly passed")
    if "fixture" not in combined:
        raise RuntimeError(f"{label} failed without identifying the fixture")
    print(f"ok {label}")


def kubeconform(resource: Path) -> subprocess.CompletedProcess[str]:
    (TOOLS_BIN.parent / "kubeconform-schemas").mkdir(parents=True, exist_ok=True)
    return docker_tool(
        KUBECONFORM_IMAGE,
        [
            "-strict",
            "-summary",
            "-verbose",
            "-kubernetes-version",
            KUBERNETES_VERSION,
            "-cache",
            "/workspace/.tools/kubeconform-schemas",
            project_path(resource),
        ],
        check=False,
    )


def kyverno(resource: Path) -> subprocess.CompletedProcess[str]:
    return docker_tool(
        KYVERNO_IMAGE,
        [
            "apply",
            project_path(POLICIES),
            "--resource",
            project_path(resource),
            "--continue-on-fail",
            "--detailed-results",
            "--remove-color",
            "--table",
        ],
        check=False,
    )


def validate_static() -> None:
    helm_lint()
    rendered = helm_render()

    require_result(kubeconform(rendered), "rendered Kubernetes schema", should_pass=True)
    require_result(
        kubeconform(FIXTURES / "invalid-deployment.yaml"),
        "invalid Kubernetes fixture rejection",
        should_pass=False,
    )
    require_result(kyverno(rendered), "rendered workload policies", should_pass=True)
    require_result(
        kyverno(FIXTURES / "policy-violation.yaml"),
        "unsafe workload fixture rejection",
        should_pass=False,
    )


def build_image() -> str:
    image = f"{APP_IMAGE_REPOSITORY}:{APP_VERSION}"
    run(
        [
            "docker",
            "build",
            "--build-arg",
            f"SOURCE_REVISION={git_revision()}",
            "--tag",
            image,
            "app",
        ]
    )
    print(image)
    return image


def kind_clusters() -> set[str]:
    result = run([str(TOOLS_BIN / "kind"), "get", "clusters"], capture=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def ensure_cluster_identity() -> None:
    if CLUSTER_NAME not in kind_clusters():
        raise RuntimeError(f"kind cluster {CLUSTER_NAME!r} does not exist")
    if not KUBECONFIG.is_file():
        raise RuntimeError(f"isolated kubeconfig is missing: {KUBECONFIG}")

    context = kubectl(["config", "current-context"], namespace=False, capture=True).stdout.strip()
    if context != KUBE_CONTEXT:
        raise RuntimeError(f"refusing context {context!r}; expected {KUBE_CONTEXT!r}")

    node = f"{CLUSTER_NAME}-control-plane"
    label = run(
        [
            "docker",
            "inspect",
            "--format",
            '{{ index .Config.Labels "io.x-k8s.kind.cluster" }}',
            node,
        ],
        capture=True,
    ).stdout.strip()
    if label != CLUSTER_NAME:
        raise RuntimeError(f"refusing Docker node {node!r} with cluster label {label!r}")


def wait_for_cluster_ready(timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = "cluster API did not respond"
    while time.monotonic() < deadline:
        result = kubectl(
            ["get", "nodes", "--output", "json"], namespace=False, capture=True, check=False
        )
        if result.returncode == 0:
            try:
                nodes = json.loads(result.stdout).get("items", [])
            except json.JSONDecodeError as error:
                last_error = f"invalid node response: {error}"
            else:
                ready = [
                    node
                    for node in nodes
                    if any(
                        condition.get("type") == "Ready" and condition.get("status") == "True"
                        for condition in nested(node, "status", "conditions") or []
                    )
                ]
                if ready:
                    print(f"ok cluster API ready with {len(ready)} node(s)")
                    return
                last_error = "cluster API responded but no node is Ready"
        else:
            last_error = (result.stderr or result.stdout).strip() or last_error
        time.sleep(2)
    raise RuntimeError(f"cluster did not become ready within {timeout_seconds}s: {last_error}")


def create_cluster() -> None:
    if CLUSTER_NAME in kind_clusters():
        ensure_cluster_identity()
        node = f"{CLUSTER_NAME}-control-plane"
        running = run(
            ["docker", "inspect", "--format", "{{.State.Running}}", node],
            capture=True,
        ).stdout.strip()
        if running != "true":
            run(["docker", "start", node])
            print(f"ok restarted stopped project node {node}")
        wait_for_cluster_ready()
        print(f"ok existing isolated cluster {CLUSTER_NAME}")
        return

    KUBECONFIG.parent.mkdir(parents=True, exist_ok=True)
    KUBECONFIG.unlink(missing_ok=True)
    run(
        [
            str(TOOLS_BIN / "kind"),
            "create",
            "cluster",
            "--name",
            CLUSTER_NAME,
            "--image",
            KIND_NODE_IMAGE,
            "--config",
            str(CLUSTER_CONFIG),
            "--kubeconfig",
            str(KUBECONFIG),
            "--wait",
            ROLLOUT_TIMEOUT,
        ]
    )
    ensure_cluster_identity()
    wait_for_cluster_ready()
    print(f"ok created isolated cluster {CLUSTER_NAME}")


def cluster_status() -> None:
    ensure_cluster_identity()
    wait_for_cluster_ready()
    result = kubectl(["cluster-info"], namespace=False, capture=True)
    print(result.stdout, end="")
    print(f"ok context {KUBE_CONTEXT}")


def delete_cluster() -> None:
    if CLUSTER_NAME not in kind_clusters():
        print(f"ok cluster {CLUSTER_NAME} is already absent")
        return
    ensure_cluster_identity()
    run([str(TOOLS_BIN / "kind"), "delete", "cluster", "--name", CLUSTER_NAME])
    KUBECONFIG.unlink(missing_ok=True)
    print(f"ok deleted isolated cluster {CLUSTER_NAME}")


def apply_namespace_and_secret() -> None:
    namespace_yaml = kubectl(
        ["create", "namespace", NAMESPACE, "--dry-run=client", "--output", "yaml"],
        namespace=False,
        capture=True,
    ).stdout
    kubectl(
        ["apply", "--server-side", "--field-manager", "deployproof", "--filename", "-"],
        namespace=False,
        input_text=namespace_yaml,
    )

    password = (SECRETS / "db-password").read_bytes()
    if not password or b"\n" in password or b"\r" in password:
        raise RuntimeError("generated database credential contains a line ending; run bootstrap")

    secret_yaml = kubectl(
        [
            "create",
            "secret",
            "generic",
            "deployproof-db",
            f"--from-file=password={SECRETS / 'db-password'}",
            "--dry-run=client",
            "--output",
            "yaml",
        ],
        capture=True,
    ).stdout
    kubectl(
        ["apply", "--server-side", "--field-manager", "deployproof", "--filename", "-"],
        input_text=secret_yaml,
    )


def kubectl_json(arguments: list[str], *, namespace: bool = True) -> dict[str, Any]:
    result = kubectl([*arguments, "--output", "json"], namespace=namespace, capture=True)
    return json.loads(result.stdout)


def nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def certification_checks(
    contract: dict[str, Any],
    observations: dict[str, Any],
    source_revision: str,
    expected_image_digest: str | None = None,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, expected: Any, observed: Any, *, passed: bool | None = None) -> None:
        checks.append(
            {
                "name": name,
                "expected": expected,
                "observed": observed,
                "passed": expected == observed if passed is None else passed,
            }
        )

    expected_release = contract["release"]
    expected_config = contract["configuration"]
    expected_state = contract["expected"]
    release = observations.get("release", {})

    contract_revision = expected_release["sourceRevision"]
    resolved_revision = source_revision if contract_revision == "git-head" else contract_revision
    normalized_config = {
        "customer_region": expected_config["customerRegion"],
        "environment": expected_config["environment"],
        "feature_mode": expected_config["featureMode"],
    }
    expected_configmap = {
        "APP_ENVIRONMENT": expected_config["environment"],
        "CUSTOMER_REGION": expected_config["customerRegion"],
        "FEATURE_MODE": expected_config["featureMode"],
    }

    containers = nested(observations, "deployment", "spec", "template", "spec", "containers")
    deployment_image = containers[0].get("image") if containers else None
    completed_jobs = sum(
        1
        for item in nested(observations, "jobs", "items") or []
        if nested(item, "status", "succeeded")
    )
    minimum_jobs = expected_state["completedMigrationJobs"]

    add("release.application", expected_release["application"], release.get("application"))
    add(
        "release.application_version",
        expected_release["applicationVersion"],
        release.get("application_version"),
    )
    add("release.source_revision", resolved_revision, release.get("source_revision"))
    add("kubernetes.deployment_image", expected_release["image"], deployment_image)
    observed_image_digest = running_api_image_id(observations)
    add(
        "kubernetes.image_digest",
        expected_image_digest,
        observed_image_digest,
        passed=bool(expected_image_digest) and expected_image_digest == observed_image_digest,
    )
    add("configuration.values", normalized_config, release.get("configuration"))
    add(
        "configuration.sha256",
        expected_state["configurationSha256"],
        release.get("configuration_sha256"),
    )
    add(
        "kubernetes.configmap",
        expected_configmap,
        nested(observations, "configmap", "data"),
    )
    add(
        "database.migration_version",
        expected_state["migrationVersion"],
        release.get("migration_version"),
    )
    add("database.row_counts", expected_state["rowCounts"], release.get("row_counts"))
    add("database.data_sha256", expected_state["dataSha256"], release.get("data_sha256"))
    add(
        "kubernetes.api_replicas",
        expected_state["apiReplicas"],
        nested(observations, "deployment", "status", "availableReplicas"),
    )
    add(
        "kubernetes.database_replicas",
        expected_state["databaseReplicas"],
        nested(observations, "statefulset", "status", "readyReplicas"),
    )
    add(
        "kubernetes.completed_migration_jobs",
        f">={minimum_jobs}",
        completed_jobs,
        passed=completed_jobs >= minimum_jobs,
    )
    return checks


def load_release_contract() -> dict[str, Any]:
    content = yaml.safe_load(RELEASE_CONTRACT.read_text(encoding="utf-8"))
    if content.get("formatVersion") != 1:
        raise RuntimeError("unsupported release contract format")
    return content


def fetch_release_info() -> dict[str, Any]:
    with urlopen(f"http://127.0.0.1:{HOST_PORT}/release-info", timeout=5) as response:
        return json.load(response)


def recorded_image_digest() -> str | None:
    if not IMAGE_DIGEST_FILE.is_file():
        return None
    digest = IMAGE_DIGEST_FILE.read_text(encoding="utf-8").strip()
    return digest or None


def gather_live_observations() -> dict[str, Any]:
    return {
        "release": fetch_release_info(),
        "deployment": kubectl_json(["get", "deployment", "deployproof-api"]),
        "statefulset": kubectl_json(["get", "statefulset", "deployproof-postgresql"]),
        "configmap": kubectl_json(["get", "configmap", "deployproof-config"]),
        "jobs": kubectl_json(
            [
                "get",
                "jobs",
                "--selector",
                "app.kubernetes.io/component=migration",
            ]
        ),
        "pods": kubectl_json(["get", "pods", "--selector", "app.kubernetes.io/component=api"]),
    }


def run_live_certification() -> dict[str, Any]:
    ensure_cluster_identity()
    wait_for_cluster_ready()
    revision = git_revision()
    checks = certification_checks(
        load_release_contract(), gather_live_observations(), revision, recorded_image_digest()
    )
    passed = all(check["passed"] for check in checks)
    report = {
        "formatVersion": 1,
        "sourceRevision": revision,
        "checks": checks,
        "passed": passed,
    }
    output = ARTIFACTS / "state" / "live-certification.json"
    write_atomic(output, f"{json.dumps(report, indent=2, sort_keys=True)}\n")

    for check in checks:
        outcome = "PASS" if check["passed"] else "FAIL"
        print(f"{outcome} {check['name']}")
    print(output.relative_to(ROOT))
    return report


def certify_live() -> bool:
    return run_live_certification()["passed"]


GATE_PROBE_SKU = "GATE-PROBE"
GATE_DRIFT_FAILURES = {"database.row_counts", "database.data_sha256"}


def postgres_sql(statement: str) -> str:
    result = kubectl(
        [
            "exec",
            "deployproof-postgresql-0",
            "-c",
            "postgresql",
            "--",
            "psql",
            "-U",
            "deployproof",
            "-d",
            "deployproof",
            "-tAc",
            statement,
        ],
        capture=True,
    )
    return result.stdout.strip()


def remove_gate_probe() -> None:
    postgres_sql(f"DELETE FROM inventory_items WHERE sku = '{GATE_PROBE_SKU}';")


def verify_live_gate() -> int:
    ensure_cluster_identity()
    wait_for_cluster_ready()

    remove_gate_probe()
    print("== baseline ==")
    if not run_live_certification()["passed"]:
        raise RuntimeError("live gate baseline is not green; run deploy before verify-gate")

    print("== drifted database ==")
    postgres_sql(
        "INSERT INTO inventory_items (sku, name, quantity, warehouse) "
        f"VALUES ('{GATE_PROBE_SKU}', 'certification gate probe', 0, 'none');"
    )
    try:
        report = run_live_certification()
        failing = {check["name"] for check in report["checks"] if not check["passed"]}
        if report["passed"] or failing != GATE_DRIFT_FAILURES:
            raise RuntimeError(
                f"expected drift to fail exactly {sorted(GATE_DRIFT_FAILURES)}, "
                f"observed failures {sorted(failing)}"
            )
    finally:
        remove_gate_probe()

    print("== restored ==")
    if not run_live_certification()["passed"]:
        raise RuntimeError("live gate did not return to green after removing the probe row")

    print(f"ok live gate rejects drift ({sorted(GATE_DRIFT_FAILURES)}) and recovers")
    return 0


def collect_live_diagnostics(reason: str) -> Path:
    sections = [f"DeployProof deployment diagnostics\nreason: {reason}\n"]

    def record(label: str, result: subprocess.CompletedProcess[str]) -> None:
        sections.append(
            f"\n## {label}\nexit_code: {result.returncode}\n{result.stdout}{result.stderr}"
        )

    record(
        "Helm status",
        helm_cluster(
            ["status", RELEASE_NAME, "--namespace", NAMESPACE],
            check=False,
        ),
    )
    for label, arguments in (
        ("Resources", ["get", "all,pvc", "--output", "wide"]),
        ("Events", ["get", "events", "--sort-by=.lastTimestamp"]),
    ):
        record(label, kubectl(arguments, capture=True, check=False))

    pods = kubectl(["get", "pods", "--output", "json"], capture=True, check=False)
    record("Pods", pods)
    if pods.returncode == 0:
        try:
            pod_names = [item["metadata"]["name"] for item in json.loads(pods.stdout)["items"]]
        except (KeyError, json.JSONDecodeError):
            pod_names = []
        for pod_name in pod_names:
            record(
                f"Describe pod {pod_name}",
                kubectl(["describe", "pod", pod_name], capture=True, check=False),
            )
            record(
                f"Logs pod {pod_name}",
                kubectl(
                    ["logs", pod_name, "--all-containers", "--tail=100"],
                    capture=True,
                    check=False,
                ),
            )

    output = ARTIFACTS / "state" / "deploy-diagnostics.txt"
    write_atomic(output, "\n".join(sections))
    print(f"diagnostics: {output.relative_to(ROOT)}", file=sys.stderr)
    return output


def deploy_live() -> None:
    create_cluster()
    validate_static()
    image = build_image()
    run(
        [
            str(TOOLS_BIN / "kind"),
            "load",
            "docker-image",
            image,
            "--name",
            CLUSTER_NAME,
        ]
    )
    digest = record_image_digest(image)
    print(f"ok recorded image digest {digest}")
    apply_namespace_and_secret()

    rendered = helm_render_live(digest)
    require_result(kubeconform(rendered), "live Kubernetes schema", should_pass=True)
    require_result(kyverno(rendered), "live workload policies", should_pass=True)
    dry_run = kubectl(
        [
            "apply",
            "--server-side",
            "--dry-run=server",
            "--field-manager",
            "helm",
            "--filename",
            str(rendered),
        ],
        capture=True,
        check=False,
    )
    print_process(dry_run)
    if dry_run.returncode != 0:
        collect_live_diagnostics(f"server-side dry-run exited with code {dry_run.returncode}")
        raise RuntimeError(f"server-side dry-run failed with exit code {dry_run.returncode}")

    result = helm_cluster(
        [
            "upgrade",
            "--install",
            RELEASE_NAME,
            "chart/deployproof",
            "--namespace",
            NAMESPACE,
            "--wait",
            "--wait-for-jobs",
            "--timeout",
            ROLLOUT_TIMEOUT,
            *live_release_overrides(digest),
        ],
        check=False,
    )
    print_process(result)
    if result.returncode != 0:
        collect_live_diagnostics(f"Helm exited with code {result.returncode}")
        raise RuntimeError(f"Helm deployment failed with exit code {result.returncode}")

    try:
        kubectl(
            [
                "rollout",
                "status",
                "statefulset/deployproof-postgresql",
                f"--timeout={ROLLOUT_TIMEOUT}",
            ]
        )
        kubectl(
            [
                "wait",
                "--for=condition=complete",
                "job",
                "--selector=app.kubernetes.io/component=migration",
                f"--timeout={ROLLOUT_TIMEOUT}",
            ]
        )
        kubectl(
            [
                "rollout",
                "status",
                "deployment/deployproof-api",
                f"--timeout={ROLLOUT_TIMEOUT}",
            ]
        )
    except subprocess.CalledProcessError as error:
        collect_live_diagnostics(f"rollout command exited with code {error.returncode}")
        raise
    if not certify_live():
        raise RuntimeError("live release certification failed")


def doctor() -> int:
    failures: list[str] = []
    for command in ("git", "python3", "docker", "kubectl", "curl", "sha256sum"):
        if shutil.which(command):
            print(f"ok command {command}")
        else:
            failures.append(f"missing command {command}")

    try:
        run(["docker", "info"], capture=True)
        print("ok docker daemon")
    except (OSError, subprocess.CalledProcessError):
        failures.append("docker daemon unavailable")

    kind = TOOLS_BIN / "kind"
    if kind.is_file() and os.access(kind, os.X_OK):
        print("ok project kind binary")
    else:
        failures.append("project kind binary missing; run scripts/bootstrap.sh")

    password = SECRETS / "db-password"
    password_bytes = password.read_bytes() if password.is_file() else b""
    if password_bytes and b"\r" not in password_bytes and b"\n" not in password_bytes:
        print("ok generated database credential")
    else:
        failures.append("generated database credential missing, empty, or contains a line ending")

    for failure in failures:
        print(f"error {failure}", file=sys.stderr)
    return int(bool(failures))


def test_project() -> None:
    commands = [
        [sys.executable, "-m", "pytest"],
        [sys.executable, "-m", "ruff", "format", "--check", "."],
        [sys.executable, "-m", "ruff", "check", "."],
        ["bash", "-n", "scripts/bootstrap.sh"],
        ["bash", "-n", "scripts/lab.sh"],
    ]
    for command in commands:
        run(command)
    validate_static()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="deployctl")
    root.add_argument("--version", action="version", version=f"deployctl {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check the local operator environment")
    commands.add_parser("build", help="build the sample application image")
    commands.add_parser("render", help="render the Helm release")
    commands.add_parser("validate", help="run static manifest and policy gates")
    commands.add_parser("deploy", help="deploy and certify the release in the isolated cluster")
    commands.add_parser("certify", help="compare the release contract with live state")
    commands.add_parser(
        "verify-gate", help="prove the live certification gate rejects drift and recovers"
    )
    commands.add_parser("test", help="run local validation")
    cluster = commands.add_parser("cluster", help="manage only the isolated DeployProof cluster")
    cluster_commands = cluster.add_subparsers(dest="cluster_command", required=True)
    cluster_commands.add_parser("create", help="create or verify the isolated cluster")
    cluster_commands.add_parser("status", help="show the isolated cluster status")
    cluster_commands.add_parser("delete", help="delete only the isolated cluster")
    return root


def main() -> int:
    arguments = parser().parse_args()
    if arguments.command == "doctor":
        return doctor()
    if arguments.command == "build":
        build_image()
        return 0
    if arguments.command == "render":
        helm_lint()
        helm_render()
        return 0
    if arguments.command == "validate":
        validate_static()
        return 0
    if arguments.command == "deploy":
        deploy_live()
        return 0
    if arguments.command == "certify":
        return 0 if certify_live() else 1
    if arguments.command == "verify-gate":
        return verify_live_gate()
    if arguments.command == "test":
        test_project()
        return 0
    if arguments.command == "cluster":
        if arguments.cluster_command == "create":
            create_cluster()
            return 0
        if arguments.cluster_command == "status":
            cluster_status()
            return 0
        if arguments.cluster_command == "delete":
            delete_cluster()
            return 0
        raise AssertionError(arguments.cluster_command)
    raise AssertionError(arguments.command)


if __name__ == "__main__":
    raise SystemExit(main())
