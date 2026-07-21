#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"

for command in python3 docker git kubectl curl sha256sum; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

mkdir -p .docker
if [[ ! -f .docker/config.json ]]; then
  printf '{"auths":{}}\n' > .docker/config.json
fi
export DOCKER_CONFIG="$root/.docker"

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but its daemon is unavailable." >&2
  exit 1
fi

venv_args=()
if [[ -f .venv/pyvenv.cfg ]]; then
  configured_executable="$(sed -n 's/^executable = //p' .venv/pyvenv.cfg | head -n 1)"
  configured_real="$(readlink -f -- "$configured_executable" 2>/dev/null || true)"
  current_real="$(python3 -c 'import os, sys; print(os.path.realpath(sys.executable))')"
  if [[ -z "$configured_real" || "$configured_real" != "$current_real" ]]; then
    echo "Python interpreter changed; rebuilding the virtual environment."
    venv_args=(--clear)
  fi
fi

python3 -m venv "${venv_args[@]}" .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt -e .

mkdir -p .tools/bin .secrets artifacts/rendered artifacts/reports artifacts/state

kind_version="v0.31.0"
kind_binary=".tools/bin/kind"
if [[ ! -x "$kind_binary" ]] || ! "$kind_binary" version | grep -Fq "$kind_version"; then
  temporary="$(mktemp .tools/bin/kind.XXXXXX)"
  trap 'rm -f -- "$temporary"' EXIT
  curl --fail --location --silent --show-error \
    "https://kind.sigs.k8s.io/dl/${kind_version}/kind-linux-amd64" \
    --output "$temporary"
  expected="$(curl --fail --location --silent --show-error \
    "https://kind.sigs.k8s.io/dl/${kind_version}/kind-linux-amd64.sha256sum" | awk '{print $1}')"
  printf '%s  %s\n' "$expected" "$temporary" | sha256sum --check --status
  chmod 755 "$temporary"
  mv -- "$temporary" "$kind_binary"
  trap - EXIT
fi

if [[ ! -f .secrets/db-password ]]; then
  .venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(36))' \
    > .secrets/db-password
fi
chmod 600 .secrets/db-password

tool_images=(
  "alpine/helm:4.2.0"
  "ghcr.io/yannh/kubeconform:v0.7.0"
  "ghcr.io/kyverno/kyverno-cli:v1.18.1"
  "grafana/k6:2.0.0"
)
for image in "${tool_images[@]}"; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker pull "$image"
  fi
done

echo "Bootstrap complete. Run: ./scripts/lab.sh doctor"
