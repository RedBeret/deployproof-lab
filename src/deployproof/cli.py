from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from deployproof import __version__
from deployproof.config import (
    APP_IMAGE_REPOSITORY,
    APP_VERSION,
    ARTIFACTS,
    FIXTURES,
    HELM_IMAGE,
    KUBECONFORM_IMAGE,
    KUBERNETES_VERSION,
    KYVERNO_IMAGE,
    POLICIES,
    ROOT,
    SECRETS,
    TOOLS_BIN,
)


def run(
    command: list[str], *, capture: bool = False, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=check,
        text=True,
        capture_output=capture,
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
    raise AssertionError(arguments.command)


if __name__ == "__main__":
    raise SystemExit(main())
