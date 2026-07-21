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

from deployproof import __version__
from deployproof.config import (
    APP_IMAGE_REPOSITORY,
    APP_VERSION,
    ARTIFACTS,
    CLUSTER_CONFIG,
    CLUSTER_NAME,
    FIXTURES,
    HELM_IMAGE,
    KIND_NODE_IMAGE,
    KUBE_CONTEXT,
    KUBECONFIG,
    KUBECONFORM_IMAGE,
    KUBERNETES_VERSION,
    KYVERNO_IMAGE,
    NAMESPACE,
    POLICIES,
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
    image: str, arguments: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return run(
        [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{ROOT}:/workspace",
            "--workdir",
            "/workspace",
            image,
            *arguments,
        ],
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


def nested(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


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
    run(["docker", "build", "--tag", image, "app"])
    print(image)
    return image


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
