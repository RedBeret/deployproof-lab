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

mkdir -p \
  .tools/bin \
  .tools/kubeconform-schemas \
  .secrets \
  artifacts/rendered \
  artifacts/reports \
  artifacts/state

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
  "alpine/helm:4.2.0@sha256:af08f75a3130d666a50b9fc150f40987ef20b885cf67659aabf4b83a5f2c5501"
  "ghcr.io/yannh/kubeconform:v0.7.0@sha256:85dbef6b4b312b99133decc9c6fc9495e9fc5f92293d4ff3b7e1b30f5611823c"
  "ghcr.io/kyverno/kyverno-cli:v1.18.1@sha256:b7e272572d244ddec0b83469f7200ba883555bf69de4b294cee52a197c8c6590"
  "grafana/k6:2.0.0@sha256:a33a0cfdc4d2483d6b7a3a22e726a499ff2831a671a49239104cd34a9937523c"
)
for image in "${tool_images[@]}"; do
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    docker pull "$image"
  fi
done

echo "Bootstrap complete. Run: ./scripts/lab.sh doctor"
