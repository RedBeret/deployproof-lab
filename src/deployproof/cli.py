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
    HELM_IMAGE,
    ROOT,
    SECRETS,
    TOOLS_BIN,
)


def run(command: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=capture,
    )


def docker_tool(image: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
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
    if password.is_file():
        print("ok generated database credential")
    else:
        failures.append("generated database credential missing")

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
    helm_lint()
    helm_render()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="deployctl")
    root.add_argument("--version", action="version", version=f"deployctl {__version__}")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="check the local operator environment")
    commands.add_parser("build", help="build the sample application image")
    commands.add_parser("render", help="render the Helm release")
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
    if arguments.command == "test":
        test_project()
        return 0
    raise AssertionError(arguments.command)


if __name__ == "__main__":
    raise SystemExit(main())
