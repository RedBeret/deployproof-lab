#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$root"

if [[ ! -x .venv/bin/deployctl ]]; then
  echo "Project environment is missing. Run ./scripts/bootstrap.sh first." >&2
  exit 2
fi

export PATH="$root/.tools/bin:$PATH"
export DOCKER_CONFIG="$root/.docker"
exec .venv/bin/deployctl "$@"
